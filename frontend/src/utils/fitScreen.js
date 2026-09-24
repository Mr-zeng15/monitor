/**
 * 大屏适配工具 - 纯 CSS 100% 自适应版
 *
 * 策略：
 *   - 不再使用 transform: scale() 缩放画布（避免与浏览器 ctrl+/- 缩放叠加造成比例怪异）
 *   - 通过 CSS 100% 自适应：让 1920×1080 画布按视口百分比缩放
 *   - 用户可以自由使用浏览器 ctrl+/-、ctrl+滚轮 缩放
 *   - 内容超出时画布自动扩展高度，整体页面可以滚动
 *
 * 设计要求（来自项目记忆）：
 *   "大屏适配不使用 JS 缩放，通过 CSS 100% 自适应实现"
 */

let initialized = false

/**
 * 初始化 - 使用 CSS 100vw/vh 自适应，不修改画布大小
 */
export function initFitScreen() {
  if (initialized) return
  initialized = true
  // 不需要 JS 缩放操作
  // 画布尺寸由 CSS 100% 控制：
  //   #app-canvas { width: 100%; min-height: 100vh; }
  // 这样画布自动跟随视口大小变化，并保留用户浏览器缩放能力
}
