/** Design tokens. Colours are CSS variables (src/index.css) so the day and night editions share one set of classes. */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"), // newsprint
        surface: token("surface"), // paper
        surface2: token("surface2"), // sand
        line: token("line"), // hairline rules
        ink: token("ink"), // navy ink
        ink2: token("ink2"),
        muted: token("muted"),
        brand: token("brand"), // deep navy
        cyan: token("sea"), // sea green (kept as "cyan" so existing classes follow the palette)
        sea: token("sea"),
        fact: token("fact"),
        inf: token("inf"),
        user: token("user"),
        hyp: token("hyp"),
        pink: token("alert"),
      },
      fontFamily: {
        sans: ['"Source Sans 3 Variable"', '"Source Sans 3"', "system-ui", "Segoe UI", "sans-serif"],
        serif: ['"Newsreader Variable"', "Newsreader", "Georgia", "serif"],
        display: ['"Newsreader Variable"', "Newsreader", "Georgia", "serif"],
      },
      borderRadius: { xl: "0.375rem", "2xl": "0.5rem" },
      boxShadow: {
        card: "none",
        glow: "none",
        lift: "0 1px 2px rgb(15 31 56 / 0.06), 0 8px 24px -12px rgb(15 31 56 / 0.18)",
      },
      keyframes: {
        rise: { from: { opacity: "0" }, to: { opacity: "1" } },
        shimmer: { to: { backgroundPosition: "-200% 0" } },
      },
      animation: {
        rise: "rise .15s ease-out both",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};
