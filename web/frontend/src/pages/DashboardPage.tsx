import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Layers,
  FileText,
  Volume2,
  Play,
  ArrowRight,
  Sparkles,
  ImageIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface SlideInfo {
  name: string
  slide_id: string
  title: string
  description: string
  element_count: number
  width: number
  height: number
  background_color: string
  created_at: string
  has_narration: boolean
  has_animation: boolean
  has_tts: boolean
  has_pptx: boolean
  original_image: string | null
}

export function DashboardPage() {
  const [slides, setSlides] = useState<SlideInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<SlideInfo[]>("/api/slides")
      .then(setSlides)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading slides...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {slides.length} processed slides
          </p>
        </div>
        <Link to="/process">
          <Button>
            <Sparkles className="h-4 w-4" />
            Process New Slide
          </Button>
        </Link>
      </div>

      {/* Grid */}
      {slides.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <ImageIcon className="h-6 w-6 text-muted-foreground" />
            </div>
            <p className="mb-1 text-sm font-medium text-foreground">
              No slides processed yet
            </p>
            <p className="mb-4 text-xs text-muted-foreground">
              Upload a slide screenshot to get started
            </p>
            <Link to="/process">
              <Button size="sm">Get Started</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {slides.map((slide) => (
            <SlideCard key={slide.name} slide={slide} />
          ))}
        </div>
      )}
    </div>
  )
}

function SlideCard({ slide }: { slide: SlideInfo }) {
  return (
    <Link to={`/result/${slide.name}`}>
      <Card className="group cursor-pointer overflow-hidden hover:shadow-card-hover hover:border-primary/30 transition-all duration-300">
        {/* Thumbnail */}
        <div className="relative aspect-video overflow-hidden bg-muted">
          {slide.original_image ? (
            <img
              src={slide.original_image}
              alt={slide.title}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <Layers className="h-8 w-8 text-muted-foreground/40" />
            </div>
          )}
          {/* Badge overlay */}
          <div className="absolute bottom-2 right-2 flex gap-1">
            {slide.has_pptx && (
              <StatusBadge icon={FileText} label="PPTX" active />
            )}
            {slide.has_tts && (
              <StatusBadge icon={Volume2} label="TTS" active />
            )}
            {slide.has_animation && (
              <StatusBadge icon={Play} label="Anim" active />
            )}
          </div>
        </div>

        <CardContent className="p-4">
          <h3 className="mb-1 text-sm font-semibold text-foreground line-clamp-1">
            {slide.title || slide.name}
          </h3>
          <p className="mb-3 text-xs text-muted-foreground line-clamp-2">
            {slide.description || `${slide.element_count} elements detected`}
          </p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Layers className="h-3 w-3" />
              <span>{slide.element_count} elements</span>
            </div>
            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function StatusBadge({
  icon: Icon,
  label,
  active,
}: {
  icon: React.ElementType
  label: string
  active: boolean
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium glass",
        active
          ? "bg-primary/80 text-primary-foreground"
          : "bg-muted/80 text-muted-foreground"
      )}
    >
      <Icon className="h-2.5 w-2.5" />
      {label}
    </div>
  )
}
