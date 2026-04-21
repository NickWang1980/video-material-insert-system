/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,vue}"],
  theme: {
    extend: {
      borderRadius: {
        xl: "12px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.1)",
      },
      colors: {
        brandBlack: "#000000",
        brandWhite: "#FFFFFF",
      },
    },
  },
  plugins: [],
};
