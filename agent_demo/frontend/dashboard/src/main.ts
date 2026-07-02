import { createApp } from 'vue'
import * as Sentry from '@sentry/vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/main.css'
import App from './App.vue'

const app = createApp(App)
const glitchtipDsn = import.meta.env.VITE_GLITCHTIP_DSN || __GLITCHTIP_DSN__
const tracesSampleRate = Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || __SENTRY_TRACES_SAMPLE_RATE__ || 0)

if (glitchtipDsn) {
  Sentry.init({
    app,
    dsn: glitchtipDsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: Number.isFinite(tracesSampleRate) ? tracesSampleRate : 0,
  })
}

app.use(ElementPlus).mount('#app')
