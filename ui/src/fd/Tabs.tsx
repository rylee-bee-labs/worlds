import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export interface TabDef { id: string; label: string; panel: ReactNode }

/** Accessible tabs: roving tabindex, arrow/Home/End keys, one visible panel. */
export function Tabs({ label, tabs, initial }: { label: string; tabs: TabDef[]; initial?: string }) {
  const base = useId();
  const [active, setActive] = useState(initial ?? tabs[0].id);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const move = (to: number) => {
    const t = tabs[(to + tabs.length) % tabs.length];
    setActive(t.id);
    refs.current[t.id]?.focus();
  };
  const onKey = (e: KeyboardEvent, i: number) => {
    if (e.key === "ArrowRight") move(i + 1);
    else if (e.key === "ArrowLeft") move(i - 1);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(tabs.length - 1);
    else return;
    e.preventDefault();
  };
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  return (
    <div className="fd-tabs">
      <div role="tablist" aria-label={label} className="fd-tablist">
        {tabs.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => { refs.current[t.id] = el; }}
            role="tab"
            id={`${base}-tab-${t.id}`}
            aria-selected={t.id === current.id}
            aria-controls={`${base}-panel`}
            tabIndex={t.id === current.id ? 0 : -1}
            className="fd-tab"
            onClick={() => setActive(t.id)}
            onKeyDown={(e) => onKey(e, i)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${base}-panel`} aria-labelledby={`${base}-tab-${current.id}`} tabIndex={0} className="fd-tabpanel">
        {current.panel}
      </div>
    </div>
  );
}
