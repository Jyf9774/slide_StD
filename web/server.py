"""
FastAPI backend for StD Pipeline Dashboard.
Wraps the existing pipeline modules and provides REST API + WebSocket progress.
"""
import sys
import os
import json
import uuid
import asyncio
import shutil
import re
import queue as queue_mod
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="StD Pipeline Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
OUTPUT_DIR = PROJECT_ROOT / "output"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Task state management
tasks: dict = {}
active_websockets: dict[str, list[WebSocket]] = {}


# Spinner frame characters used by media.progress.Spinner
_SPINNER_CHARS = frozenset('⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏')


def _is_spinner_line(msg: str) -> bool:
    """Check if a log message is a spinner progress line."""
    return bool(msg) and msg[0] in _SPINNER_CHARS


def _spinner_msg_key(msg: str) -> str:
    """Extract the stable message prefix from a spinner line for dedup.
    e.g. '⠇ VLM分析幻灯片整体信息... 6s' -> 'VLM分析幻灯片整体信息'
    """
    idx = msg.find('...')
    return msg[1:idx].strip() if idx > 0 else ""


async def _log(task_id: str, message: str):
    """Append a log line to a task and broadcast it.

    Consecutive spinner updates with the same message prefix are merged
    in-place so the frontend log panel doesn't flood with repetitive lines.
    """
    if task_id in tasks:
        tasks[task_id].setdefault("logs", [])
        entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": message}
        logs = tasks[task_id]["logs"]

        # Merge consecutive spinner lines (e.g. "⠇ VLM分析... 6s" -> "⠹ VLM分析... 7s")
        if (_is_spinner_line(message)
                and logs
                and _is_spinner_line(logs[-1]["msg"])
                and _spinner_msg_key(message) == _spinner_msg_key(logs[-1]["msg"])):
            logs[-1] = entry  # replace in-place, keep count stable
        else:
            logs.append(entry)

        await broadcast_progress(task_id, tasks[task_id])


class OutputCapture:
    """Intercepts sys.stdout writes and queues complete lines for async log consumption."""

    def __init__(self, original):
        self._original = original
        self._queue: queue_mod.Queue = queue_mod.Queue()
        self._buffer = ""

    def write(self, text: str) -> int:
        if self._original:
            self._original.write(text)
        self._buffer += text
        # Split on \n or \r (progress-bar style output)
        parts = re.split(r'[\r\n]+', self._buffer)
        self._buffer = parts[-1]  # incomplete trailing part
        for part in parts[:-1]:
            stripped = part.strip()
            if stripped:
                self._queue.put(stripped)
        return len(text)

    def flush(self):
        if self._original:
            self._original.flush()
        if self._buffer.strip():
            self._queue.put(self._buffer.strip())
            self._buffer = ""

    def get_lines(self) -> list[str]:
        lines = []
        while True:
            try:
                lines.append(self._queue.get_nowait())
            except queue_mod.Empty:
                break
        return lines

    @property
    def encoding(self):
        return getattr(self._original, "encoding", "utf-8")

    def isatty(self):
        return False


async def _run_with_logs(task_id: str, func):
    """Run a blocking function in executor while capturing its stdout as real-time task logs."""
    capture = OutputCapture(sys.__stdout__)
    finished = asyncio.Event()

    def wrapped():
        old_stdout = sys.stdout
        sys.stdout = capture
        try:
            return func()
        finally:
            sys.stdout = old_stdout
            capture.flush()

    async def drain():
        while not finished.is_set():
            for line in capture.get_lines():
                await _log(task_id, line)
            try:
                await asyncio.wait_for(finished.wait(), timeout=0.4)
            except asyncio.TimeoutError:
                pass
        # Final drain
        for line in capture.get_lines():
            await _log(task_id, line)

    drain_task = asyncio.create_task(drain())
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, wrapped)
    finally:
        finished.set()
        await drain_task

    return result


class ProcessConfig(BaseModel):
    use_vlm: bool = True
    hybrid_mode: bool = True
    min_area: int = 300
    use_original_bg: bool = True
    mask_elements: bool = True
    verbose: bool = True


class NarrateConfig(BaseModel):
    language: str = "zh"
    style: str = "formal"


class TTSConfig(BaseModel):
    voice: str = "Cherry"
    use_llm_animation: bool = True


