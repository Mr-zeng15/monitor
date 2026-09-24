<template>
  <div class="customer-manager">
    <el-table :data="customers" style="width: 100%">
      <el-table-column prop="code" label="客户编码" width="150" />
      <el-table-column prop="name" label="客户名称" width="200" />
      <el-table-column prop="product_count" label="产品数量" width="100" align="center" />
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
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { customerApi } from '../../api/product'

const emit = defineEmits(['edit'])

const customers = ref([])

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadCustomers = async () => {
  try {
    const response = await customerApi.getList()
    customers.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error('加载客户列表失败')
  }
}

const handleDelete = async (customer) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除客户 "${customer.name}" 吗？该客户下的所有产品也将被删除。`,
      '确认删除',
      { type: 'warning' }
    )
    await customerApi.delete(customer.id)
    ElMessage.success('删除成功')
    loadCustomers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadCustomers()
})

// 暴露刷新方法给父组件
defineExpose({
  refresh: loadCustomers
})
</script>

<style lang="scss" scoped>
.customer-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
