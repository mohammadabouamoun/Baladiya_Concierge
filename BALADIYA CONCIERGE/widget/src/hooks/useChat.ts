import { useState, useCallback, useRef } from "react";

export interface Turn {
  message: string;
  response?: string;
  loading?: boolean;
}

interface UseChatResult {
  turns: Turn[];
  sending: boolean;
  sessionExpired: boolean;
  send: (message: string, lang: "en" | "ar") => void;
}

const ERROR_MSG_EN = "Something went wrong. Please try again.";
const ERROR_MSG_AR = "حدث خطأ ما. يرجى المحاولة مرة أخرى.";

const MOCK_REPLIES: Record<string, string> = {
  default: "Thanks for reaching out! Our team will look into this and get back to you shortly.",
  ar: "شكراً لتواصلك معنا! سيقوم فريقنا بمراجعة طلبك والرد عليك قريباً.",
};

export function useChat(token: string, apiBase: string): UseChatResult {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sending, setSending] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const sessionId = useRef<string>(crypto.randomUUID());

  // Preview mode — simulate replies without a real backend
  if (token === "preview") {
    const send = (message: string, lang: "en" | "ar") => {
      setTurns((prev) => [...prev, { message, loading: true }]);
      setSending(true);
      setTimeout(() => {
        setTurns((prev) =>
          prev.map((t, i) =>
            i === prev.length - 1
              ? { ...t, response: lang === "ar" ? MOCK_REPLIES.ar : MOCK_REPLIES.default, loading: false }
              : t
          )
        );
        setSending(false);
      }, 1200);
    };
    return { turns, sending, sessionExpired, send };
  }

  const send = useCallback(
    (message: string, lang: "en" | "ar") => {
      if (sending || sessionExpired) return;

      setTurns((prev) => [...prev, { message, loading: true }]);
      setSending(true);

      fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: sessionId.current,
          message,
        }),
      })
        .then((r) => {
          if (r.status === 401) {
            setSessionExpired(true);
            throw new Error("__expired__");
          }
          if (!r.ok) throw new Error(`API ${r.status}`);
          return r.json() as Promise<{ response: string; handled_by: string }>;
        })
        .then(({ response }) => {
          setTurns((prev) =>
            prev.map((t, i) =>
              i === prev.length - 1 ? { ...t, response, loading: false } : t
            )
          );
        })
        .catch((err: Error) => {
          if (err.message === "__expired__") {
            // Remove the loading turn — session-expired screen replaces it
            setTurns((prev) => prev.slice(0, -1));
            return;
          }
          setTurns((prev) =>
            prev.map((t, i) =>
              i === prev.length - 1
                ? {
                    ...t,
                    response: lang === "ar" ? ERROR_MSG_AR : ERROR_MSG_EN,
                    loading: false,
                  }
                : t
            )
          );
        })
        .finally(() => setSending(false));
    },
    [token, apiBase, sending, sessionExpired]
  );

  return { turns, sending, sessionExpired, send };
}
