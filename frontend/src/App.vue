<template>
  <div id="app-scale-wrap">
    <div id="app-canvas">
      <router-view />
    </div>
  </div>
</template>

<script setup>
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  width: 100%;
  min-height: 100vh;
  overflow: auto;             /* 允许浏览器原生滚动 */
  background: #03090f;
  color: #c8ddf5;
  font-family: 'Microsoft YaHei', 'Microsoft JhengHei', 'PingFang SC', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  width: 100%;
  min-height: 100vh;
  background: #03090f;
}

/* 缩放包裹层 - 100% 自适应，不限制宽度 */
#app-scale-wrap {
  width: 100%;
  min-height: 100vh;
  overflow: auto;             /* 内容超出时浏览器原生滚动条 */
  position: relative;
  background: #03090f;
  background-image:
    radial-gradient(ellipse at top, rgba(0, 60, 120, 0.15), transparent 60%),
    radial-gradient(ellipse at bottom, rgba(0, 30, 80, 0.1), transparent 60%);
}

/* 画布层 - 100% 自适应宽度，高度随内容扩展 */
#app-canvas {
  width: 100%;
  min-height: 100vh;
  position: relative;
  background: transparent;
}
</style>
