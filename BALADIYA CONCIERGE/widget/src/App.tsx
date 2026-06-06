import { useEffect, useState } from "react";
import ChatWidget from "./components/ChatWidget";

interface WidgetConfig {
  greeting_en: string;
  greeting_ar: string;
  theme_color: string;
  logo_url: string;
}

function getTokenFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("token");
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const API_BASE: string =
  (import.meta as any).env?.VITE_API_BASE ??
  window.location.origin.replace(":5173", ":8000");

const MOCK_CONFIG = {
  greeting_en: "Hello! I'm the Municipal Assistant. How can I help you today?",
  greeting_ar: "مرحباً! أنا المساعد البلدي. كيف يمكنني مساعدتك؟",
  theme_color: "#1d4ed8",
  logo_url: "",
};

type AppState =
  | { kind: "loading" }
  | { kind: "ready"; config: WidgetConfig }
  | { kind: "expired" }
  | { kind: "error"; msg: string }
  | { kind: "no-token" };

export default function App() {
  const [token] = useState<string | null>(getTokenFromUrl);
  const [state, setState] = useState<AppState>(
    token === "preview" ? { kind: "ready", config: MOCK_CONFIG } : { kind: "loading" }
  );

  useEffect(() => {
    if (token === "preview") return;  // skip API in preview mode
    if (!token) { setState({ kind: "no-token" }); return; }

    fetch(`${API_BASE}/widget/config`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (r.status === 401) { setState({ kind: "expired" }); return null; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<WidgetConfig>;
      })
      .then((cfg) => {
        if (!cfg) return;
        // Inject theme color as CSS custom property
        if (cfg.theme_color) {
          document.documentElement.style.setProperty("--accent", cfg.theme_color);
          document.documentElement.style.setProperty(
            "--accent-dim",
            cfg.theme_color + "26"
          );
        }
        setState({ kind: "ready", config: cfg });
      })
      .catch(() => setState({ kind: "error", msg: "Unable to load widget." }));
  }, [token]);

  if (state.kind === "no-token" || state.kind === "error") {
    return (
      <div className="status-screen flex items-center justify-center h-full bg-[var(--surface)] p-6 text-center">
        <p className="text-[var(--text-muted)] text-sm max-w-[200px] leading-relaxed">
          {state.kind === "no-token" ? "Widget not initialized." : state.msg}
        </p>
      </div>
    );
  }

  if (state.kind === "expired") {
    return (
      <div className="status-screen flex flex-col items-center justify-center h-full bg-[var(--surface)] p-6 text-center gap-3">
        <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden>
          <circle cx="18" cy="18" r="16" stroke="var(--text-muted)" strokeWidth="1.5" />
          <path d="M18 10v9l5 3" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <p className="text-[var(--text-secondary)] text-sm max-w-[220px] leading-relaxed">
          Your session has expired. Reload the page to continue.
        </p>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <div className="flex items-center justify-center h-full bg-[var(--surface)]">
        <div className="w-5 h-5 border-2 border-[var(--border)] border-t-[var(--accent)] rounded-full"
          style={{ animation: "spin-slow 0.9s linear infinite" }} aria-label="Loading" />
      </div>
    );
  }

  return <ChatWidget token={token!} config={state.config} apiBase={API_BASE} />;
}
