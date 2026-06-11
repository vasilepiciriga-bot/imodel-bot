/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          from: '#6C47FF',
          to: '#FF2D78',
        },
        surface: '#FFFFFF',
        bg: '#F5F5F7',
        text: '#1D1D1F',
        text2: '#6E6E73',
        success: '#34C759',
        border: 'rgba(0,0,0,0.08)',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"SF Pro Text"', 'sans-serif'],
      },
      borderRadius: {
        card: '20px',
        pill: '100px',
      },
      boxShadow: {
        card: '0 2px 20px rgba(0,0,0,0.08)',
        tab: '0 -1px 0 rgba(0,0,0,0.06)',
      },
      keyframes: {
        shimmer: {
          '100%': { transform: 'translateX(200%)' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s infinite',
      },
    },
  },
  plugins: [],
}
