<template>
  <div class="register-container">
    <div class="register-card">
      <div class="register-header">
        <h1 class="system-title">深度学习车牌识别</h1>
        <h1 class="register-title">{{ $t('register.title') }}</h1>
        <p class="register-subtitle">请填写注册信息</p>
      </div>
        
        <a-form
          :model="form"
          :rules="rules"
          @finish="handleRegister"
          layout="vertical"
          class="register-form"
        >
          <a-form-item
            label="用户名"
            name="username"
          >
            <a-input
              v-model:value="form.username"
              placeholder="请输入用户名"
              size="large"
            >
              <template #prefix>
                <UserOutlined />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item
            label="邮箱"
            name="email"
          >
            <a-input
              v-model:value="form.email"
              placeholder="请输入邮箱"
              size="large"
            >
              <template #prefix>
                <MailOutlined />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item label="真实姓名" name="real_name">
            <a-input
              v-model:value="form.real_name"
              placeholder="请输入真实姓名"
              size="large"
            >
              <template #prefix>
                <IdcardOutlined />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item label="手机号" name="phone">
            <a-input
              v-model:value="form.phone"
              placeholder="请输入手机号"
              size="large"
            >
              <template #prefix>
                <PhoneOutlined />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item
            label="密码"
            name="password"
          >
            <a-input-password
              v-model:value="form.password"
              placeholder="请输入密码"
              size="large"
            >
              <template #prefix>
                <LockOutlined />
              </template>
            </a-input-password>
          </a-form-item>

          <a-form-item
            label="确认密码"
            name="confirmPassword"
          >
            <a-input-password
              v-model:value="form.confirmPassword"
              placeholder="请再次输入密码"
              size="large"
            >
              <template #prefix>
                <LockOutlined />
              </template>
            </a-input-password>
          </a-form-item>

          <a-form-item>
            <a-button
              type="primary"
              html-type="submit"
              size="large"
              :loading="loading"
              block
              class="register-button"
            >
              注册
            </a-button>
          </a-form-item>

          <div class="login-link">
            已有账户？
            <a @click="goToLogin">立即登录</a>
          </div>
        </a-form>
      </div>
    </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  UserOutlined,
  LockOutlined,
  MailOutlined,
  IdcardOutlined,
  PhoneOutlined,
} from '@ant-design/icons-vue'
import { registerUser } from '@/api/auth'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  real_name: '',
  phone: '',
  password: '',
  confirmPassword: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  real_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string) => {
        if (value !== form.password) {
          return Promise.reject('两次输入的密码不一致')
        }
        return Promise.resolve()
      },
      trigger: 'blur'
    }
  ],
}

const handleRegister = async () => {
  loading.value = true
  
  try {
    const payload = {
      username: form.username,
      password: form.password,
      confirm_password: form.confirmPassword,
      email: form.email,
      phone: form.phone,
      real_name: form.real_name,
      // 后端未启用验证码时传空串，保持字段兼容
      captcha: '',
      captcha_id: '',
    }

    await registerUser(payload as any)
    message.success('注册成功')
    router.push('/login')
  } catch (error: any) {
    const detail = error?.response?.data
    if (detail) {
      const msg = detail.message || detail.detail || '注册失败'
      message.error(msg)
    } else {
      message.error('注册失败')
    }
  } finally {
    loading.value = false
  }
}

const goToLogin = () => {
  router.push('/login')
}
</script>

<style scoped>
.register-container {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5 url('/public/models/background.jpg') no-repeat center center;
  background-size: cover;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.register-card {
  width: 100%;
  max-width: 480px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.register-header {
  text-align: center;
  margin-bottom: 40px;
}

.system-title {
  font-size: 24px;
  font-weight: 600;
  color: #1890ff;
  margin-bottom: 16px;
  line-height: 1.4;
}

.register-title {
  font-size: 20px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.register-subtitle {
  color: #666;
  font-size: 14px;
}

.register-form {
  margin-top: 24px;
}

.register-button {
  height: 40px;
  font-size: 16px;
}

.login-link {
  text-align: center;
  margin-top: 16px;
  color: #666;
}
</style>
