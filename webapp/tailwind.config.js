/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#05070D",
        bgAlt: "#080B12",
        surface: "#101622",
        surface2: "#171F2D",
        text: "#F5F7FA",
        muted: "#98A2B3",
        soft: "#CDD5E0",
        accent: "#8EF6E4",
        gold: "#E8C878",
        hot: "#FF6FAE",
        electric: "#8EA7FF",
        success: "#5CF2A8",
        danger: "#FF5C7A",
      },
    },
  },
  plugins: [],
};
