import { createContext, useContext } from "react";
import type { Density, Pack, TextSize, Theme, Words } from "./types";

export interface Prefs { words: Words; density: Density; pack: Pack; theme: Theme; text: TextSize; name?: string; /** 2 once Mulberry & Mint is the default; older saves said "starfield" only because it was the default. */ themeV?: number }
export const DEFAULT_PREFS: Prefs = { words: "short", density: "standard", pack: "none", theme: "mulberry", text: "standard", themeV: 2 };
export const PrefsCtx = createContext<{ prefs: Prefs; set: (p: Partial<Prefs>) => void }>({ prefs: DEFAULT_PREFS, set: () => undefined });
export const usePrefs = () => useContext(PrefsCtx);
