import { useEffect, useState, useRef } from "react"
import { useParams, Link } from "react-router-dom"
import { api, formatDuration } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  ArrowLeft,
  Layers,
  FileText,
  Volume2,
  Play,
  Pause,
  Download,
  Clock,
  Zap,
  Eye,
  ChevronDown,
  ChevronUp,
} from "lucide-react"

interface SlideDetail {
  metadata: SlideMetadata
  narration: NarrationData | null
  animation: AnimationData | null
  audio_info: AudioInfo | null
  original_image: string | null
  pptx_url: string | null
}

interface SlideMetadata {
  slide_id: string
  title: string
  description: string
  width: number
  height: number
  background_color: string
  element_count: number
  elements: ElementData[]
  key_points?: string[]
  created_at: string
}

interface ElementData {
  id: string
  name: string
  type: string
  bbox: { x: number; y: number; width: number; height: number }
  image_url?: string
  text_content: string
  confidence: number
  is_title: boolean
  description: string
  z_order: number
}

interface NarrationData {
  opening: string
  closing: string
  segments: NarrationSegment[]
  total_duration: number
  language: string
  style: string
}

interface NarrationSegment {
  order: number
  element_name: string
  element_type: string
  narration_text: string
  duration_estimate: number
}

interface AnimationData {
  total_duration: number
  animations: AnimationItem[]
}

interface AnimationItem {
  element: string
  animation_type: string
  effect: string
  duration: number
  delay: number
  repeat_count: number
}

interface AudioInfo {
  total_duration: number
  full_audio_url?: string
  segments: AudioSegment[]
}

interface AudioSegment {
  order: number
  element_name: string
  element_type: string
  narration_text: string
  audio_url?: string
  duration: number
  start_time: number
}

type TabId = "elements" | "narration" | "animation" | "audio"

