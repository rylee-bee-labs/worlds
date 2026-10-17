import { usePrefs } from "./prefs-core";

/**
 * Station adds decoration only, in space that is always reserved so toggling it never shifts layout.
 * Everything here is aria-hidden: no landmark, name, order, function or fact changes with the pack.
 * The marks are placeholders; the protected character art is not used.
 */
export function StationDecor() {
  const { prefs } = usePrefs();
  const on = prefs.pack === "station";
  return (
    <div className="fd-decor" data-on={on ? "true" : "false"} aria-hidden="true">
      <span className="fd-decor-eyebrow">{on ? "Station · online" : " "}</span>
      <span className="fd-decor-mark">{on ? "✦" : " "}</span>
    </div>
  );
}
