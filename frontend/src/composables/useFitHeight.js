// ============================================================
//  useFitHeight — 表格高度自适应（Q4：消除双滚动条、吸顶稳定）
//  原理：.table-wrapper 在 flex 布局中占剩余高度；ResizeObserver 监听其高度，
//        el-table 的 max-height 绑定测量值 → 只有表格内部纵向滚动（单滚动条），
//        表头在表格顶部吸顶稳定，页面外层不再出现第二个滚动条。
//  用法：
//    const wrapRef = ref(null)          // 绑到 .table-wrapper 上
//    const tableMaxH = useFitHeight(wrapRef)
//    <el-table :max-height="tableMaxH" ...>
//  注意：v-if 延迟渲染时 composable 内部用 watch 等待 wrapper 出现后自动测量。
// ============================================================
import { ref, watch, onBeforeUnmount } from 'vue'

export function useFitHeight(wrapRef) {
  const fitH = ref(400)
  let ro = null
  let observed = false

  function measure() {
    const el = wrapRef.value
    if (!el) return
    const h = Math.floor(el.clientHeight - 4)   // 减去上下边框
    if (h >= 120) fitH.value = h
  }

  // wrapper 可能因 v-if（数据加载后）才出现 → watch 等待
  watch(wrapRef, el => {
    if (!el) return
    measure()
    if (!observed && typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => measure())
      ro.observe(el)
      observed = true
    }
  }, { immediate: true })

  window.addEventListener('resize', measure)

  onBeforeUnmount(() => {
    if (ro) ro.disconnect()
    window.removeEventListener('resize', measure)
  })

  return fitH
}