export function ResultPage() {
  const { slideName } = useParams<{ slideName: string }>()
  const [data, setData] = useState<SlideDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabId>("elements")
  const [selectedElement, setSelectedElement] = useState<string | null>(null)
  const [overlayVisible, setOverlayVisible] = useState(false)

  useEffect(() => {
    if (slideName) {
      api<SlideDetail>(`/api/slides/${slideName}`)
        .then((d) => {
          setData(d)
          // Default to best available tab
          if (d.audio_info) setActiveTab("audio")
          else if (d.narration) setActiveTab("narration")
        })
        .catch(console.error)
        .finally(() => setLoading(false))
    }
  }, [slideName])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="py-24 text-center text-sm text-muted-foreground">
        Slide not found.
      </div>
    )
  }

  const { metadata, narration, animation, audio_info } = data
  const tabs: { id: TabId; label: string; icon: React.ElementType; available: boolean }[] = [
    { id: "elements", label: "Elements", icon: Layers, available: true },
    { id: "narration", label: "Narration", icon: FileText, available: !!narration },
    { id: "animation", label: "Animation", icon: Zap, available: !!animation },
    { id: "audio", label: "Audio", icon: Volume2, available: !!audio_info },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Breadcrumb + Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-foreground">
              {metadata.title || slideName}
            </h1>
            <p className="text-xs text-muted-foreground">
              {metadata.element_count} elements &middot;{" "}
              {metadata.width}&times;{metadata.height}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {data.pptx_url && (
            <a href={data.pptx_url} download>
              <Button variant="outline" size="sm">
                <Download className="h-3.5 w-3.5" />
                PPTX
              </Button>
            </a>
          )}
        </div>
      </div>

      {/* Top section: Slide preview + Info */}
      <div className="grid gap-4 lg:grid-cols-5">
        {/* Slide preview */}
        <Card className="lg:col-span-3 overflow-hidden">
          <div className="relative">
            {data.original_image && (
              <div className="relative">
                <img
                  src={data.original_image}
                  alt={metadata.title}
                  className="w-full"
                />
                {/* Bounding box overlay */}
                {overlayVisible && (
                  <svg
                    className="absolute inset-0 h-full w-full"
                    viewBox={`0 0 ${metadata.width} ${metadata.height}`}
                    preserveAspectRatio="xMidYMid meet"
                  >
                    {metadata.elements.map((elem) => (
                      <g key={elem.id}>
                        <rect
                          x={elem.bbox.x}
                          y={elem.bbox.y}
                          width={elem.bbox.width}
                          height={elem.bbox.height}
                          fill="none"
                          stroke={selectedElement === elem.name ? "hsl(245,72%,65%)" : "hsl(152,55%,48%)"}
                          strokeWidth={selectedElement === elem.name ? 4 : 2}
                          strokeDasharray={selectedElement === elem.name ? "none" : "6,3"}
                          opacity={0.8}
                          rx={4}
                        />
                        <text
                          x={elem.bbox.x + 4}
                          y={elem.bbox.y - 4}
                          fill={selectedElement === elem.name ? "hsl(245,72%,65%)" : "hsl(152,55%,48%)"}
                          fontSize={Math.min(14, metadata.width * 0.012)}
                          fontWeight="600"
                        >
                          {elem.name}
                        </text>
                      </g>
                    ))}
                  </svg>
                )}
              </div>
            )}
            <button
              onClick={() => setOverlayVisible(!overlayVisible)}
              className="absolute bottom-3 right-3 flex items-center gap-1 rounded-md bg-card/90 px-2 py-1 text-[10px] font-medium text-foreground glass transition-colors hover:bg-card"
            >
              <Eye className="h-3 w-3" />
              {overlayVisible ? "Hide" : "Show"} Boxes
            </button>
          </div>
        </Card>

        {/* Info sidebar */}
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardContent className="p-4 space-y-3">
              <div>
                <p className="text-xs text-muted-foreground">Description</p>
                <p className="mt-1 text-sm text-foreground leading-relaxed">
                  {metadata.description || "No description available."}
                </p>
              </div>
              {metadata.key_points && metadata.key_points.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Key Points</p>
                  <ul className="space-y-1">
                    {metadata.key_points.map((kp, i) => (
                      <li key={i} className="flex gap-2 text-xs text-foreground">
                        <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-primary" />
                        <span className="leading-relaxed">{kp}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-2">
            <StatCard
              label="Elements"
              value={String(metadata.element_count)}
              icon={Layers}
            />
            <StatCard
              label="Background"
              value={metadata.background_color}
              icon={Eye}
              color={metadata.background_color}
            />
            {narration && (
              <StatCard
                label="Narration"
                value={formatDuration(narration.total_duration)}
                icon={Clock}
              />
            )}
            {audio_info && (
              <StatCard
                label="Audio"
                value={formatDuration(audio_info.total_duration)}
                icon={Volume2}
              />
            )}
          </div>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 rounded-lg bg-muted p-1">
        {tabs.filter(t => t.available).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <tab.icon className="h-3.5 w-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="animate-slide-in">
        {activeTab === "elements" && (
          <ElementsTab
            elements={metadata.elements}
            selectedElement={selectedElement}
            onSelect={setSelectedElement}
          />
        )}
        {activeTab === "narration" && narration && (
          <NarrationTab narration={narration} />
        )}
        {activeTab === "animation" && animation && (
          <AnimationTab animation={animation} />
        )}
        {activeTab === "audio" && audio_info && (
          <AudioTab audioInfo={audio_info} />
        )}
      </div>
    </div>
  )
}

/* --- Tab panels --- */

function ElementsTab({
  elements,
  selectedElement,
  onSelect,
}: {
  elements: ElementData[]
  selectedElement: string | null
  onSelect: (name: string | null) => void
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {elements.map((elem) => (
        <Card
          key={elem.id}
          className={cn(
            "cursor-pointer overflow-hidden transition-all hover:shadow-card-hover",
            selectedElement === elem.name && "ring-2 ring-primary"
          )}
          onClick={() =>
            onSelect(selectedElement === elem.name ? null : elem.name)
          }
        >
          {elem.image_url && (
            <div className="aspect-video bg-muted">
              <img
                src={elem.image_url}
                alt={elem.name}
                className="h-full w-full object-contain"
                loading="lazy"
              />
            </div>
          )}
          <CardContent className="p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-foreground">
                {elem.name}
              </span>
              <TypeBadge type={elem.type} />
            </div>
            {elem.description && (
              <p className="text-[11px] text-muted-foreground line-clamp-2">
                {elem.description}
              </p>
            )}
            {elem.text_content && (
              <p className="text-[10px] text-muted-foreground/70 line-clamp-2 font-mono">
                {elem.text_content}
              </p>
            )}
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span>Conf: {(elem.confidence * 100).toFixed(0)}%</span>
              <span>&middot;</span>
              <span>
                {elem.bbox.width}&times;{elem.bbox.height}
              </span>
              {elem.is_title && (
                <>
                  <span>&middot;</span>
                  <span className="text-primary font-medium">Title</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function NarrationTab({ narration }: { narration: NarrationData }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  return (
    <div className="space-y-3">
      {/* Opening */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-semibold uppercase text-primary tracking-wider">
              Opening
            </span>
          </div>
          <p className="text-sm text-foreground leading-relaxed">
            {narration.opening}
          </p>
        </CardContent>
      </Card>

      {/* Segments */}
      {narration.segments.map((seg, i) => (
        <Card key={i}>
          <button
            className="w-full p-4 text-left"
            onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                  {seg.order}
                </span>
                <span className="text-xs font-medium text-foreground">
                  {seg.element_name}
                </span>
                <TypeBadge type={seg.element_type} />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground">
                  ~{formatDuration(seg.duration_estimate)}
                </span>
                {expandedIdx === i ? (
                  <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </div>
            </div>
            {expandedIdx === i && (
              <p className="mt-3 text-sm text-foreground leading-relaxed border-t pt-3">
                {seg.narration_text}
              </p>
            )}
          </button>
        </Card>
      ))}

      {/* Closing */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-semibold uppercase text-primary tracking-wider">
              Closing
            </span>
          </div>
          <p className="text-sm text-foreground leading-relaxed">
            {narration.closing}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function AnimationBlock({ anim, left, width }: { anim: AnimationItem; left: number; width: number }) {
  const [hover, setHover] = useState(false)
  return (
    <div
      className={cn(
        "absolute top-1 h-6 rounded-sm flex items-center justify-center text-[8px] font-medium text-primary-foreground truncate px-1 cursor-default",
        anim.animation_type === "Entrance"
          ? "bg-success"
          : anim.animation_type === "Emphasis"
          ? "bg-info"
          : "bg-destructive"
      )}
      style={{ left: `${left}%`, width: `${width}%`, minWidth: "4px" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {width > 3 ? anim.effect : ""}
      {hover && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50 pointer-events-none">
          <div className="bg-popover text-popover-foreground border rounded-md shadow-md px-2.5 py-1.5 text-[10px] whitespace-nowrap space-y-0.5">
            <div className="font-semibold">{anim.element}</div>
            <div>{anim.effect} · {anim.animation_type}</div>
            <div className="text-muted-foreground">Duration: {anim.duration}s · Delay: {anim.delay.toFixed(1)}s</div>
          </div>
        </div>
      )}
    </div>
  )
}

function AnimationTab({ animation }: { animation: AnimationData }) {
  // Group animations by element
  const grouped = animation.animations.reduce(
    (acc, anim) => {
      if (!acc[anim.element]) acc[anim.element] = []
      acc[anim.element].push(anim)
      return acc
    },
    {} as Record<string, AnimationItem[]>
  )

  const maxTime = animation.total_duration

  return (
    <div className="space-y-4">
      {/* Timeline header */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Total Duration: {formatDuration(maxTime)}</span>
            <span>{animation.animations.length} animation steps</span>
          </div>
        </CardContent>
      </Card>

      {/* Timeline per element */}
      {Object.entries(grouped).map(([elemName, anims]) => (
        <Card key={elemName}>
          <CardContent className="p-4 space-y-2">
            <p className="text-xs font-semibold text-foreground">{elemName}</p>
            {/* Mini timeline */}
            <div className="relative h-8 rounded-md bg-muted overflow-hidden">
              {anims.map((anim, i) => {
                const left = (anim.delay / maxTime) * 100
                const width = Math.max((anim.duration / maxTime) * 100, 1)
                return <AnimationBlock key={i} anim={anim} left={left} width={width} />
              })}
            </div>
            {/* Animation list */}
            <div className="flex flex-wrap gap-1.5">
              {anims.map((anim, i) => (
                <span
                  key={i}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
                    anim.animation_type === "Entrance"
                      ? "bg-success/10 text-success"
                      : anim.animation_type === "Emphasis"
                      ? "bg-info/10 text-info"
                      : "bg-destructive/10 text-destructive"
                  )}
                >
                  {anim.effect}
                  <span className="opacity-60">@{anim.delay.toFixed(1)}s</span>
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-success" /> Entrance
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-info" /> Emphasis
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-destructive" /> Exit
        </span>
      </div>
    </div>
  )
}

function AudioTab({ audioInfo }: { audioInfo: AudioInfo }) {
  const [playing, setPlaying] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  function togglePlay(idx: number, url?: string) {
    if (!url || !audioRef.current) return
    if (playing === idx) {
      audioRef.current.pause()
      setPlaying(null)
    } else {
      audioRef.current.src = url
      audioRef.current.play()
      setPlaying(idx)
    }
  }

  return (
    <div className="space-y-3">
      <audio
        ref={audioRef}
        onEnded={() => setPlaying(null)}
        className="hidden"
      />

      {/* Full narration */}
      {audioInfo.full_audio_url && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Volume2 className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium text-foreground">
                  Full Narration
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatDuration(audioInfo.total_duration)}
                </span>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => togglePlay(-1, audioInfo.full_audio_url)}
              >
                {playing === -1 ? (
                  <Pause className="h-3.5 w-3.5" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                {playing === -1 ? "Pause" : "Play"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Segments */}
      {audioInfo.segments.map((seg, i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <button
                onClick={() => togglePlay(i, seg.audio_url)}
                disabled={!seg.audio_url}
                className={cn(
                  "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors",
                  seg.audio_url
                    ? playing === i
                      ? "gradient-primary text-primary-foreground"
                      : "bg-primary/10 text-primary hover:bg-primary/20"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {playing === i ? (
                  <Pause className="h-3.5 w-3.5" />
                ) : (
                  <Play className="h-3.5 w-3.5 ml-0.5" />
                )}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold text-foreground">
                    {seg.element_name}
                  </span>
                  <TypeBadge type={seg.element_type} />
                  <span className="ml-auto text-[10px] text-muted-foreground">
                    {formatDuration(seg.start_time)} - {formatDuration(seg.start_time + seg.duration)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {seg.narration_text}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

/* --- Shared --- */

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    text: "bg-info/10 text-info",
    title: "bg-primary/10 text-primary",
    image: "bg-success/10 text-success",
    chart: "bg-warning/10 text-warning",
    table: "bg-info/10 text-info",
    diagram: "bg-primary/10 text-primary",
    mixed: "bg-muted text-muted-foreground",
    narration: "bg-primary/10 text-primary",
  }
  return (
    <span
      className={cn(
        "rounded-full px-1.5 py-0.5 text-[9px] font-medium",
        colors[type] || "bg-muted text-muted-foreground"
      )}
    >
      {type}
    </span>
  )
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string
  value: string
  icon: React.ElementType
  color?: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground">{label}</p>
          <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
            {color && color.startsWith("#") && (
              <span
                className="inline-block h-3 w-3 rounded-sm border"
                style={{ backgroundColor: color }}
              />
            )}
            {value}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
