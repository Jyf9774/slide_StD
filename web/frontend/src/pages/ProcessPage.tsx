import { useState, useEffect, useCallback, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { api, uploadFile, formatFileSize } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Upload,
  Settings2,
  Loader2,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Sparkles,
  Terminal,
} from "lucide-react"

interface UploadedFile {
  filename: string
  path: string
  size: number
  source?: string
}

interface LogEntry {
  time: string
  msg: string
}

interface TaskState {
  id: string
  status: string
  step: string
  progress: number
  result: { slide_name: string } | null
  error: string | null
  logs?: LogEntry[]
}

interface ProcessConfig {
  use_vlm: boolean
  hybrid_mode: boolean
  min_area: number
  use_original_bg: boolean
  mask_elements: boolean
}

interface NarrateConfig {
  language: string
  style: string
}

interface TTSConfig {
  voice: string
  use_llm_animation: boolean
}

const STEPS = [
  { key: "upload", label: "Select Slide" },
  { key: "config", label: "Configure" },
  { key: "process", label: "Process" },
]

export function ProcessPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)

  // File state
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  // Config state
  const [processConfig, setProcessConfig] = useState<ProcessConfig>({
    use_vlm: true,
    hybrid_mode: true,
    min_area: 300,
    use_original_bg: true,
    mask_elements: true,
  })
  const [narrateConfig, setNarrateConfig] = useState<NarrateConfig>({
    language: "zh",
    style: "formal",
  })
  const [ttsConfig, setTTSConfig] = useState<TTSConfig>({
    voice: "Cherry",
    use_llm_animation: true,
  })
  const [runNarration, setRunNarration] = useState(true)
  const [runTTS, setRunTTS] = useState(true)

  // Task state
  const [task, setTask] = useState<TaskState | null>(null)
  const [currentPhase, setCurrentPhase] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [allLogs, setAllLogs] = useState<LogEntry[]>([])

  // Load available files
  useEffect(() => {
    api<UploadedFile[]>("/api/uploads").then(setFiles).catch(console.error)
  }, [])

  // Upload handler
  const handleUpload = useCallback(
    async (fileList: FileList) => {
      for (const file of Array.from(fileList)) {
        try {
          const result = await uploadFile(file)
          setFiles((prev) => [
            ...prev.filter((f) => f.filename !== result.filename),
            result,
          ])
          setSelectedFile(result.filename)
        } catch (e) {
          setError(e instanceof Error ? e.message : "Upload failed")
        }
      }
    },
    []
  )

  // Accumulate logs from task polling
  const seenLogCount = useRef(0)
  function collectLogs(state: TaskState) {
    const taskLogs = state.logs || []
    if (taskLogs.length > seenLogCount.current) {
      // New log entries appended
      const newEntries = taskLogs.slice(seenLogCount.current)
      seenLogCount.current = taskLogs.length
      setAllLogs((prev) => [...prev, ...newEntries])
    } else if (taskLogs.length > 0 && taskLogs.length === seenLogCount.current) {
      // Backend may have replaced the last spinner entry in-place (count unchanged)
      const lastEntry = taskLogs[taskLogs.length - 1]
      setAllLogs((prev) => {
        if (prev.length > 0 && prev[prev.length - 1].msg !== lastEntry.msg) {
          return [...prev.slice(0, -1), lastEntry]
        }
        return prev
      })
    }
  }

  // Process pipeline
  async function startProcessing() {
    if (!selectedFile) return
    setStep(2)
    setError(null)
    setAllLogs([])
    seenLogCount.current = 0

    try {
      // Phase 1: Slide processing
      setCurrentPhase("Slide Processing")
      const { task_id } = await api<{ task_id: string }>(
        `/api/process?filename=${encodeURIComponent(selectedFile)}`,
        {
          method: "POST",
          body: JSON.stringify(processConfig),
        }
      )

      const result = await pollTask(task_id)
      if (!result?.result?.slide_name) throw new Error("Processing failed")

      const slideName = result.result.slide_name

      // Phase 2: Narration
      if (runNarration) {
        setCurrentPhase("Narration Generation")
        seenLogCount.current = 0
        const { task_id: narrId } = await api<{ task_id: string }>(
          `/api/narrate/${slideName}`,
          {
            method: "POST",
            body: JSON.stringify(narrateConfig),
          }
        )
        await pollTask(narrId)
      }

      // Phase 3: TTS + Animation
      if (runNarration && runTTS) {
        setCurrentPhase("TTS & Animation")
        seenLogCount.current = 0
        const { task_id: ttsId } = await api<{ task_id: string }>(
          `/api/tts/${slideName}`,
          {
            method: "POST",
            body: JSON.stringify(ttsConfig),
          }
        )
        await pollTask(ttsId)
      }

      // Done!
      setCurrentPhase("Complete")
      setTimeout(() => navigate(`/result/${slideName}`), 1500)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing failed")
    }
  }

  async function pollTask(taskId: string): Promise<TaskState> {
    while (true) {
      const state = await api<TaskState>(`/api/tasks/${taskId}`)
      setTask(state)
      collectLogs(state)
      if (state.status === "completed") return state
      if (state.status === "failed") throw new Error(state.error || "Task failed")
      await new Promise((r) => setTimeout(r, 1500))
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 animate-fade-in">
      {/* Stepper */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <button
              onClick={() => i < step && step !== 2 ? setStep(i) : undefined}
              className={cn(
                "flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                i === step
                  ? "gradient-primary text-primary-foreground"
                  : i < step
                  ? "bg-success/20 text-success"
                  : "bg-muted text-muted-foreground"
              )}
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-background/20 text-[10px]">
                {i < step ? <CheckCircle2 className="h-3 w-3" /> : i + 1}
              </span>
              {s.label}
            </button>
            {i < STEPS.length - 1 && (
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      {step === 0 && (
        <FileSelectStep
          files={files}
          selectedFile={selectedFile}
          onSelect={setSelectedFile}
          onUpload={handleUpload}
          dragging={dragging}
          setDragging={setDragging}
          onNext={() => setStep(1)}
        />
      )}

      {step === 1 && (
        <ConfigStep
          processConfig={processConfig}
          setProcessConfig={setProcessConfig}
          narrateConfig={narrateConfig}
          setNarrateConfig={setNarrateConfig}
          ttsConfig={ttsConfig}
          setTTSConfig={setTTSConfig}
          runNarration={runNarration}
          setRunNarration={setRunNarration}
          runTTS={runTTS}
          setRunTTS={setRunTTS}
          onBack={() => setStep(0)}
          onStart={startProcessing}
        />
      )}

      {step === 2 && (
        <ProcessingStep
          task={task}
          phase={currentPhase}
          error={error}
          logs={allLogs}
        />
      )}
    </div>
  )
}

/* --- Sub-components --- */

function FileSelectStep({
  files,
  selectedFile,
  onSelect,
  onUpload,
  dragging,
  setDragging,
  onNext,
}: {
  files: UploadedFile[]
  selectedFile: string | null
  onSelect: (f: string) => void
  onUpload: (f: FileList) => void
  dragging: boolean
  setDragging: (d: boolean) => void
  onNext: () => void
}) {
  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <Card
        className={cn(
          "border-dashed transition-colors cursor-pointer",
          dragging && "border-primary bg-primary/5"
        )}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files.length) onUpload(e.dataTransfer.files)
        }}
        onClick={() => {
          const input = document.createElement("input")
          input.type = "file"
          input.accept = "image/*"
          input.multiple = true
          input.onchange = () => input.files && onUpload(input.files)
          input.click()
        }}
      >
        <CardContent className="flex flex-col items-center justify-center py-12">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Upload className="h-5 w-5 text-primary" />
          </div>
          <p className="text-sm font-medium text-foreground">
            Drop slide screenshots here
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            PNG, JPG, BMP, WebP supported
          </p>
        </CardContent>
      </Card>

      {/* File list with previews */}
      {files.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Available Images</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {files.map((f) => (
              <button
                key={f.filename}
                onClick={(e) => { e.stopPropagation(); onSelect(f.filename) }}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition-all",
                  selectedFile === f.filename
                    ? "bg-primary/10 text-primary ring-1 ring-primary/20"
                    : "hover:bg-accent text-foreground"
                )}
              >
                {/* Thumbnail */}
                <div className="h-10 w-16 shrink-0 overflow-hidden rounded-md bg-muted">
                  <img
                    src={`/api/preview/${encodeURIComponent(f.filename)}`}
                    alt={f.filename}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="truncate text-xs font-medium">{f.filename}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {formatFileSize(f.size)}
                  </p>
                </div>
                {f.source === "project" && (
                  <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                    project
                  </span>
                )}
              </button>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Selected preview */}
      {selectedFile && (
        <Card className="overflow-hidden">
          <div className="relative aspect-video bg-muted">
            <img
              src={`/api/preview/${encodeURIComponent(selectedFile)}`}
              alt={selectedFile}
              className="h-full w-full object-contain"
            />
          </div>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground">
              Selected: <span className="font-medium text-foreground">{selectedFile}</span>
            </p>
          </CardContent>
        </Card>
      )}

      <div className="flex justify-end">
        <Button onClick={onNext} disabled={!selectedFile}>
          Next: Configure
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function ConfigStep({
  processConfig,
  setProcessConfig,
  narrateConfig,
  setNarrateConfig,
  ttsConfig,
  setTTSConfig,
  runNarration,
  setRunNarration,
  runTTS,
  setRunTTS,
  onBack,
  onStart,
}: {
  processConfig: ProcessConfig
  setProcessConfig: React.Dispatch<React.SetStateAction<ProcessConfig>>
  narrateConfig: NarrateConfig
  setNarrateConfig: React.Dispatch<React.SetStateAction<NarrateConfig>>
  ttsConfig: TTSConfig
  setTTSConfig: React.Dispatch<React.SetStateAction<TTSConfig>>
  runNarration: boolean
  setRunNarration: (v: boolean) => void
  runTTS: boolean
  setRunTTS: (v: boolean) => void
  onBack: () => void
  onStart: () => void
}) {
  return (
    <div className="space-y-4">
      {/* Pipeline Config */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Settings2 className="h-4 w-4 text-primary" />
            Pipeline Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Toggle
              label="VLM Analysis"
              description="Use Qwen VLM for semantic understanding"
              checked={processConfig.use_vlm}
              onChange={(v) => setProcessConfig((c) => ({ ...c, use_vlm: v }))}
            />
            <Toggle
              label="Hybrid Mode"
              description="DocLayout-YOLO + VLM combined"
              checked={processConfig.hybrid_mode}
              onChange={(v) => setProcessConfig((c) => ({ ...c, hybrid_mode: v }))}
            />
            <Toggle
              label="Original Background"
              description="Use original image as slide background"
              checked={processConfig.use_original_bg}
              onChange={(v) => setProcessConfig((c) => ({ ...c, use_original_bg: v }))}
            />
            <Toggle
              label="Mask Elements"
              description="Mask element regions on background"
              checked={processConfig.mask_elements}
              onChange={(v) => setProcessConfig((c) => ({ ...c, mask_elements: v }))}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-foreground">
              Minimum Element Area (px)
            </label>
            <input
              type="range"
              min={50}
              max={2000}
              step={50}
              value={processConfig.min_area}
              onChange={(e) =>
                setProcessConfig((c) => ({ ...c, min_area: Number(e.target.value) }))
              }
              className="w-full accent-primary"
            />
            <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
              <span>50</span>
              <span className="font-medium text-foreground">{processConfig.min_area}</span>
              <span>2000</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Narration Config */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Narration Generation</CardTitle>
            <Toggle
              label=""
              checked={runNarration}
              onChange={setRunNarration}
              compact
            />
          </div>
        </CardHeader>
        {runNarration && (
          <CardContent className="space-y-3">
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Language"
                value={narrateConfig.language}
                onChange={(v) => setNarrateConfig((c) => ({ ...c, language: v }))}
                options={[
                  { value: "zh", label: "Chinese" },
                  { value: "en", label: "English" },
                ]}
              />
              <SelectField
                label="Style"
                value={narrateConfig.style}
                onChange={(v) => setNarrateConfig((c) => ({ ...c, style: v }))}
                options={[
                  { value: "formal", label: "Formal" },
                  { value: "casual", label: "Casual" },
                  { value: "academic", label: "Academic" },
                ]}
              />
            </div>
          </CardContent>
        )}
      </Card>

      {/* TTS Config */}
      {runNarration && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">TTS & Animation</CardTitle>
              <Toggle
                label=""
                checked={runTTS}
                onChange={setRunTTS}
                compact
              />
            </div>
          </CardHeader>
          {runTTS && (
            <CardContent className="space-y-3">
              <div className="grid gap-4 sm:grid-cols-2">
                <SelectField
                  label="Voice"
                  value={ttsConfig.voice}
                  onChange={(v) => setTTSConfig((c) => ({ ...c, voice: v }))}
                  options={[
                    { value: "Cherry", label: "Cherry / 芊悦 (阳光亲切女声)" },
                    { value: "Serena", label: "Serena / 苏瑶 (温柔女声)" },
                    { value: "Ethan", label: "Ethan / 晨煦 (阳光活力男声)" },
                  ]}
                />
                <Toggle
                  label="LLM Animation"
                  description="Use LLM to generate smart animation scheme"
                  checked={ttsConfig.use_llm_animation}
                  onChange={(v) => setTTSConfig((c) => ({ ...c, use_llm_animation: v }))}
                />
              </div>
            </CardContent>
          )}
        </Card>
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onStart}>
          <Sparkles className="h-4 w-4" />
          Start Processing
        </Button>
      </div>
    </div>
  )
}

function ProcessingStep({
  task,
  phase,
  error,
  logs,
}: {
  task: TaskState | null
  phase: string
  error: string | null
  logs: LogEntry[]
}) {
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs.length])

  const phases = [
    { key: "Slide Processing", label: "Slide Processing" },
    { key: "Narration Generation", label: "Narration" },
    { key: "TTS & Animation", label: "TTS & Animation" },
    { key: "Complete", label: "Complete" },
  ]

  const currentIdx = phases.findIndex((p) => p.key === phase)

  const phaseWeight = 100 / (phases.length - 1)
  const overallProgress =
    phase === "Complete"
      ? 100
      : Math.min(
          99,
          Math.round(
            currentIdx * phaseWeight +
              ((task?.progress || 0) / 100) * phaseWeight
          )
        )

  const stepLabels: Record<string, string> = {
    slide_processing: "Initializing pipeline...",
    layout_detection: "Running layout detection (DocLayout-YOLO)...",
    vlm_analysis: "VLM semantic analysis (Qwen)...",
    element_extraction: "Extracting slide elements...",
    reconstruction: "Reconstructing PPTX...",
    reconstruction_complete: "Reconstruction finished",
    narration_generation: "LLM generating narration...",
    tts_synthesis: "Synthesizing speech audio...",
    animation_generation: "Generating animation scheme...",
    done: "Completed",
  }

  return (
    <div className="space-y-4">
      {/* Phase indicators */}
      <div className="flex items-center gap-1">
        {phases.map((p, i) => (
          <div key={p.key} className="flex flex-1 items-center gap-1">
            <div
              className={cn(
                "flex flex-1 items-center gap-2 rounded-lg px-3 py-2.5 text-xs transition-all",
                i < currentIdx
                  ? "bg-success/10 text-success"
                  : i === currentIdx && phase !== "Complete"
                  ? "bg-primary/10 text-primary ring-1 ring-primary/20"
                  : phase === "Complete" && p.key === "Complete"
                  ? "bg-success/10 text-success"
                  : "bg-muted text-muted-foreground"
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold",
                  i < currentIdx
                    ? "bg-success text-success-foreground"
                    : i === currentIdx && phase !== "Complete"
                    ? "bg-primary text-primary-foreground"
                    : phase === "Complete" && p.key === "Complete"
                    ? "bg-success text-success-foreground"
                    : "bg-muted-foreground/20 text-muted-foreground"
                )}
              >
                {i < currentIdx || (phase === "Complete" && p.key === "Complete") ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  i + 1
                )}
              </span>
              <span className="font-medium hidden sm:inline">{p.label}</span>
            </div>
            {i < phases.length - 1 && (
              <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground/30" />
            )}
          </div>
        ))}
      </div>

      {/* Main status card */}
      <Card>
        <CardContent className="flex flex-col items-center py-12">
          {error ? (
            <>
              <XCircle className="mb-4 h-12 w-12 text-destructive" />
              <p className="mb-1 text-sm font-medium text-foreground">
                Processing Failed
              </p>
              <p className="text-xs text-destructive max-w-md text-center">
                {error}
              </p>
            </>
          ) : phase === "Complete" ? (
            <>
              <CheckCircle2 className="mb-4 h-12 w-12 text-success" />
              <p className="mb-1 text-sm font-medium text-foreground">
                Processing Complete!
              </p>
              <p className="text-xs text-muted-foreground">
                Redirecting to results...
              </p>
            </>
          ) : (
            <>
              <Loader2 className="mb-3 h-10 w-10 animate-spin text-primary" />
              <p className="mb-0.5 text-sm font-semibold text-foreground">{phase}</p>
              <p className="mb-5 text-xs text-muted-foreground">
                {stepLabels[task?.step || ""] || task?.step || "Initializing..."}
              </p>

              {/* Progress bar */}
              <div className="w-80 max-w-full">
                <div className="mb-1.5 flex justify-between text-[10px] text-muted-foreground">
                  <span>
                    Phase {currentIdx + 1}/{phases.length - 1}
                  </span>
                  <span className="font-medium text-foreground">
                    {overallProgress}%
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full progress-bar transition-all duration-700 ease-out"
                    style={{ width: `${overallProgress}%` }}
                  />
                </div>
                <p className="mt-2 text-center text-[10px] text-muted-foreground/70">
                  Current step: {task?.progress || 0}%
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Log output console */}
      {logs.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs text-muted-foreground">
              <Terminal className="h-3.5 w-3.5" />
              Backend Log
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-48 overflow-y-auto rounded-b-lg bg-muted/50 px-4 py-2 font-mono text-[11px] leading-relaxed">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-2">
                  <span className="shrink-0 text-muted-foreground/60">{log.time}</span>
                  <span className={cn(
                    "text-foreground/80",
                    log.msg.startsWith("ERROR") && "text-destructive"
                  )}>
                    {log.msg}
                  </span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

/* --- Primitives --- */

function Toggle({
  label,
  description,
  checked,
  onChange,
  compact,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (v: boolean) => void
  compact?: boolean
}) {
  return (
    <label className={cn("flex items-center gap-3", compact ? "" : "cursor-pointer")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors",
          checked ? "bg-primary" : "bg-muted-foreground/20"
        )}
      >
        <span
          className={cn(
            "inline-block h-3.5 w-3.5 rounded-full bg-background shadow-sm transition-transform",
            checked ? "translate-x-[18px]" : "translate-x-[3px]"
          )}
        />
      </button>
      {(label || description) && (
        <div className="flex-1">
          {label && <span className="text-xs font-medium text-foreground">{label}</span>}
          {description && (
            <p className="text-[10px] text-muted-foreground">{description}</p>
          )}
        </div>
      )}
    </label>
  )
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-foreground">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}
