<template>
  <div class="dashboard-view">
    <div class="page-header">
      <h1>æ°æ®çæ¿</h1>
      <p class="page-desc">å®æ¶çæ§äº§éæ°æ®ä¸é¢è­¦ç¶æ</p>
    </div>
    
    <div class="content-placeholder">
      <el-empty description="æ°æ®çæ¿åè½å¼åä¸­..." />
    </div>
  </div>
</template>

<script setup>
</script>

<style lang="scss" scoped>
.dashboard-view {
  height: 100%;
}

.page-header {
  margin-bottom: 24px;
  
  h1 {
    font-size: 24px;
    font-weight: 600;
    color: #e0f0ff;
    margin-bottom: 8px;
  }
  
  .page-desc {
    font-size: 14px;
    color: #8ba9c4;
  }
}

.content-placeholder {
  background: rgba(0, 40, 80, 0.3);
  border: 1px solid rgba(0, 150, 255, 0.2);
  border-radius: 8px;
  padding: 80px 0;
}
</style>
