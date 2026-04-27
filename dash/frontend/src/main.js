import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import './style.css'
import zh from './locales/zh.js'
import en from './locales/en.js'

// 从服务端注入的全局变量读取 API Key
if (window.__SOMA_API_KEY__) {
  localStorage.setItem('soma_api_key', window.__SOMA_API_KEY__)
}

const i18n = createI18n({
  legacy: false,
  locale: 'zh',
  fallbackLocale: 'en',
  messages: { zh, en },
})

const app = createApp(App)
app.use(router)
app.use(i18n)
app.mount('#app')