# --- Helper ---
async def broadcast_progress(task_id: str, data: dict):
    if task_id in active_websockets:
        for ws in active_websockets[task_id]:
            try:
                await ws.send_json(data)
            except Exception:
                pass


def scan_output_dir() -> list[dict]:
    """Scan the output directory and return a list of processed slides."""
    results = []
    if not OUTPUT_DIR.exists():
        return results
    for slide_dir in sorted(OUTPUT_DIR.iterdir()):
        if not slide_dir.is_dir() or slide_dir.name.startswith("."):
            continue
        # Find metadata JSON
        meta_json = None
        narration_json = None
        animation_json = None
        audio_info_json = None
        pptx_file = None
        original_image = None

        for f in slide_dir.iterdir():
            if f.suffix == ".json" and not f.name.endswith("_narration.json"):
                meta_json = f
            elif f.name.endswith("_narration.json"):
                narration_json = f
            elif f.suffix == ".pptx":
                pptx_file = f
            elif f.name.startswith("original_"):
                original_image = f

        # Check subdirs
        anim_path = slide_dir / "animation" / "animation_scheme.json"
        if anim_path.exists():
            animation_json = anim_path
        tts_audio_path = slide_dir / "tts" / "audio_info.json"
        if tts_audio_path.exists():
            audio_info_json = tts_audio_path

        if meta_json and meta_json.exists():
            try:
                meta = json.loads(meta_json.read_text(encoding="utf-8"))
                results.append({
                    "name": slide_dir.name,
                    "slide_id": meta.get("slide_id", ""),
                    "title": meta.get("title", slide_dir.name),
                    "description": meta.get("description", ""),
                    "element_count": meta.get("element_count", 0),
                    "width": meta.get("width", 0),
                    "height": meta.get("height", 0),
                    "background_color": meta.get("background_color", "#ffffff"),
                    "created_at": meta.get("created_at", ""),
                    "has_narration": narration_json is not None,
                    "has_animation": animation_json is not None,
                    "has_tts": audio_info_json is not None,
                    "has_pptx": pptx_file is not None,
                    "original_image": f"/api/files/{slide_dir.name}/{original_image.name}" if original_image else None,
                })
            except Exception:
                pass
    return results


# --- API Routes ---

@app.get("/api/slides")
async def list_slides():
    return scan_output_dir()


@app.get("/api/slides/{slide_name}")
async def get_slide_detail(slide_name: str):
    slide_dir = OUTPUT_DIR / slide_name
    if not slide_dir.exists():
        raise HTTPException(404, "Slide not found")

    # Find and read metadata JSON
    meta = None
    narration = None
    animation = None
    audio_info = None

    for f in slide_dir.iterdir():
        if f.suffix == ".json" and not f.name.endswith("_narration.json"):
            meta = json.loads(f.read_text(encoding="utf-8"))
        elif f.name.endswith("_narration.json"):
            narration = json.loads(f.read_text(encoding="utf-8"))

    anim_path = slide_dir / "animation" / "animation_scheme.json"
    if anim_path.exists():
        animation = json.loads(anim_path.read_text(encoding="utf-8"))

    tts_path = slide_dir / "tts" / "audio_info.json"
    if tts_path.exists():
        audio_info = json.loads(tts_path.read_text(encoding="utf-8"))

    if not meta:
        raise HTTPException(404, "Metadata not found")

    # Fix element image paths to be API URLs
    for elem in meta.get("elements", []):
        img_path = elem.get("image_path", "")
        if img_path:
            elem["image_url"] = f"/api/files/{slide_name}/{img_path}"

    # Fix audio paths
    if audio_info:
        for seg in audio_info.get("segments", []):
            audio_path = seg.get("audio_path", "")
            if audio_path:
                # The path might be relative to project root
                rel = audio_path.replace(f"output/{slide_name}/", "")
                seg["audio_url"] = f"/api/files/{slide_name}/{rel}"
        full_path = audio_info.get("full_audio_path", "")
        if full_path:
            rel = full_path.replace(f"output/{slide_name}/", "")
            audio_info["full_audio_url"] = f"/api/files/{slide_name}/{rel}"

    # Find original image and PPTX
    original_image = None
    pptx_url = None
    for f in slide_dir.iterdir():
        if f.name.startswith("original_"):
            original_image = f"/api/files/{slide_name}/{f.name}"
        elif f.suffix == ".pptx":
            pptx_url = f"/api/files/{slide_name}/{f.name}"

    return {
        "metadata": meta,
        "narration": narration,
        "animation": animation,
        "audio_info": audio_info,
        "original_image": original_image,
        "pptx_url": pptx_url,
    }


