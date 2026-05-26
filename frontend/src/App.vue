<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useUserStore } from './stores/hertz_user'
import { RouterView } from 'vue-router'
import { ConfigProvider } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import enUS from 'ant-design-vue/es/locale/en_US'

const userStore = useUserStore()

// 主题配置 - 简约现代风格
const theme = ref({
  algorithm: 'default' as 'default' | 'dark' | 'compact',
  token: {
    colorPrimary: '#2563eb',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    borderRadius: 8,
    fontSize: 14,
  },
})

// 语言配置
const locale = ref(zhCN)

// 主题切换
const toggleTheme = () => {
  const currentTheme = localStorage.getItem('theme') || 'light'
  const newTheme = currentTheme === 'light' ? 'dark' : 'light'
  
  localStorage.setItem('theme', newTheme)
  
  if (newTheme === 'dark') {
    theme.value.algorithm = 'dark'
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    theme.value.algorithm = 'default'
    document.documentElement.setAttribute('data-theme', 'light')
  }
}

// 初始化主题
onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'light'
  if (savedTheme === 'dark') {
    theme.value.algorithm = 'dark'
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    theme.value.algorithm = 'default'
    document.documentElement.setAttribute('data-theme', 'light')
  }
})

const showLayout = computed(() => {
  return userStore.isLoggedIn
})
</script>

<template>
  <div id="app">
    <ConfigProvider :theme="theme" :locale="locale">
      <RouterView />
    </ConfigProvider>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  margin: 0;
  padding: 0;
}
</style>
