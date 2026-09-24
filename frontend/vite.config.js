import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// ★ 2026-09-16：dev server 的代理目标改为可用环境变量覆盖，避免换端口就得改代码。
//   （只影响 `npm run dev`；生产构建不走这里 —— 前端产物用相对路径 /api，
//     由 Django 在同源下提供，换端口/换机器都不受影响。）
//   用法：VITE_DEV_BACKEND=http://127.0.0.1:8001 npm run dev
const DEV_BACKEND = process.env.VITE_DEV_BACKEND || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: DEV_BACKEND,
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        // ★ 使用 Dart Sass 的 modern API（Vite 5.4+ 支持）
        //   默认值 'legacy' 会在每次编译时打印：
        //   "The legacy JS API is deprecated and will be removed in Dart Sass 2.0.0."
        //   注意：'modern' 走 sass 包的 compileString；'modern-compiler' 需要额外装 sass-embedded
        api: 'modern',
        charset: false,
      },
    },
  },
});
