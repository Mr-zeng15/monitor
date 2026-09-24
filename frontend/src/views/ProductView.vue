<template>
  <div class="product-view">
    <div class="page-header">
      <h1>产品管理</h1>
      <p class="page-desc">管理产品基础信息</p>
    </div>
    
    <div class="content-section">
      <div class="tech-card">
        <div class="card-header">
          <h3 class="section-title">产品列表</h3>
          <button class="btn primary" @click="openProductForm">
            <el-icon><Plus /></el-icon>
            新增产品
          </button>
        </div>
        
        <ProductList @edit="openProductForm" />
      </div>
      
      <div class="tech-card" style="margin-top: 20px;">
        <div class="card-header">
          <h3 class="section-title">客户管理</h3>
          <button class="btn primary" @click="openCustomerForm">
            <el-icon><Plus /></el-icon>
            新增客户
          </button>
        </div>
        
        <CustomerManager @edit="openCustomerForm" />
      </div>
    </div>
    
    <!-- 产品表单弹窗 -->
    <ProductForm 
      v-model:visible="productFormVisible"
      :product="currentProduct"
      @success="handleProductSuccess"
    />
    
    <!-- 客户表单弹窗 -->
    <el-dialog
      v-model="customerFormVisible"
      :title="currentCustomer ? '编辑客户' : '新增客户'"
      width="500px"
    >
      <el-form :model="customerForm" label-width="100px">
        <el-form-item label="客户编码" required>
          <el-input v-model="customerForm.code" placeholder="请输入客户编码" />
        </el-form-item>
        <el-form-item label="客户名称" required>
          <el-input v-model="customerForm.name" placeholder="请输入客户名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="btn" @click="customerFormVisible = false">取消</button>
        <button class="btn primary" @click="saveCustomer">保存</button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { customerApi } from '../api/product'
import ProductList from '../components/product/ProductList.vue'
import ProductForm from '../components/product/ProductForm.vue'
import CustomerManager from '../components/product/CustomerManager.vue'

// 产品表单
const productFormVisible = ref(false)
const currentProduct = ref(null)

const openProductForm = (product = null) => {
  currentProduct.value = product
  productFormVisible.value = true
}

const handleProductSuccess = () => {
  productFormVisible.value = false
  // 刷新列表（通过事件通知子组件）
}

// 客户表单
const customerFormVisible = ref(false)
const currentCustomer = ref(null)
const customerForm = ref({
  code: '',
  name: ''
})

const openCustomerForm = (customer = null) => {
  currentCustomer.value = customer
  if (customer) {
    customerForm.value = { ...customer }
  } else {
    customerForm.value = { code: '', name: '' }
  }
  customerFormVisible.value = true
}

const saveCustomer = async () => {
  if (!customerForm.value.code || !customerForm.value.name) {
    ElMessage.warning('请填写完整信息')
    return
  }
  
  try {
    if (currentCustomer.value) {
      await customerApi.update(currentCustomer.value.id, customerForm.value)
      ElMessage.success('更新成功')
    } else {
      await customerApi.create(customerForm.value)
      ElMessage.success('创建成功')
    }
    customerFormVisible.value = false
    // 刷新客户列表
  } catch (error) {
    ElMessage.error('操作失败')
  }
}
</script>

<style lang="scss" scoped>
.product-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header {
  h1 {
    font-size: 20px;
    font-weight: 500;
    color: #e0f0ff;
    margin-bottom: 6px;
  }
  
  .page-desc {
    font-size: 13px;
    color: #6b8299;
  }
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tech-card {
  background: #002850;
  border: 1px solid rgba(0, 150, 255, 0.15);
  border-radius: 4px;
  padding: 20px 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  
  .section-title {
    font-size: 14px;
    font-weight: 500;
    color: #e0f0ff;
    display: flex;
    align-items: center;
    gap: 8px;
    
    &::before {
      content: '';
      width: 3px;
      height: 14px;
      background: #0096ff;
      border-radius: 2px;
    }
  }
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 20px;
  border: 1px solid rgba(0, 150, 255, 0.3);
  border-radius: 5px;
  background: transparent;
  color: #e0f0ff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(0, 150, 255, 0.1);
    border-color: #0096ff;
  }

  &.primary {
    background: #0096ff;
    border-color: #0096ff;
    color: #0a1928;

    &:hover {
      background: #33aaff;
    }
  }
}
</style>
