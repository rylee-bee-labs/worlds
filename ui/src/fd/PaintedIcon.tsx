import { usePrefs } from "./prefs-core";

/**
 * A painted icon from the design-system B Classic sticker set (copies in public/assets/painted/, see its README).
 * Station-only decoration: with the pack off it renders nothing, so the plain front door is unchanged. Always beside
 * a word that carries the meaning, so the image is alt="" and aria-hidden. Still image; nothing animates.
 */
export function PaintedIcon({ name, size = 24, className }: { name: string; size?: number; className?: string }) {
  const { prefs } = usePrefs();
  if (prefs.pack !== "station") return null;
  const file = `${import.meta.env.BASE_URL}assets/painted/${name}-${size > 32 ? 128 : 64}.webp`;
  return (
    <img
      className={["fd-painted", className].filter(Boolean).join(" ")}
      src={file}
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      decoding="async"
    />
  );
}

/** Painted picture per landmark, from the design-system vocabulary (action-*). */
export const LANDMARK_ICON: Record<string, string> = {
  home: "action-home",
  connect: "action-pinned",
  memory: "action-files",
  settings: "action-settings",
};

/** Painted picture per row icon key, where the set has a clear match. Others keep their text glyph. */
export const ROW_ICON: Record<string, string> = {
  book: "object-books",
  calendar: "action-calendar",
};

/** Companion presence: Renai. Presence only; the pose word is always read out beside it. */
export function companionArt(state: string, tone: string): string {
  return state === "engaged" || tone === "warm" || tone === "good_news" ? "crew-renai-wink" : "crew-renai-hello";
}
