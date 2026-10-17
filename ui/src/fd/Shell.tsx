import { useLayoutEffect, useRef, type MouseEvent, type ReactNode } from "react";
import { LANDMARKS, hashFor, type Landmark } from "./route";
import { LANDMARK_ICON, PaintedIcon } from "./PaintedIcon";
import "./fd.css";

export interface ShellProps {
  current: Landmark;
  onNavigate: (l: Landmark) => void;
  boards: { id: string; title: string }[];
  /** A quiet control in the header/rail (e.g. the Companion button). Not a landmark. */
  headerExtra?: ReactNode;
  children: ReactNode;
}

export function Shell({ current, onNavigate, boards, headerExtra, children }: ShellProps) {
  const handleLandmarkClick =
    (landmark: Landmark) => (event: MouseEvent<HTMLAnchorElement>) => {
      // Only a plain left click is intercepted; modified clicks keep
      // their native behaviour (new tab, download, and so on).
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      event.preventDefault();
      onNavigate(landmark);
    };

  // The rail's nav sticks just below the header, whatever height the header has (the Companion button can wrap at big text).
  const headerRef = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const el = headerRef.current;
    if (!el) return;
    const set = () => document.documentElement.style.setProperty("--fd-header-h", `${el.getBoundingClientRect().height}px`);
    set();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <>
      <a className="fd-skip" href="#main">
        Skip to main content
      </a>
      <header className="fd-header" ref={headerRef}>
        <span className="fd-header-brand">Worlds</span>
        {headerExtra}
      </header>
      <nav className="fd-nav" aria-label="Main">
        <ul className="fd-nav-landmarks">
          {LANDMARKS.map((landmark) => (
            <li key={landmark.id}>
              <a
                href={hashFor(landmark.id)}
                aria-current={landmark.id === current ? "page" : undefined}
                onClick={handleLandmarkClick(landmark.id)}
              >
                <PaintedIcon name={LANDMARK_ICON[landmark.id]} size={24} className="fd-nav-painted" />
                {landmark.label}
              </a>
            </li>
          ))}
        </ul>
        <ul className="fd-nav-boards">
          {boards.map((board) => (
            <li key={board.id}>
              <a href={`#board/${board.id}`}>{board.title}</a>
            </li>
          ))}
        </ul>
      </nav>
      <main className="fd-main" id="main" tabIndex={-1}>
        {children}
      </main>
    </>
  );
}