@app.get("/api/files/{slide_name}/{file_path:path}")
async def serve_file(slide_name: str, file_path: str):
    full_path = OUTPUT_DIR / slide_name / file_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, "File not found")
    # Security: ensure path is within output dir
    try:
        full_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        raise HTTPException(403, "Access denied")
    return FileResponse(full_path)


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
        raise HTTPException(400, f"Unsupported format: {ext}")

    save_path = UPLOAD_DIR / file.filename
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    return {"filename": file.filename, "path": str(save_path), "size": len(content)}


@app.get("/api/uploads")
async def list_uploads():
    files = []
    if UPLOAD_DIR.exists():
        for f in sorted(UPLOAD_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
                files.append({
                    "filename": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                })
    # Also list images in project root
    for f in sorted(PROJECT_ROOT.iterdir()):
        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg") and not f.name.startswith("."):
            files.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "source": "project",
            })
    return files


@app.get("/api/preview/{filename}")
async def preview_image(filename: str):
    """Serve an uploaded or project-root image for preview."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        file_path = PROJECT_ROOT / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "File not found")
    # Security: only serve from allowed dirs
    resolved = file_path.resolve()
    if not (str(resolved).startswith(str(UPLOAD_DIR.resolve())) or str(resolved).startswith(str(PROJECT_ROOT.resolve()))):
        raise HTTPException(403, "Access denied")
    return FileResponse(file_path)


@app.post("/api/process")
async def start_process(config: ProcessConfig, filename: str):
    """Start slide processing pipeline."""
    # Find the file
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        file_path = PROJECT_ROOT / filename
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {filename}")

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "id": task_id,
        "filename": filename,
        "status": "queued",
        "step": "",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "result": None,
        "error": None,
    }

    asyncio.create_task(_run_process(task_id, str(file_path), config))
    return {"task_id": task_id}


async def _run_process(task_id: str, image_path: str, config: ProcessConfig):
    """Run the pipeline in background."""
    try:
        tasks[task_id]["status"] = "running"
        tasks[task_id]["step"] = "slide_processing"
        tasks[task_id]["progress"] = 5
        await _log(task_id, f"Starting pipeline for {Path(image_path).name}")

        from pipeline import process_slide
        loop = asyncio.get_event_loop()

        mode = "hybrid (DocLayout-YOLO + VLM)" if config.hybrid_mode else ("VLM" if config.use_vlm else "CV fallback")
        await _log(task_id, f"Analysis mode: {mode}")

        tasks[task_id]["progress"] = 10
        tasks[task_id]["step"] = "layout_detection"
        await _log(task_id, "Running layout detection...")

        json_path, pptx_path = await _run_with_logs(
            task_id,
            lambda: process_slide(
                image_path,
                str(OUTPUT_DIR),
                use_vlm=config.use_vlm,
                use_original_bg=config.use_original_bg,
                mask_elements=config.mask_elements,
                min_area=config.min_area,
                verbose=config.verbose,
                hybrid_mode=config.hybrid_mode,
            )
        )

        tasks[task_id]["progress"] = 90
        tasks[task_id]["step"] = "reconstruction_complete"
        await _log(task_id, f"Reconstruction done -> {Path(pptx_path).name}")

        # Read element count from result
        try:
            meta = json.loads(Path(json_path).read_text(encoding="utf-8"))
            elem_count = meta.get("element_count", "?")
            await _log(task_id, f"Detected {elem_count} elements, metadata saved")
        except Exception:
            pass

        slide_name = Path(image_path).stem
        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["step"] = "done"
        tasks[task_id]["result"] = {
            "slide_name": slide_name,
            "json_path": json_path,
            "pptx_path": pptx_path,
        }
        await _log(task_id, "Slide processing complete")

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        await _log(task_id, f"ERROR: {e}")


@app.post("/api/narrate/{slide_name}")
async def start_narration(slide_name: str, config: NarrateConfig):
    """Generate narration for a processed slide."""
    slide_dir = OUTPUT_DIR / slide_name
    if not slide_dir.exists():
        raise HTTPException(404, "Slide not found")

    # Find metadata JSON
    json_path = None
    for f in slide_dir.iterdir():
        if f.suffix == ".json" and not f.name.endswith("_narration.json"):
            json_path = str(f)
            break
    if not json_path:
        raise HTTPException(404, "Metadata JSON not found")

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "id": task_id,
        "filename": slide_name,
        "status": "running",
        "step": "narration_generation",
        "progress": 30,
        "created_at": datetime.now().isoformat(),
        "result": None,
        "error": None,
    }

    asyncio.create_task(_run_narration(task_id, json_path, config))
    return {"task_id": task_id}


async def _run_narration(task_id: str, json_path: str, config: NarrateConfig):
    try:
        from narration_generator import generate_narration

        await _log(task_id, f"Generating narration (lang={config.language}, style={config.style})")
        tasks[task_id]["progress"] = 30
        await broadcast_progress(task_id, tasks[task_id])

        await _log(task_id, "Calling LLM for narration text...")
        tasks[task_id]["progress"] = 50
        await broadcast_progress(task_id, tasks[task_id])

        narration = await _run_with_logs(
            task_id,
            lambda: generate_narration(json_path, language=config.language, style=config.style)
        )

        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["step"] = "done"
        tasks[task_id]["result"] = {"narration": "generated"}
        await _log(task_id, "Narration generated successfully")
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        await _log(task_id, f"ERROR: {e}")


@app.post("/api/tts/{slide_name}")
async def start_tts(slide_name: str, config: TTSConfig):
    """Generate TTS audio and animation for a slide."""
    slide_dir = OUTPUT_DIR / slide_name
    if not slide_dir.exists():
        raise HTTPException(404, "Slide not found")

    narration_json = None
    for f in slide_dir.iterdir():
        if f.name.endswith("_narration.json"):
            narration_json = str(f)
            break
    if not narration_json:
        raise HTTPException(404, "Narration JSON not found. Generate narration first.")

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "id": task_id,
        "filename": slide_name,
        "status": "running",
        "step": "tts_synthesis",
        "progress": 20,
        "created_at": datetime.now().isoformat(),
        "result": None,
        "error": None,
    }

    asyncio.create_task(_run_tts(task_id, narration_json, str(slide_dir), config))
    return {"task_id": task_id}


async def _run_tts(task_id: str, narration_json: str, output_dir: str, config: TTSConfig):
    try:
        from media import generate_tts_and_animations

        await _log(task_id, f"Starting TTS synthesis (voice={config.voice})")
        tasks[task_id]["progress"] = 20
        await broadcast_progress(task_id, tasks[task_id])

        await _log(task_id, "Synthesizing speech audio segments...")
        tasks[task_id]["progress"] = 40
        await broadcast_progress(task_id, tasks[task_id])

        result = await _run_with_logs(
            task_id,
            lambda: generate_tts_and_animations(
                narration_json_path=narration_json,
                output_dir=output_dir,
                voice=config.voice,
                use_llm_animation=config.use_llm_animation,
            )
        )

        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["step"] = "done"
        tasks[task_id]["result"] = {"tts": "generated"}
        anim_note = "LLM animation scheme" if config.use_llm_animation else "rule-based animation"
        await _log(task_id, f"TTS & {anim_note} generated successfully")
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        await _log(task_id, f"ERROR: {e}")


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")
    return tasks[task_id]


@app.get("/api/tasks")
async def list_tasks():
    return list(tasks.values())


@app.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    if task_id not in active_websockets:
        active_websockets[task_id] = []
    active_websockets[task_id].append(websocket)

    try:
        # Send current state
        if task_id in tasks:
            await websocket.send_json(tasks[task_id])
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_websockets[task_id].remove(websocket)
        if not active_websockets[task_id]:
            del active_websockets[task_id]


@app.get("/api/config/defaults")
async def get_default_config():
    return {
        "process": {
            "use_vlm": True,
            "hybrid_mode": True,
            "min_area": 300,
            "use_original_bg": True,
            "mask_elements": True,
        },
        "narrate": {
            "language": "zh",
            "style": "formal",
            "languages": ["zh", "en"],
            "styles": ["formal", "casual", "academic"],
        },
        "tts": {
            "voice": "Cherry",
            "use_llm_animation": True,
            "voices": [
                {"id": "Cherry", "label": "Cherry / 芊悦 (阳光亲切女声)"},
                {"id": "Serena", "label": "Serena / 苏瑶 (温柔女声)"},
                {"id": "Ethan", "label": "Ethan / 晨煦 (阳光活力男声)"},
            ],
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)
