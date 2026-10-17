import { useCallback, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_PREFS, PrefsCtx, type Prefs } from "./prefs-core";
const KEY = "worlds.prefs.v2";

function load(): Prefs {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_PREFS;
    const stored = JSON.parse(raw) as Partial<Prefs> & { theme?: string };
    // Anything unknown (the removed Plain theme too) falls back to the default. A save from before
    // Mulberry & Mint (no themeV) said "starfield" only because Starfield was the default then.
    const known = stored.theme === "daylight" || stored.theme === "starfield" || stored.theme === "mulberry";
    const theme = !known || (stored.theme === "starfield" && stored.themeV !== 2) ? "mulberry" : (stored.theme as Prefs["theme"]);
    return { ...DEFAULT_PREFS, ...stored, theme, themeV: 2 };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function PrefsProvider({ children, initial }: { children: ReactNode; initial?: Partial<Prefs> }) {
  const [prefs, setPrefs] = useState<Prefs>(() => ({ ...load(), ...initial }));
  const set = useCallback((p: Partial<Prefs>) => {
    setPrefs((cur) => {
      const next = { ...cur, ...p };
      try { window.localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage unavailable: keep in memory */ }
      return next;
    });
  }, []);
  const value = useMemo(() => ({ prefs, set }), [prefs, set]);
  return <PrefsCtx.Provider value={value}>{children}</PrefsCtx.Provider>;
}
