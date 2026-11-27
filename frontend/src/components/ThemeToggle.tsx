import { useState } from "react"
import { type Theme, applyTheme, initialTheme, nextTheme, saveTheme } from "../theme"

function browserStore() {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme
  if (set === "light" || set === "dark") return set
  return initialTheme(browserStore(), window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false)
}

/** Button that switches light/dark mode for every page and remembers the choice. */
export function ThemeToggle({ floating = false }: { floating?: boolean }) {
  const [theme, setTheme] = useState<Theme>(currentTheme)

  function toggle() {
    const next = nextTheme(theme)
    applyTheme(document.documentElement, next)
    saveTheme(browserStore(), next)
    setTheme(next)
  }

  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
  return (
    <button type="button" className={`theme-toggle${floating ? " theme-toggle-floating" : ""}`}
      onClick={toggle} aria-label={label} title={label}>
      {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
    </button>
  )
}
