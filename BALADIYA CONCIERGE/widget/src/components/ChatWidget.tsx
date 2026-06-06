import React, { useRef, useState, useEffect } from "react";
import MessageList from "./MessageList";
import LangToggle from "./LangToggle";
import { useChat } from "../hooks/useChat";

interface WidgetConfig {
  greeting_en: string;
  greeting_ar: string;
  theme_color: string;
  logo_url: string;
}

interface Props {
  token: string;
  config: WidgetConfig;
  apiBase: string;
}

export default function ChatWidget({ token, config, apiBase }: Props) {
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { turns, sending, sessionExpired, send } = useChat(token, apiBase);

  const isRtl = lang === "ar";
  const greeting =
    lang === "ar" && config.greeting_ar ? config.greeting_ar : config.greeting_en;

  // Focus input on mount
  useEffect(() => { inputRef.current?.focus(); }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const msg = input.trim();
    if (!msg || sending || sessionExpired) return;
    setInput("");
    send(msg, lang);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  if (sessionExpired) {
    return (
      <div
        className="widget-root flex flex-col items-center justify-center h-full bg-[var(--surface)] p-6 text-center gap-4"
        dir={isRtl ? "rtl" : "ltr"}
        role="alert"
      >
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden>
          <circle cx="20" cy="20" r="18" stroke="var(--text-muted)" strokeWidth="1.5" />
          <path d="M20 11v10l6 3.5" stroke="var(--text-muted)" strokeWidth="1.5"
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p className="text-[var(--text-secondary)] text-sm leading-relaxed max-w-[200px]"
          style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
          {isRtl
            ? "انتهت جلستك. يرجى إعادة تحميل الصفحة."
            : "Your session has expired. Please reload the page to continue."}
        </p>
      </div>
    );
  }

  return (
    <div
      className="widget-root flex flex-col h-full overflow-hidden"
      dir={isRtl ? "rtl" : "ltr"}
      lang={lang}
    >
      {/* ── Header ─────────────────────────────────────────── */}
      <header
        className="header-pattern flex-shrink-0 flex items-center justify-between px-4 py-3"
        role="banner"
        aria-label="Municipal Assistant"
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* Avatar / logo */}
          <div
            className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center overflow-hidden"
            style={{
              background: "rgba(255,255,255,0.12)",
              border: "1.5px solid rgba(255,255,255,0.18)",
            }}
            aria-hidden
          >
            {config.logo_url ? (
              <img
                src={config.logo_url}
                alt=""
                className="w-full h-full object-cover"
              />
            ) : (
              <CivicIcon />
            )}
          </div>

          {/* Title block */}
          <div className="min-w-0">
            <p
              className="text-white text-[13px] font-semibold leading-tight truncate"
              style={{ fontFamily: "'Syne', system-ui, sans-serif", letterSpacing: "0.01em" }}
            >
              {isRtl ? "المساعد البلدي" : "Municipal Assistant"}
            </p>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" aria-hidden />
              <span className="text-white/50 text-[10px] tracking-wide uppercase"
                style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
                {isRtl ? "متاح" : "Online"}
              </span>
            </div>
          </div>
        </div>

        <LangToggle lang={lang} onToggle={setLang} />
      </header>

      {/* ── Messages ───────────────────────────────────────── */}
      <main
        className="flex-1 overflow-hidden"
        id="chat-messages"
        aria-label="Conversation"
        aria-live="polite"
        aria-atomic={false}
      >
        <MessageList
          greeting={greeting}
          turns={turns}
          lang={lang}
          sending={sending}
        />
      </main>

      {/* ── Input bar ──────────────────────────────────────── */}
      <footer
        className="flex-shrink-0 px-3 py-3 bg-[var(--surface)]"
        style={{ borderTop: "1px solid var(--border)" }}
        role="form"
        aria-label="Send a message"
      >
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            dir={isRtl ? "rtl" : "ltr"}
            placeholder={isRtl ? "اكتب رسالتك…" : "Type a message…"}
            disabled={sending || sessionExpired}
            aria-label={isRtl ? "رسالتك" : "Your message"}
            className="chat-input flex-1 px-4 py-2.5 text-sm text-[var(--text-primary)]
              bg-[var(--surface-alt)] rounded-full border border-[var(--border)]
              placeholder:text-[var(--text-muted)]
              disabled:opacity-50 transition-shadow"
            style={{
              textAlign: isRtl ? "right" : "left",
              fontFamily: "'DM Sans', system-ui, sans-serif",
            }}
          />

          <button
            type="submit"
            disabled={!input.trim() || sending || sessionExpired}
            aria-label={isRtl ? "إرسال" : "Send message"}
            className="send-btn flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center
              bg-[var(--accent)] text-white
              disabled:opacity-35 disabled:pointer-events-none"
          >
            <SendIcon rtl={isRtl} />
          </button>
        </form>

        <p className="text-center text-[9px] text-[var(--text-muted)] mt-2 tracking-wide"
          style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
          {isRtl ? "مشغّل بالذكاء الاصطناعي" : "Powered by AI · Municipal Services"}
        </p>
      </footer>
    </div>
  );
}

/* ── Icons ──────────────────────────────────────────────────── */

function CivicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path d="M10 2L17 6V14L10 18L3 14V6L10 2Z" stroke="rgba(255,255,255,0.7)"
        strokeWidth="1.2" fill="none" />
      <circle cx="10" cy="10" r="2.5" fill="rgba(255,255,255,0.6)" />
    </svg>
  );
}

function SendIcon({ rtl }: { rtl: boolean }) {
  return (
    <svg
      width="16" height="16" viewBox="0 0 16 16" fill="none"
      style={{ transform: rtl ? "rotate(180deg)" : undefined }}
      aria-hidden
    >
      <path d="M14 8L2 3l3.5 5L2 13l12-5z" fill="currentColor" />
    </svg>
  );
}
