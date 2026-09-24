<template>
  <div class="product-list">
    <div class="filter-bar">
      <el-input
        v-model="searchText"
        placeholder="搜索产品名称或编码..."
        clearable
        style="width: 300px"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>
    
    <el-table :data="filteredProducts" style="width: 100%">
      <el-table-column prop="code" label="产品编码" width="150" />
      <el-table-column prop="name" label="产品名称" width="200" />
      <el-table-column prop="customer_name" label="客户" width="150" />
      <el-table-column prop="priority" label="优先级" width="100" align="center">
        <template #default="{ row }">
          <span :class="['priority-badge', `priority-${row.priority}`]">
            {{ getPriorityText(row.priority) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="$emit('edit', row)">编辑</el-button>
          <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productApi } from '../../api/product'

const emit = defineEmits(['edit'])

const products = ref([])
const searchText = ref('')

const filteredProducts = computed(() => {
  if (!searchText.value) return products.value
  const text = searchText.value.toLowerCase()
  return products.value.filter(p => 
    p.name.toLowerCase().includes(text) || 
    p.code.toLowerCase().includes(text)
  )
})

const getPriorityText = (priority) => {
  const map = { 1: '高', 2: '中', 3: '低' }
  return map[priority] || '普通'
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadProducts = async () => {
  try {
    const response = await productApi.getList()
    products.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error('加载产品列表失败')
  }
}

const handleDelete = async (product) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除产品 "${product.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await productApi.delete(product.id)
    ElMessage.success('删除成功')
    loadProducts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadProducts()
})

// 暴露刷新方法给父组件
defineExpose({
  refresh: loadProducts
})
</script>

<style lang="scss" scoped>
.product-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-bar {
  display: flex;
  gap: 12px;
}

.priority-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  
  &.priority-1 {
    background: rgba(198, 40, 40, 0.12);
    color: #c62828;
  }
  
  &.priority-2 {
    background: rgba(212, 160, 23, 0.12);
    color: #d4a017;
  }
  
  &.priority-3 {
    background: rgba(46, 125, 50, 0.12);
    color: #2e7d32;
  }
}
</style>
