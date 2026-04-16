# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Slide Screenshot Segmentation and PPTX Reconstruction Pipeline v4.0** - A Python tool that automatically converts slide screenshots into editable PowerPoint (PPTX) files with full speech synthesis and animation generation:
- Qwen3.6-Plus VLM (Vision Language Model) analysis as primary solution
- DocLayout-YOLO for professional layout detection
- Traditional Computer Vision/OCR as fallback option
- OpenCV for image processing and contour detection
- python-pptx for PPTX reconstruction
- LLM-based narration generation
- Qwen3-TTS integration for speech synthesis
- LLM-driven intelligent animation generation synchronized with narration timing

## Commands

### Install Dependencies

**macOS:**
```bash
brew install tesseract tesseract-lang ffmpeg
pip install -r requirements.txt
```

**Linux:**
```bash
apt-get install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng ffmpeg
pip install -r requirements.txt
```

### Run Demo

```bash
python demo.py                    # Use default test_slide.png
python demo.py <image_path>       # Use custom image
python demo.py --lang=en          # Generate English narration
python demo.py --no-vlm           # Use traditional CV/OCR only (no VLM)
python demo.py --hybrid           # Use DocLayout-YOLO + VLM hybrid mode (default)
```

### Command-line Batch Processing

```bash
python batch.py process <slide.png> -o ./output        # Process single image
python batch.py process <slide.png> -o ./output --no-vlm  # Process without VLM
python batch.py batch ./slides -o ./output             # Batch process directory
python batch.py batch ./slides -o ./output --no-vlm    # Batch process without VLM
python batch.py merge ./output -o presentation.pptx    # Merge into single PPTX
python batch.py narrate ./output -o narration.json     # Generate narration scripts
python batch.py tts narration.json -o ./tts_output      # Generate TTS audio + animation scheme
python batch.py tts narration.json -o ./tts_output --no-llm  # Generate TTS without LLM animation
```

### API Usage

```python
from pipeline import process_slide
json_path, pptx_path = process_slide("slide.png", "./output")

from narration_generator import generate_narration
narration = generate_narration(json_path, language="zh")

from media import generate_tts_and_animations
result = generate_tts_and_animations(
    narration_json_path="narration.json",
    output_dir="./tts_output"
)
```

## Architecture

### Core Modules

| File | Purpose |
|------|---------|
| `pipeline/` | **Main v4 pipeline package** with modular architecture:
| `pipeline/models.py` | Data models: `ElementType`, `BoundingBox`, `SlideElement`, `SlideMetadata` |
| `pipeline/vlm_analyzer.py` | Qwen3.6-Plus VLM analyzer for semantic understanding |
| `pipeline/layout_analyzer.py` | DocLayout-YOLO professional layout detector |
| `pipeline/cv_analyzer.py` | Traditional CV fallback analyzer |
| `pipeline/processor.py` | Main pipeline processor `SlideProcessor` |
| `pipeline/reconstructor.py` | PPTX reconstructor `SlideReconstructor` |
| `pipeline/cli.py` | Command-line interface and utility functions |
| `batch.py` | Batch processing with CLI, configuration, parallel execution, and full workflow support |
| `demo.py` | Demonstration script with command-line interface |
| `narration_generator.py` | LLM-based narration generation for TTS |
| `media/` | Media processing package:
| `media/tts_synthesizer.py` | Qwen3-TTS speech synthesis |
| `media/animation_generator.py` | LLM-driven intelligent animation generation |
| `openai_client.py` | OpenAI/DashScope API client management |
| `key_manage.py` | API key storage for Qwen/OpenAI services |

### Pipeline Flow

1. **Layout Detection** (`LayoutAnalyzer`):
   - Uses DocLayout-YOLO to detect professional slide layout elements
   - Provides high-precision bounding boxes for different element types

2. **Semantic Analysis** (`VLMAnalyzer`):
   - Qwen3.6-Plus VLM analyzes whole slide (background color, title, overall description)
   - Analyzes each detected region (type, text content, semantic meaning, importance)
   - Generates structured metadata for all elements

3. **Fallback Processing** (`CVFallbackAnalyzer`):
   - When VLM is unavailable, uses traditional CV (K-means for background, Tesseract OCR, rule-based classification)
   - Maintains functionality even without internet/API access

4. **Reconstruction** (`SlideReconstructor`):
   - Uses original image as background with elements masked out using background color
   - Inserts each detected element as an image at the original coordinates
   - Saves as `.pptx` file preserving original layout and visual fidelity

5. **Narration Generation** (optional):
   - Generates natural-language descriptions per slide and per element
   - Output JSON ready for text-to-speech processing

6. **TTS Synthesis & Animation Generation** (optional):
   - Synthesizes speech audio for each narration segment using Qwen3-TTS
   - LLM analyzes speech timing and generates synchronized animation scheme
   - Outputs audio files and animation configuration ready for presentation

### Data Structures

- `SlideMetadata`: Complete slide information including all elements, background color, title, description
- `SlideElement`: Individual element (type, bounding box, text content, image path, metadata)
- `ElementType`: Enumeration of supported element types
- `BoundingBox`: Coordinate system for element positioning
- JSON output stores all structured data for downstream processing

### Key Design Features

- **Modular architecture**: Clear separation of concerns, easy to maintain and extend
- **Hybrid analysis**: DocLayout-YOLO layout detection + Qwen VLM semantic enhancement for superior accuracy
- **Multiple fallback levels**: Graceful degradation when VLM/API services are unavailable
- **Background strategy**: Original image as background + masked elements + element reinsertion preserves visual fidelity
- **Meaningful filenames**: Element files generated as `{idx}_{type}_{keyword}` for easier debugging
- **Configurable**: Supports various aspect ratios, processing parameters via `PipelineConfig`
- **End-to-end workflow**: From screenshot to animated presentation with narration - complete pipeline in one tool

## Output Structure

```
output/
└── <slide_name>/
    ├── <slide_id>.json           # Metadata JSON
    ├── elements/                 # Extracted element images
    │   ├── 00_text_title.png
    │   ├── 01_chart_sales.png
    │   └── ...
    ├── original_<name>.png      # Original image copy
    ├── masked_background.png    # Masked background (if used)
    └── <name>_reconstructed.pptx # Reconstructed PPTX

tts_output/
├── audio_info.json              # Audio timing information
├── animation_scheme.json        # LLM-generated synchronized animation scheme
├── segment_00.wav              # Individual audio segments
├── segment_01.wav
└── ...
```

## Element Types

- `text` - Pure text region
- `title` - Slide title
- `subtitle` - Slide subtitle
- `header` - Page header
- `footer` - Page footer
- `image` - Photograph/illustration
- `chart` - Bar, line, pie chart etc.
- `table` - Tabular data
- `diagram` - Flowchart/diagram
- `list` - Bullet/numbered list
- `equation` - Mathematical formula
- `logo` - Logo/icon
- `decoration` - Decorative element
- `mixed` - Mixed content type

## Notes

- API keys for Qwen/DashScope are configured in `key_manage.py` (not committed to git)
- Tesseract path is auto-detected: `/opt/homebrew/bin/tesseract`, `/usr/local/bin/tesseract`, `/usr/bin/tesseract`
- Default slide size: 16:9 (13.333" × 7.5") which matches most modern presentations
- DocLayout-YOLO models are automatically downloaded on first run
