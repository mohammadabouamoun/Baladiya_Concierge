import React, { useState, useRef, useEffect } from "react";

interface Props {
  lang: "en" | "ar";
  countryCode: string;   // e.g. "961" — no leading +
  onRequestOtp: (phoneE164: string) => Promise<"sent" | "rate_limited" | "error">;
  onConfirmOtp: (phoneE164: string, code: string) => Promise<"verified" | "invalid" | "error">;
  onDismiss: () => void;
}

const T = {
  en: {
    title: "Verify your phone",
    subtitle: "Required to file a report",
    phonePlaceholder: "70 123 456",
    sendCode: "Send Code",
    sending: "Sending…",
    codeSent: "Code sent to",
    codePlaceholder: "6-digit code",
    verify: "Verify",
    verifying: "Verifying…",
    changePhone: "Change number",
    dismiss: "Cancel",
    rateLimit: "Too many attempts. Please try again in 10 minutes.",
    invalid: "Incorrect code. Please try again.",
    error: "Something went wrong. Please try again.",
    invalidPhone: "Enter a valid Lebanese mobile number (e.g. 70 123456).",
  },
  ar: {
    title: "تحقق من هاتفك",
    subtitle: "مطلوب لتقديم بلاغ",
    phonePlaceholder: "70 123 456",
    sendCode: "إرسال الرمز",
    sending: "جارٍ الإرسال…",
    codeSent: "تم إرسال الرمز إلى",
    codePlaceholder: "رمز مؤلف من 6 أرقام",
    verify: "تحقق",
    verifying: "جارٍ التحقق…",
    changePhone: "تغيير الرقم",
    dismiss: "إلغاء",
    rateLimit: "محاولات كثيرة جداً. حاول مرة أخرى خلال 10 دقائق.",
    invalid: "الرمز غير صحيح. حاول مرة أخرى.",
    error: "حدث خطأ ما. يرجى المحاولة مرة أخرى.",
    invalidPhone: "أدخل رقم هاتف لبناني صحيح (مثل 70 123456).",
  },
};

// Lebanese mobile prefixes — Touch & Alfa
const LB_PREFIXES = ["03", "70", "71", "76", "78", "79", "81", "82", "83", "86", "88"];

function validateLocal961(local: string): boolean {
  // Must be exactly 8 digits starting with a valid Lebanese mobile prefix
  return local.length === 8 && local[0] !== undefined &&
    LB_PREFIXES.includes(local.slice(0, 2)) && /^\d+$/.test(local);
}

function toE164(countryCode: string, localDigits: string): string {
  return `+${countryCode}${localDigits}`;
}

type Step = "phone" | "code";

