import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // BFF routes
      '/bff': {
        target: 'http://bff:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://bff:8000',
        changeOrigin: true,
      },
      // Direct-to-service routes (para demonstração do Card 18)
      '/direct/orders': {
        target: 'http://order-service:8003',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/direct\/orders/, '/orders'),
      },
      '/direct/users': {
        target: 'http://user-service:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/direct\/users/, '/users'),
      },
      '/direct/products': {
        target: 'http://product-service:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/direct\/products/, '/products'),
      },
    },
  },
})
