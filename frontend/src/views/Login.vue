<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1 class="system-title">深度学习车牌识别</h1>
        <h2 class="login-title">{{ $t('login.title') }}</h2>
        <p class="login-subtitle">请输入您的登录信息</p>
      </div>

        <a-form
          :model="form"
          :rules="rules"
          @finish="handleLogin"
          layout="vertical"
          class="login-form"
        >
          <a-form-item
            :label="$t('login.username')"
            name="username"
          >
            <a-input
              v-model:value="form.username"
              :placeholder="$t('login.username')"
              size="large"
            >
              <template #prefix>
                <UserOutlined />
              </template>
            </a-input>
          </a-form-item>

          <a-form-item
            :label="$t('login.password')"
            name="password"
          >
            <a-input-password
              v-model:value="form.password"
              :placeholder="$t('login.password')"
              size="large"
            >
              <template #prefix>
                <LockOutlined />
              </template>
            </a-input-password>
          </a-form-item>

          <a-form-item
            label="验证码"
            name="captcha"
          >
            <a-row :gutter="8">
              <a-col :span="14">
                <a-input
                  v-model:value="form.captcha"
                  placeholder="请输入验证码"
                  size="large"
                >
                  <template #prefix>
                    <SafetyOutlined />
                  </template>
                </a-input>
              </a-col>
              <a-col :span="10">
                <div class="captcha-container">
                  <img
                    v-if="captchaData?.image_data"
                    :src="captchaData.image_data"
                    alt="验证码"
                    class="captcha-image"
                    @click="handleRefreshCaptcha"
                  />
                  <a-button
                    v-else
                    size="large"
                    :loading="captchaLoading"
                    @click="handleRefreshCaptcha"
                    block
                  >
                    获取验证码
                  </a-button>
                </div>
              </a-col>
            </a-row>
          </a-form-item>

          <a-form-item>
            <div class="login-options">
              <a-checkbox v-model:checked="form.remember">
                {{ $t('login.rememberMe') }}
              </a-checkbox>
              <a href="#" class="forgot-password">{{ $t('login.forgotPassword') }}</a>
            </div>
          </a-form-item>

          <a-form-item>
            <a-button
              type="primary"
              html-type="submit"
              size="large"
              :loading="loading"
              block
              class="login-button"
            >
              {{ $t('login.login') }}
            </a-button>
          </a-form-item>

          <div class="register-link">
            还没有账户？
            <a @click="goToRegister">立即注册</a>
          </div>
        </a-form>
      </div>
    </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/hertz_user'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  UserOutlined,
  LockOutlined,
  SafetyOutlined
} from '@ant-design/icons-vue'
import { useCaptcha } from '@/utils/hertz_captcha'
import { loginUser } from '@/api'
import { errorHandler, handleSuccess } from '@/utils/hertz_error_handler'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()

// 初始化错误处理器的i18n实例
errorHandler.setI18n({ t })

const loading = ref(false)

// 验证码相关
const { captchaData, captchaLoading, generateCaptcha, refreshCaptcha } = useCaptcha()

const form = reactive({
  username: '',
  password: '',
  captcha: '',
  remember: false,
})

const rules = {
  username: [
    { required: true, message: t('error.usernameRequired'), trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('error.passwordRequired'), trigger: 'blur' },
  ],
  captcha: [
    { required: true, message: t('error.captchaRequired'), trigger: 'blur' },
  ],
}

const handleLogin = async () => {
  if (loading.value) return
  
  // 验证表单
  if (!form.username || !form.password || !form.captcha) {
    message.error(t('error.requiredFieldMissing'))
    return
  }

  // 检查验证码数据是否存在
  if (!captchaData.value?.captcha_id) {
    message.error(t('error.captchaExpired'))
    await handleRefreshCaptcha()
    return
  }

  loading.value = true
  
  try {
    // 构建登录数据 - 严格按照API接口定义
    const loginData = {
      username: form.username,
      password: form.password,
      captcha_code: form.captcha.trim(),
      captcha_key: captchaData.value.captcha_id
    }
    
    const response = await loginUser(loginData)
    
    // 设置用户状态到store
    if (response.data) {
      // 设置token - 使用后端返回的access_token
      if (response.data.access_token) {
        userStore.token = response.data.access_token
        localStorage.setItem('token', response.data.access_token)
      }

      const refreshToken = response.data?.refresh_token || (response as any)?.refresh_token
      if (refreshToken) {
        localStorage.setItem('refresh_token', refreshToken)
      }
      
      // 设置用户信息
      if (response.data.user_info) {
        userStore.userInfo = response.data.user_info
        userStore.isLoggedIn = true
        localStorage.setItem('userInfo', JSON.stringify(response.data.user_info))
      }
    }
    
    handleSuccess('login')
    
    // 根据用户角色跳转到对应首页
    const userRole = response.data?.user_info?.roles?.[0]?.role_code
    
    // 仅管理员角色进入管理端，其余（含未定义）进入用户端
    const adminRoles = ['admin', 'system_admin', 'super_admin']
    const isAdmin = adminRoles.includes(userRole as any)
    if (isAdmin) {
      router.push('/admin')
    } else {
      router.push('/dashboard')
    }
    
  } catch (error: any) {
    console.error('登录失败:', error)
    
    // 清除敏感字段
    form.password = ''
    form.captcha = ''
    
    // 刷新验证码
    await handleRefreshCaptcha()
  } finally {
    loading.value = false
  }
}

const handleRefreshCaptcha = async () => {
  try {
    await refreshCaptcha()
    // 清空验证码输入
    form.captcha = ''
  } catch (error) {
    message.error('刷新验证码失败')
  }
}

const goToRegister = () => {
  router.push('/register')
}

// 页面加载时生成验证码
onMounted(() => {
  generateCaptcha()
})
</script>

<style scoped>
.login-container {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5 url('/public/models/background.jpg') no-repeat center center;
  background-size: cover;
  align-items: center;
  justify-content: center;
}

.login-card {
  width: 100%;
  max-width: 480px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.login-header {
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

.login-title {
  font-size: 20px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.login-subtitle {
  color: #666;
  font-size: 14px;
}

.login-form {
  margin-top: 24px;
}

.captcha-container {
  display: flex;
  gap: 8px;
}

.captcha-image {
  height: 40px;
  cursor: pointer;
  border-radius: 4px;
  border: 1px solid #d9d9d9;
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.forgot-password {
  color: #1890ff;
}

.login-button {
  height: 40px;
  font-size: 16px;
}

.register-link {
  text-align: center;
  margin-top: 16px;
  color: #666;
}
</style>
