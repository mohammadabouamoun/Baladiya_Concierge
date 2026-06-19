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
  verificationRequired: boolean;
  send: (message: string, lang: "en" | "ar") => void;
  requestOtp: (phone: string) => Promise<"sent" | "rate_limited" | "error">;
  confirmOtp: (phone: string, code: string) => Promise<"verified" | "invalid" | "error">;
  dismissVerification: () => void;
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
  const [verificationRequired, setVerificationRequired] = useState(false);
  const sessionId = useRef<string>(crypto.randomUUID());
  const pendingRef = useRef<{ message: string; lang: "en" | "ar" } | null>(null);
  // Always points to the latest send — lets confirmOtp resend without stale closure
  const sendRef = useRef<(message: string, lang: "en" | "ar") => void>(() => {});

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
    const noopAsync = async () => "error" as const;
    return {
      turns, sending, sessionExpired, verificationRequired: false,
      send, requestOtp: noopAsync, confirmOtp: noopAsync, dismissVerification: () => {},
    };
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
          return r.json() as Promise<{
            response: string;
            handled_by: string;
            verification_required: boolean;
          }>;
        })
        .then(({ response, verification_required }) => {
          setTurns((prev) =>
            prev.map((t, i) =>
              i === prev.length - 1 ? { ...t, response, loading: false } : t
            )
          );
          if (verification_required) {
            pendingRef.current = { message, lang };
            setVerificationRequired(true);
          }
        })
        .catch((err: Error) => {
          if (err.message === "__expired__") {
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

  sendRef.current = send;

  const requestOtp = useCallback(
    async (phone: string): Promise<"sent" | "rate_limited" | "error"> => {
      try {
        const r = await fetch(`${apiBase}/verify/otp/request`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ phone, session_id: sessionId.current }),
        });
        if (!r.ok) return "error";
        const data = (await r.json()) as { status: string };
        return data.status as "sent" | "rate_limited";
      } catch {
        return "error";
      }
    },
    [token, apiBase]
  );

  const confirmOtp = useCallback(
    async (phone: string, code: string): Promise<"verified" | "invalid" | "error"> => {
      try {
        const r = await fetch(`${apiBase}/verify/otp/confirm`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ phone, code, session_id: sessionId.current }),
        });
        if (!r.ok) return "error";
        const data = (await r.json()) as { status: string };
        if (data.status === "verified") {
          setVerificationRequired(false);
          const pending = pendingRef.current;
          pendingRef.current = null;
          // Small delay so verification panel animates out before new turn appears
          if (pending) setTimeout(() => sendRef.current(pending.message, pending.lang), 120);
          return "verified";
        }
        return "invalid";
      } catch {
        return "error";
      }
    },
    [token, apiBase]
  );

  const dismissVerification = useCallback(() => {
    setVerificationRequired(false);
    pendingRef.current = null;
  }, []);

  return { turns, sending, sessionExpired, verificationRequired, send, requestOtp, confirmOtp, dismissVerification };
}
