import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { FdApp } from "./fd/FdApp";
import { PrefsProvider } from "./fd/prefs";
import { QueryProvider } from "./app/QueryProvider";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryProvider>
      <PrefsProvider>
        <FdApp />
      </PrefsProvider>
    </QueryProvider>
  </StrictMode>,
);