export default function PhoneVerification({
  lang, countryCode, onRequestOtp, onConfirmOtp, onDismiss,
}: Props) {
  const t = T[lang];
  const isRtl = lang === "ar";
  const [step, setStep] = useState<Step>("phone");
  const [localNumber, setLocalNumber] = useState("");   // what user types
  const [confirmedE164, setConfirmedE164] = useState(""); // stored after OTP sent
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, [step]);

  // Strip non-digits from input and limit to 9 chars (max "070123456")
  const handlePhoneChange = (raw: string) => {
    setLocalNumber(raw.replace(/\D/g, "").slice(0, 9));
    setErrorMsg("");
  };

  const getLocalDigits = (): string => {
    // Strip optional leading 0 (070... → 70...)
    const d = localNumber.replace(/\D/g, "");
    return d.startsWith("0") ? d.slice(1) : d;
  };

  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    const local = getLocalDigits();

    // Client-side validation before network call
    if (countryCode === "961" && !validateLocal961(local)) {
      setErrorMsg(t.invalidPhone);
      return;
    }

    const e164 = toE164(countryCode, local);
    setBusy(true);
    setErrorMsg("");
    const result = await onRequestOtp(e164);
    setBusy(false);
    if (result === "sent") {
      setConfirmedE164(e164);
      setStep("code");
    } else if (result === "rate_limited") {
      setErrorMsg(t.rateLimit);
    } else {
      setErrorMsg(t.error);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length !== 6 || busy) return;
    setBusy(true);
    setErrorMsg("");
    const result = await onConfirmOtp(confirmedE164, code);
    setBusy(false);
    if (result === "invalid") {
      setErrorMsg(t.invalid);
      setCode("");
    } else if (result === "error") {
      setErrorMsg(t.error);
    }
    // "verified" → parent clears verificationRequired + auto-resends the pending report
  };

  // Masked display for "code sent to" label
  const maskedPhone = confirmedE164.replace(/(\+\d{3})(\d{2})(\d+)(\d{3})/, "$1 $2 *** $4");

  return (
    <div
      dir={isRtl ? "rtl" : "ltr"}
      className="flex flex-col gap-3 px-4 py-4 bg-[var(--surface-alt)]"
      style={{ borderTop: "1px solid var(--border)" }}
      role="region"
      aria-label={t.title}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p
            className="text-[var(--text-primary)] text-[13px] font-semibold leading-tight"
            style={{ fontFamily: "'Syne', system-ui, sans-serif" }}
          >
            {t.title}
          </p>
          <p
            className="text-[var(--text-muted)] text-[11px] mt-0.5"
            style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
          >
            {t.subtitle}
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label={t.dismiss}
          className="text-[var(--text-muted)] text-[11px] hover:text-[var(--text-secondary)] transition-colors"
          style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
        >
          {t.dismiss}
        </button>
      </div>

      {/* Phone step */}
      {step === "phone" && (
        <form onSubmit={handleSendCode} className="flex flex-col gap-2">
          {/* Country code prefix + local number input side by side */}
          <div className="flex items-center gap-1.5">
            <span
              className="flex-shrink-0 px-3 py-2 text-sm text-[var(--text-secondary)]
                bg-[var(--surface)] rounded-lg border border-[var(--border)] select-none"
              style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
              aria-label={`Country code +${countryCode}`}
            >
              +{countryCode}
            </span>
            <input
              ref={inputRef}
              type="tel"
              value={localNumber}
              onChange={(e) => handlePhoneChange(e.target.value)}
              placeholder={t.phonePlaceholder}
              disabled={busy}
              dir="ltr"
              inputMode="numeric"
              aria-label={isRtl ? "رقم الهاتف المحلي" : "Local phone number"}
              className="chat-input flex-1 min-w-0 px-3 py-2 text-sm text-[var(--text-primary)]
                bg-[var(--surface)] rounded-lg border border-[var(--border)]
                placeholder:text-[var(--text-muted)] disabled:opacity-50 transition-shadow"
              style={{ fontFamily: "'DM Sans', system-ui, sans-serif", textAlign: "left" }}
            />
          </div>
          {errorMsg && (
            <p
              className="text-red-500 text-[11px]"
              style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
            >
              {errorMsg}
            </p>
          )}
          <button
            type="submit"
            disabled={localNumber.replace(/\D/g, "").length < 8 || busy}
            className="w-full py-2 px-4 rounded-lg text-sm font-medium text-white
              bg-[var(--accent)] disabled:opacity-40 disabled:pointer-events-none transition-opacity"
            style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
          >
            {busy ? t.sending : t.sendCode}
          </button>
        </form>
      )}

      {/* Code step */}
      {step === "code" && (
        <form onSubmit={handleVerify} className="flex flex-col gap-2">
          <p
            className="text-[var(--text-secondary)] text-[11px]"
            style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
          >
            {t.codeSent}{" "}
            <span className="font-medium" dir="ltr">
              {maskedPhone}
            </span>
          </p>
          <input
            ref={inputRef}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder={t.codePlaceholder}
            disabled={busy}
            dir="ltr"
            aria-label={isRtl ? "رمز التحقق" : "Verification code"}
            className="chat-input w-full px-3 py-2 text-sm text-[var(--text-primary)] text-center
              bg-[var(--surface)] rounded-lg border border-[var(--border)]
              placeholder:text-[var(--text-muted)] disabled:opacity-50 transition-shadow"
            style={{ fontFamily: "monospace", letterSpacing: "0.3em" }}
          />
          {errorMsg && (
            <p
              className="text-red-500 text-[11px]"
              style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
            >
              {errorMsg}
            </p>
          )}
          <button
            type="submit"
            disabled={code.length !== 6 || busy}
            className="w-full py-2 px-4 rounded-lg text-sm font-medium text-white
              bg-[var(--accent)] disabled:opacity-40 disabled:pointer-events-none transition-opacity"
            style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
          >
            {busy ? t.verifying : t.verify}
          </button>
          <button
            type="button"
            onClick={() => {
              setStep("phone");
              setCode("");
              setErrorMsg("");
            }}
            className="text-[var(--text-muted)] text-[11px] hover:text-[var(--text-secondary)] transition-colors text-center"
            style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}
          >
            {t.changePhone}
          </button>
        </form>
      )}
    </div>
  );
}
