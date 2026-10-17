export type Landmark = "home" | "connect" | "memory" | "settings";
export const LANDMARKS: { id: Landmark; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "connect", label: "Connect" },
  { id: "memory", label: "Memory" },
  { id: "settings", label: "Settings" },
];

/** "#connect" → "connect". Anything unknown, including the removed area ids, falls back to home. */
export function parseHash(hash: string): Landmark {
  const slug = decodeURIComponent(hash.replace(/^#\/?/, "")).trim().toLowerCase().split(/[/?]/)[0];
  return LANDMARKS.some((l) => l.id === slug) ? (slug as Landmark) : "home";
}
export const hashFor = (l: Landmark): string => `#${l}`;
