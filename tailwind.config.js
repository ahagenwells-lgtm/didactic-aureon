module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aureon: {
          900: "#0A0A0C",
          800: "#0F0F11",
          gold: "#C9A24B",
          indigo: "#5B4EFF",
          platinum: "#F5F4F0",
        },
      },
    },
  },
  plugins: [],
};
