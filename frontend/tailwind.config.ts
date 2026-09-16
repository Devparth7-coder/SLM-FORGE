import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Dark research-lab palette
        bg: {
          DEFAULT: "#0a0a0b",
          elevated: "#111114",
          surface: "#16161a",
          muted: "#1c1c21",
        },
        border: {
          DEFAULT: "#26262c",
          subtle: "#1e1e23",
        },
        fg: {
          DEFAULT: "#e4e4e7",
          muted: "#a1a1aa",
          subtle: "#71717a",
        },
        accent: {
          DEFAULT: "#3b82f6",
          success: "#22c55e",
          warning: "#f59e0b",
          danger: "#ef4444",
          info: "#06b6d4",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas",
          "Liberation Mono", "Courier New", "monospace",
        ],
        sans: [
          "Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI",
          "Roboto", "Helvetica Neue", "Arial", "sans-serif",
        ],
      },
      fontSize: {
        xxs: "0.625rem",
      },
    },
  },
  plugins: [],
};

export default config;
