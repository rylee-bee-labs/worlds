import type { Meter as MeterData } from "./types";
import "./fd.css";

export interface MeterProps {
  meter: MeterData | null;
  frozen: boolean;
}

const MARKS_SHOWN = 6;

const clamp01 = (n: number) => Math.max(0, Math.min(1, n));

/** Parse "09:00 Walk" into a position along the day and a label. Items that do not parse are not drawn. */
function dayEvents(items: (number | string | boolean)[]): { at: number; clock: string; label: string }[] {
  const out: { at: number; clock: string; label: string }[] = [];
  for (const it of items) {
    const m = typeof it === "string" ? it.match(/^(\d{1,2}):(\d{2})\s*(.*)$/) : null;
    if (m && Number(m[1]) <= 23 && Number(m[2]) <= 59) out.push({ at: clamp01((Number(m[1]) * 60 + Number(m[2])) / 1440), clock: `${m[1].padStart(2, "0")}:${m[2]}`, label: m[3] });
  }
  return out;
}

/**
 * The drawing for a meter, or null when the data to draw it is missing: never invent progress. The
 * text equivalent still names the whole meter for assistive tech.
 */
function body(m: MeterData): React.JSX.Element | null {
  switch (m.type) {
    case "progress": {
      if (typeof m.value !== "number" || typeof m.max !== "number" || m.max <= 0) return null;
      return (
        <span className="fd-track">
          <span className="fd-fill" style={{ width: `${clamp01(m.value / m.max) * 100}%` }} />
        </span>
      );
    }
    case "segments": {
      if (typeof m.count !== "number" || typeof m.filled !== "number" || m.count <= 0) return null;
      return (
        <span className="fd-seg">
          {Array.from({ length: m.count }, (_, i) => (
            <i key={i} className={i < m.filled! ? "on" : "off"} />
          ))}
        </span>
      );
    }
    case "bars": {
      if (!Array.isArray(m.items)) return null;
      const nums = m.items.filter((x): x is number => typeof x === "number");
      const max = Math.max(1, ...nums);
      return (
        <span className="fd-bars">
          {nums.map((n, i) => (
            <i key={i} style={{ height: `${(n / max) * 100}%` }} />
          ))}
        </span>
      );
    }
    case "dots": {
      if (!Array.isArray(m.items)) return null;
      return (
        <span className="fd-dots">
          {m.items.map((x, i) => (
            <i key={i} className={x === true || (typeof x === "number" && x > 0) ? "on" : ""} />
          ))}
        </span>
      );
    }
    case "marks": {
      if (!Array.isArray(m.items)) return null;
      const more = m.items.length - MARKS_SHOWN;
      return (
        <span className="fd-marks">
          {m.items.slice(0, MARKS_SHOWN).map((x, i) => (
            <span key={i} className="fd-mk on">
              {String(x)}
            </span>
          ))}
          {more > 0 && <span className="fd-mk">{`+${more} more`}</span>}
        </span>
      );
    }
    case "day": {
      if (!Array.isArray(m.items)) return null;
      const ev = dayEvents(m.items);
      return (
        <span className="fd-day">
          <span className="fd-day-track">
            {ev.map((e, i) => (
              <span key={i} className="fd-day-dot" style={{ left: `${e.at * 100}%` }} />
            ))}
          </span>
          <span className="fd-day-labels">
            {ev.map((e, i) => (
              <span key={i} className="fd-day-label">
                <span className="fd-day-clock">{e.clock}</span> {e.label}
              </span>
            ))}
          </span>
        </span>
      );
    }
    case "shelf": {
      if (!Array.isArray(m.items)) return null;
      return (
        <span className="fd-shelf">
          {m.items.map((x, i) => (
            <span key={i} className="fd-spine">
              {String(x)}
            </span>
          ))}
        </span>
      );
    }
    default:
      return null;
  }
}

/**
 * One visual meter. A single image to assistive tech named by the text equivalent; the drawn marks
 * are presentational and never animate. Frozen draws the striped last-good treatment. A meter with no
 * data to draw renders nothing.
 */
export function Meter({ meter, frozen }: MeterProps) {
  if (!meter) return null;
  const drawn = body(meter);
  if (!drawn) return null;
  return (
    <span
      className={`fd-meter fd-meter--${meter.type}${frozen ? " fd-meter--frozen" : ""}`}
      role="img"
      aria-label={meter.text_equivalent}
      data-frozen={frozen ? "true" : undefined}
    >
      {drawn}
    </span>
  );
}
