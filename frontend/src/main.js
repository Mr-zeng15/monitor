import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './styles/global.scss'
import { initFitScreen } from './utils/fitScreen'

const app = createApp(App)
const pinia = createPinia()

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.mount('#app')

// 启动大屏适配：CSS 100% 自适应模式（不修改画布大小，让浏览器自由缩放）
initFitScreen()

// 保险：确保 #app-canvas 不会被任何旧版 transform 缩放干扰
setTimeout(() => {
  const canvas = document.getElementById('app-canvas')
  if (canvas) {
    canvas.style.transform = ''
    canvas.style.transformOrigin = ''
    canvas.style.width = '100%'
    canvas.style.minHeight = '100vh'
    canvas.style.position = 'relative'
    canvas.style.top = ''
    canvas.style.left = ''
  }
}, 50)

// Vue 挂载完成后清除加载占位
const loader = document.querySelector('.app-loader')
if (loader) {
  loader.style.transition = 'opacity 0.2s'
  loader.style.opacity = '0'
  setTimeout(() => loader.remove(), 250)
}


