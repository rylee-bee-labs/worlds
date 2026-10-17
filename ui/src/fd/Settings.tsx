import { useEffect, useId, useState } from "react";
import { usePrefs } from "./prefs-core";
import { Notifications } from "./Notifications";
import { companionApi } from "./companion/api";
import { useCompanionOptional } from "./companion/companion-core";
import { companionStatus } from "./companion/companion-status";
import type { HealthView, Result } from "./companion/types";
import type { Density, Pack, TextSize, Theme, Words } from "./types";
import "./fd.css";

interface Option<T extends string> {
  value: T;
  label: string;
  /** One plain line about this choice. */
  hint: string;
}

const DENSITY_OPTIONS: Option<Density>[] = [
  { value: "calm", label: "Calm", hint: "What needs you first, quiet things folded away." },
  { value: "standard", label: "Standard", hint: "Everything in order." },
  { value: "detailed", label: "Detailed", hint: "Everything, with the technical details open." },
];

const WORDS_OPTIONS: Option<Words>[] = [
  { value: "minimal", label: "Minimal", hint: "Facts only: names, values and states." },
  { value: "short", label: "Short", hint: "A short meaning beside each fact." },
  { value: "full", label: "Full", hint: "Whole sentences, and when each thing last worked." },
];

const TEXT_OPTIONS: Option<TextSize>[] = [
  { value: "standard", label: "Standard", hint: "16px." },
  { value: "large", label: "Large", hint: "About 18px." },
  { value: "larger", label: "Larger", hint: "About 21px." },
];

const THEME_OPTIONS: Option<Theme>[] = [
  { value: "mulberry", label: "Mulberry & Mint", hint: "Plum and mint, the estate's look. The default." },
  { value: "starfield", label: "Starfield", hint: "Dark and warm." },
  { value: "daylight", label: "Daylight", hint: "Light." },
];

const PACK_OPTIONS: Option<Pack>[] = [
  { value: "none", label: "None", hint: "Nothing added." },
  { value: "station", label: "Station", hint: "Decoration only. It never changes what Worlds says or does." },
];

interface RadioGroupProps<T extends string> {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** One native radio group bound to prefs. The fieldset and legend name the group once; each option has its own line. */
function RadioGroup<T extends string>({ label, options, value, onChange }: RadioGroupProps<T>) {
  const name = useId();
  return (
    <fieldset className="fd-settings-group">
      <legend className="fd-settings-legend">{label}</legend>
      <div className="fd-radio-group">
        {options.map((option) => {
          const hintId = `${name}-${option.value}-hint`;
          return (
            <div key={option.value} className="fd-radio">
              <label className="fd-radio-label-wrap">
                <input type="radio" name={name} value={option.value} checked={value === option.value} aria-describedby={hintId} onChange={() => onChange(option.value)} />
                <span className="fd-radio-label">{option.label}</span>
              </label>
              <span id={hintId} className="fd-radio-hint">
                {option.hint}
              </span>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

/** The same health the panel reads, in one line, with the next step. One call on open, read-only: no thread,
 * context or grant is touched here, so Settings cannot show anyone's content or imply a permission it did not get.
 * Where the panel is mounted, the button opens that same panel — there is one Companion, not a second status. */
function CompanionStatus() {
  const companion = useCompanionOptional();
  const [result, setResult] = useState<Result<HealthView> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    void companionApi.health().then((r) => {
      if (live) {
        setResult(r);
        setLoading(false);
      }
    });
    return () => {
      live = false;
    };
  }, []);

  const status = companionStatus(result, loading);
  return (
    <>
      <p className="fd-settings-value" role="status">
        {status.line}
      </p>
      {status.next && <p className="fd-settings-note">{status.next}</p>}
      {companion && (
        <button type="button" className="fd-btn fd-btn--quiet" onClick={() => companion.setOpen(true)}>
          Open the Companion panel
        </button>
      )}
    </>
  );
}

/** Settings: comfort first, then the look, then the optional pack, then Companion. */
export function Settings() {
  const { prefs, set } = usePrefs();

  return (
    <div className="fd-screen">
      <h1 className="fd-screen-title">Settings</h1>

      <section className="fd-settings-section">
        <h2 className="fd-settings-section-title">Comfort</h2>
        <RadioGroup label="Density" options={DENSITY_OPTIONS} value={prefs.density} onChange={(density) => set({ density })} />
        <RadioGroup label="Words" options={WORDS_OPTIONS} value={prefs.words} onChange={(words) => set({ words })} />
        <RadioGroup label="Text size" options={TEXT_OPTIONS} value={prefs.text} onChange={(text) => set({ text })} />
        <p className="fd-settings-note">Motion follows your device setting.</p>
      </section>

      <section className="fd-settings-section">
        <h2 className="fd-settings-section-title">Look</h2>
        <RadioGroup label="Theme" options={THEME_OPTIONS} value={prefs.theme} onChange={(theme) => set({ theme })} />
      </section>

      <section className="fd-settings-section">
        <h2 className="fd-settings-section-title">Experience</h2>
        <RadioGroup label="Experience pack" options={PACK_OPTIONS} value={prefs.pack} onChange={(pack) => set({ pack })} />
      </section>

      <section className="fd-settings-section">
        <h2 className="fd-settings-section-title">Companion</h2>
        <p className="fd-settings-note">One Companion: the presence in the header. It reads only what you approve, and you approve in Project Home.</p>
        <CompanionStatus />
      </section>
      <Notifications />
    </div>
  );
}
