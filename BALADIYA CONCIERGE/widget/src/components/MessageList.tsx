import React, { useEffect, useRef } from "react";
import { Turn } from "../hooks/useChat";

interface Props {
  greeting: string;
  turns: Turn[];
  lang: "en" | "ar";
  sending: boolean;
}

export default function MessageList({ greeting, turns, lang, sending }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isRtl = lang === "ar";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, sending]);

  return (
    <div
      className="messages-area h-full overflow-y-auto px-4 py-5 flex flex-col gap-4"
      role="log"
      aria-label="Message history"
    >
      {/* Greeting — bot message */}
      <BotBubble text={greeting} isRtl={isRtl} />

      {turns.map((turn, i) => (
        <React.Fragment key={i}>
          {/* Visitor message */}
          <UserBubble text={turn.message} isRtl={isRtl} />

          {/* Agent response */}
          {turn.loading ? (
            <TypingBubble />
          ) : turn.response !== undefined ? (
            <BotBubble text={turn.response} isRtl={isRtl} />
          ) : null}
        </React.Fragment>
      ))}

      {/* Extra typing indicator while sending (before turn is in list) */}
      {sending && turns.length > 0 && turns[turns.length - 1].response !== undefined && (
        <TypingBubble />
      )}

      <div ref={bottomRef} className="h-px" aria-hidden />
    </div>
  );
}

/* ── Bot bubble ─────────────────────────────────────────────── */
function BotBubble({ text, isRtl }: { text: string; isRtl: boolean }) {
  return (
    <div
      className={`msg flex items-end gap-2 ${isRtl ? "flex-row-reverse justify-start" : "justify-start"}`}
      role="listitem"
    >
      {/* Avatar dot */}
      <div
        className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center mb-0.5"
        style={{
          background: "var(--accent-dim)",
          border: "1.5px solid var(--accent)",
        }}
        aria-hidden
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M5 1L8.5 3V7L5 9L1.5 7V3L5 1Z" stroke="var(--accent)"
            strokeWidth="0.9" fill="none" />
        </svg>
      </div>

      {/* Bubble */}
      <div
        className="bot-bubble msg-bubble max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed text-[var(--text-primary)]"
        style={{
          background: "var(--surface-alt)",
          borderRadius: isRtl
            ? "18px 18px 18px 4px"
            : "18px 18px 4px 18px",
          fontFamily: "'DM Sans', system-ui, sans-serif",
          borderInlineStart: "2.5px solid var(--accent)",
        }}
        dir={isRtl ? "rtl" : "ltr"}
      >
        {text}
      </div>
    </div>
  );
}

/* ── User bubble ────────────────────────────────────────────── */
function UserBubble({ text, isRtl }: { text: string; isRtl: boolean }) {
  return (
    <div
      className={`msg flex ${isRtl ? "justify-start" : "justify-end"}`}
      role="listitem"
    >
      <div
        className="max-w-[78%] px-4 py-3 text-sm leading-relaxed text-white"
        style={{
          background: "var(--accent)",
          borderRadius: isRtl
            ? "18px 18px 4px 18px"
            : "18px 18px 18px 4px",
          fontFamily: "'DM Sans', system-ui, sans-serif",
        }}
        dir={isRtl ? "rtl" : "ltr"}
      >
        {text}
      </div>
    </div>
  );
}

/* ── Typing indicator ───────────────────────────────────────── */
function TypingBubble() {
  return (
    <div className="msg flex items-end gap-2" aria-label="Assistant is typing" role="status">
      {/* Match bot avatar size */}
      <div
        className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center mb-0.5"
        style={{
          background: "var(--accent-dim)",
          border: "1.5px solid var(--accent)",
        }}
        aria-hidden
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M5 1L8.5 3V7L5 9L1.5 7V3L5 1Z" stroke="var(--accent)"
            strokeWidth="0.9" fill="none" />
        </svg>
      </div>

      <div
        className="px-4 py-3.5 flex items-center gap-1.5"
        style={{
          background: "var(--surface-alt)",
          borderRadius: "18px 18px 4px 18px",
          borderInlineStart: "2.5px solid var(--accent)",
        }}
        aria-hidden
      >
        {[0, 1, 2].map((n) => (
          <span
            key={n}
            className="dot block w-1.5 h-1.5 rounded-full"
            style={{ background: "var(--text-muted)" }}
          />
        ))}
      </div>
    </div>
  );
}
