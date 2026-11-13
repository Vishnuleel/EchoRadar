/** Theme tokens. Colours are CSS variables (see src/index.css) so dark and light share one set of classes. */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        surface2: token("surface2"),
        line: token("line"),
        ink: token("ink"),
        ink2: token("ink2"),
        muted: token("muted"),
        brand: token("brand"),
        cyan: token("cyan"),
        // label colours used everywhere: FACT / INFERENCE / USER / HYPOTHESIS
        fact: token("fact"),
        inf: token("inf"),
        user: token("user"),
        hyp: token("hyp"),
        pink: token("pink"),
      },
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "Segoe UI", "sans-serif"],
        display: ['"Space Grotesk Variable"', '"Inter Variable"', "system-ui", "sans-serif"],
      },
      borderRadius: { xl: "0.875rem", "2xl": "1.125rem" },
      boxShadow: {
        card: "0 1px 0 rgb(255 255 255 / 0.03) inset, 0 10px 30px -18px rgb(0 0 0 / 0.55)",
        glow: "0 0 0 1px rgb(var(--brand) / 0.35), 0 8px 30px -8px rgb(var(--brand) / 0.45)",
      },
      keyframes: {
        sweep: { to: { transform: "rotate(360deg)" } },
        ping2: { "0%": { transform: "scale(.6)", opacity: ".9" }, "100%": { transform: "scale(2.6)", opacity: "0" } },
        rise: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } },
        shimmer: { to: { backgroundPosition: "-200% 0" } },
      },
      animation: {
        sweep: "sweep 7s linear infinite",
        ping2: "ping2 2.6s ease-out infinite",
        rise: "rise .35s ease-out both",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};
