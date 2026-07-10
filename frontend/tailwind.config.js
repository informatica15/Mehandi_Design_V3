/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        henna: {
          50: '#fdfbf7',   // Cream background
          100: '#f7f2e8',  // Light warm gray
          200: '#eddcc4',  // Light amber accent
          300: '#dfc098',  // Soft bronze
          400: '#cc9766',  // Warm clay
          500: '#e07a5f',  // Vibrant copper/orange
          600: '#b85a3c',  // Deep amber
          700: '#8e3a24',  // Terracotta
          800: '#6b1d2f',  // Traditional Maroon/Burgundy
          900: '#3d0c18',  // Dark chocolate/burgundy
          950: '#1a0409',  // Near-black burgundy
        }
      },
      fontFamily: {
        sans: ['Outfit', 'Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
