import { Outlet, NavLink } from "react-router-dom"
import { LayoutDashboard, Sparkles, Sun, Moon } from "lucide-react"
import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"

function getSystemDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
}

export function Layout() {
  const [dark, setDark] = useState(getSystemDark)

  // Sync <html> class on mount & whenever dark changes
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
  }, [dark])

  // Listen for OS theme changes
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const handler = (e: MediaQueryListEvent) => setDark(e.matches)
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  function toggleTheme() {
    setDark((d) => !d)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-card/80 glass">
        <div className="mx-auto flex h-14 max-w-screen-2xl items-center justify-between px-6">
          <div className="flex items-center gap-6">
            <NavLink to="/" className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
                <Sparkles className="h-4 w-4 text-primary-foreground" />
              </div>
              <span className="text-sm font-semibold tracking-tight text-foreground">
                StD Pipeline
              </span>
            </NavLink>

            <nav className="flex items-center gap-1">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
                    isActive
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                  )
                }
              >
                <LayoutDashboard className="h-3.5 w-3.5" />
                Dashboard
              </NavLink>
              <NavLink
                to="/process"
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
                    isActive
                      ? "bg-accent text-accent-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                  )
                }
              >
                <Sparkles className="h-3.5 w-3.5" />
                Process
              </NavLink>
            </nav>
          </div>

          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-screen-2xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  )
}
