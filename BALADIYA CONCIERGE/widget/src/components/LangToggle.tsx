import { useEffect } from "react";

interface Props {
  lang: "en" | "ar";
  onToggle: (lang: "en" | "ar") => void;
}

export default function LangToggle({ lang, onToggle }: Props) {
  useEffect(() => {
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [lang]);

  return (
    <button
      type="button"
      onClick={() => onToggle(lang === "en" ? "ar" : "en")}
      aria-label={lang === "en" ? "Switch to Arabic" : "Switch to English"}
      aria-pressed={lang === "ar"}
      className="lang-pill flex-shrink-0 px-2.5 py-1 rounded-full text-[11px] font-semibold
        text-white/70 border border-white/20
        hover:text-white hover:border-white/40 hover:bg-white/10
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
      style={{ fontFamily: "'Syne', system-ui, sans-serif", letterSpacing: "0.04em" }}
    >
      {lang === "en" ? "ع" : "EN"}
    </button>
  );
}
