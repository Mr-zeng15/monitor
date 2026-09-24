<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    :title="isEdit ? '编辑产品' : '新增产品'"
    width="500px"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
    >
      <el-form-item label="产品编码" prop="code">
        <el-input
          v-model="form.code"
          placeholder="请输入产品编码"
          :disabled="isEdit"
        />
      </el-form-item>
      
      <el-form-item label="产品名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入产品名称" />
      </el-form-item>
      
      <el-form-item label="客户" prop="customer">
        <el-select
          v-model="form.customer"
          placeholder="请选择客户"
          style="width: 100%"
          popper-class="app-select-popper"
        >
          <el-option
            v-for="customer in customers"
            :key="customer.id"
            :label="customer.name"
            :value="customer.id"
          />
        </el-select>
      </el-form-item>
      
      <el-form-item label="优先级" prop="priority">
        <el-select v-model="form.priority" placeholder="请选择优先级" style="width: 100%" popper-class="app-select-popper">
          <el-option label="高" :value="1" />
          <el-option label="中" :value="2" />
          <el-option label="低" :value="3" />
          <el-option label="普通" :value="0" />
        </el-select>
      </el-form-item>
    </el-form>
    
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="submitting">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { productApi, customerApi } from '../../api/product'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  product: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:visible', 'success'])

const formRef = ref(null)
const submitting = ref(false)
const customers = ref([])

const isEdit = computed(() => !!props.product)

const form = reactive({
  code: '',
  name: '',
  customer: null,
  priority: 0
})

const rules = {
  code: [
    { required: true, message: '请输入产品编码', trigger: 'blur' },
    { max: 100, message: '编码长度不能超过100个字符', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入产品名称', trigger: 'blur' },
    { max: 200, message: '名称长度不能超过200个字符', trigger: 'blur' }
  ],
  customer: [
    { required: true, message: '请选择客户', trigger: 'change' }
  ]
}

watch(() => props.visible, async (val) => {
  if (val) {
    await loadCustomers()
    if (props.product) {
      // 编辑模式
      form.code = props.product.code
      form.name = props.product.name
      form.customer = props.product.customer
      form.priority = props.product.priority || 0
    } else {
      // 新增模式
      form.code = ''
      form.name = ''
      form.customer = null
      form.priority = 0
    }
  }
})

const loadCustomers = async () => {
  try {
    const response = await customerApi.getList()
    customers.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error('加载客户列表失败')
  }
}

const handleClose = () => {
  formRef.value?.resetFields()
  emit('update:visible', false)
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    
    if (isEdit.value) {
      await productApi.update(props.product.id, form)
      ElMessage.success('更新成功')
    } else {
      await productApi.create(form)
      ElMessage.success('创建成功')
    }
    
    emit('success')
    handleClose()
  } catch (error) {
    if (error !== false) {
      ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
    }
  } finally {
    submitting.value = false
  }
}
</script>

