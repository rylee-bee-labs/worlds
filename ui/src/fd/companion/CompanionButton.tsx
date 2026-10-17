import { useCompanion } from "./companion-core";
import { poseFor } from "./presentation";
import { PaintedIcon, companionArt } from "../PaintedIcon";
import { usePrefs } from "../prefs-core";
import "../fd.css";

/** A quiet button in the header or rail. Its mark is the presence mark: static, decorative, never the only signal. */
export function CompanionButton() {
  const { setOpen, presentation } = useCompanion();
  const pose = poseFor(presentation);
  const { prefs } = usePrefs();
  const station = prefs.pack === "station";
  return (
    <button type="button" className="fd-companion-btn" aria-haspopup="dialog" onClick={() => setOpen(true)}>
      <span className="fd-companion-mark" aria-hidden="true">
        {station ? <PaintedIcon name={companionArt(presentation.state, presentation.tone)} size={32} className="fd-companion-art" /> : pose.mark}
      </span>
      <span>Companion</span>
      <span className="fd-sr">, {pose.word}</span>
    </button>
  );
}
