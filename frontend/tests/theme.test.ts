// Run with:  node --test tests/   (Node 22.18+/24 runs TypeScript directly, no extra packages)
import assert from "node:assert/strict"
import { test } from "node:test"
import { THEME_KEY, applyTheme, initialTheme, nextTheme, saveTheme, type KeyValueStore } from "../src/theme.ts"

function memoryStore(initial: Record<string, string> = {}): KeyValueStore & { data: Record<string, string> } {
  const data = { ...initial }
  return { data, getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v } }
}

const blocked: KeyValueStore = {
  getItem: () => { throw new Error("SecurityError") },
  setItem: () => { throw new Error("SecurityError") },
}

test("saved choice wins over the system setting (persists across reloads)", () => {
  assert.equal(initialTheme(memoryStore({ [THEME_KEY]: "dark" }), false), "dark")
  assert.equal(initialTheme(memoryStore({ [THEME_KEY]: "light" }), true), "light")
})

test("without a saved choice the system setting is used", () => {
  assert.equal(initialTheme(memoryStore(), true), "dark")
  assert.equal(initialTheme(memoryStore(), false), "light")
  assert.equal(initialTheme(null, false), "light")
})

test("garbage in storage is ignored", () => {
  assert.equal(initialTheme(memoryStore({ [THEME_KEY]: "purple" }), false), "light")
})

test("toggle switches between the two themes", () => {
  assert.equal(nextTheme("light"), "dark")
  assert.equal(nextTheme("dark"), "light")
})

test("save then reload gives the same theme", () => {
  const store = memoryStore()
  saveTheme(store, "dark")
  assert.equal(store.data[THEME_KEY], "dark")
  assert.equal(initialTheme(store, false), "dark")
})

test("blocked storage does not crash", () => {
  assert.doesNotThrow(() => saveTheme(blocked, "dark"))
  assert.equal(initialTheme(blocked, true), "dark")
})

test("applyTheme sets data-theme on the root element", () => {
  const root = { dataset: {} as Record<string, string | undefined> }
  applyTheme(root, "dark")
  assert.equal(root.dataset.theme, "dark")
})
