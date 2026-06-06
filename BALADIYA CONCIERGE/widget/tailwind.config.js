/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Syne'", "system-ui", "sans-serif"],
        body: ["'DM Sans'", "system-ui", "sans-serif"],
      },
      borderRadius: {
        bubble: "18px",
      },
      animation: {
        "spin-slow": "spin-slow 0.9s linear infinite",
      },
    },
  },
  plugins: [],
};
