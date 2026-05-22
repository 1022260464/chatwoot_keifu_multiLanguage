import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const backendEnv = loadEnv(mode, '../../', '')
  const extraAllowedHosts = (process.env.VITE_ALLOWED_HOSTS || backendEnv.VITE_ALLOWED_HOSTS || '')
    .split(',')
    .map((host) => host.trim())
    .filter(Boolean)

  return {
    plugins: [vue()],
    define: {
      __DASHBOARD_API_TOKEN__: JSON.stringify(
        backendEnv.DASHBOARD_API_TOKEN || backendEnv.VITE_DASHBOARD_API_TOKEN || '',
      ),
    },
    server: {
      host: '0.0.0.0',
      allowedHosts: ['192.168.2.102.nip.io', 'chat.wupiantech.com', ...extraAllowedHosts],
      proxy: {
        '/dashboard': {
          target: 'http://127.0.0.1:9090',
          changeOrigin: true,
        },
      },
    },
  }
})
