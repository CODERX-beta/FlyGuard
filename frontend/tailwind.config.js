/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: "#060b16",
        panel: "#0b1324",
        panelHover: "#101b33",
        borderDark: "#1c2a44",
      },
    },
  },
  plugins: [],
};

