// Light / dark theme. The choice is saved in localStorage so it survives reloads;
// until the user chooses, the operating system setting (prefers-color-scheme) is used.
// The CSS only swaps colour variables: :root[data-theme="dark"] in index.css.
// index.html runs the same logic before React starts, so the page never flashes white.

export type Theme = "light" | "dark"

export const THEME_KEY = "printpoint-theme"

/** Minimal part of localStorage we use (lets tests pass a fake one). */
export interface KeyValueStore {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

export function initialTheme(store: KeyValueStore | null, systemPrefersDark: boolean): Theme {
  let saved: string | null = null
  try {
    saved = store?.getItem(THEME_KEY) ?? null
  } catch {
    saved = null // storage blocked (private mode) - fall back to the system setting
  }
  if (saved === "light" || saved === "dark") return saved
  return systemPrefersDark ? "dark" : "light"
}

export function nextTheme(theme: Theme): Theme {
  return theme === "dark" ? "light" : "dark"
}

export function saveTheme(store: KeyValueStore | null, theme: Theme): void {
  try {
    store?.setItem(THEME_KEY, theme)
  } catch {
    // not saved, but the theme still changes for this visit
  }
}

export function applyTheme(root: { dataset: Record<string, string | undefined> }, theme: Theme): void {
  root.dataset.theme = theme
}
