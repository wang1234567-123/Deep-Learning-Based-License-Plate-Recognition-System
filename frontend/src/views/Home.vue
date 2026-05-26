<template>
  <div class="home-container">
    <!-- 简约导航栏 -->
    <header class="header">
      <div class="header-content">
        <div class="logo-section">
          <div class="logo-text">
            <span class="brand-name">深度学习车牌识别</span>
          </div>
        </div>
        
        <nav class="navigation">
          <a href="#home" class="nav-link">首页</a>
          <a href="#about" class="nav-link">关于</a>
          <a href="#service" class="nav-link">服务</a>
          <a href="#contact" class="nav-link">联系</a>
        </nav>
        
        <div class="header-actions">
          <button class="btn-login" @click="goToLogin">
            登录
          </button>
        </div>
      </div>
    </header>

    <!-- 英雄区域 -->
    <section class="hero-section" id="home">
      <div class="hero-content">
        <h1 class="hero-title">深度学习车牌识别</h1>
        <p class="hero-description">
          基于 YOLO 与 LPRNet 的车牌检测与车牌号识别平台
        </p>
        <div class="hero-actions">
          <button class="btn-primary" @click="goToLogin">
            开始使用
          </button>
          <button class="btn-secondary">
            了解更多
          </button>
        </div>
      </div>
    </section>

    <!-- 特性区域 -->
    <section class="features-section" id="service">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">核心特性</h2>
          <p class="section-subtitle">提供全方位的功能支持</p>
        </div>
        
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3 class="feature-title">数据可视化</h3>
            <p class="feature-description">
              直观的图表展示，让数据一目了然
            </p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">🔐</div>
            <h3 class="feature-title">权限管理</h3>
            <p class="feature-description">
              完善的权限控制体系，保障系统安全
            </p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">⚡</div>
            <h3 class="feature-title">高性能</h3>
            <p class="feature-description">
              优化的架构设计，提供流畅的使用体验
            </p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">📱</div>
            <h3 class="feature-title">响应式设计</h3>
            <p class="feature-description">
              完美适配各种设备，随时随地访问
            </p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">🎨</div>
            <h3 class="feature-title">界面美观</h3>
            <p class="feature-description">
              现代化的UI设计，提升用户体验
            </p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">🔧</div>
            <h3 class="feature-title">易于扩展</h3>
            <p class="feature-description">
              模块化设计，轻松添加新功能
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 关于区域 -->
    <section class="about-section" id="about">
      <div class="container">
        <div class="about-content">
          <div class="about-text">
            <h2 class="about-title">关于系统</h2>
            <p class="about-description">
              这是一个现代化的后台管理系统模板，采用最新的技术栈构建，
              提供完善的功能模块和优雅的用户界面，帮助您快速搭建企业级应用。
            </p>
            <ul class="about-features">
              <li>基于 Vue 3 + TypeScript</li>
              <li>Ant Design Vue 组件库</li>
              <li>响应式布局设计</li>
              <li>完整的权限管理</li>
              <li>丰富的功能模块</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- 页脚 -->
    <footer class="footer" id="contact">
      <div class="container">
        <div class="footer-content">
          <div class="footer-info">
            <h3 class="footer-title">管理系统模板</h3>
            <p class="footer-description">
              现代化的后台管理系统解决方案
            </p>
          </div>
          <div class="footer-links">
            <div class="link-group">
              <h4>快速链接</h4>
              <ul>
                <li><a href="#" @click="goToLogin">登录系统</a></li>
                <li><a href="#about">关于我们</a></li>
                <li><a href="#service">功能介绍</a></li>
              </ul>
            </div>
            <div class="link-group">
              <h4>联系方式</h4>
              <ul>
                <li>邮箱：contact@example.com</li>
                <li>电话：+86 123-4567-8900</li>
              </ul>
            </div>
          </div>
        </div>
        <div class="footer-bottom">
          <p>&copy; 2024 管理系统模板. All rights reserved.</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goToLogin = () => {
  router.push('/login')
}
</script>

<style scoped lang="scss">
.home-container {
  min-height: 100vh;
  background: #ffffff;
}

// 导航栏
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.header-content {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 64px;
}

.logo-section {
  .logo-text {
    .brand-name {
      font-size: 20px;
      font-weight: 600;
      color: #111827;
    }
  }
}

.navigation {
  display: flex;
  gap: 32px;
  
  .nav-link {
    color: #6b7280;
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    transition: color 0.2s;
    
    &:hover {
      color: #2563eb;
    }
  }
}

.header-actions {
  .btn-login {
    padding: 8px 20px;
    background: #2563eb;
    border: none;
    border-radius: 6px;
    color: white;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
    
    &:hover {
      background: #1d4ed8;
    }
  }
}

// 英雄区域
.hero-section {
  padding: 160px 24px 120px;
  text-align: center;
  background: #ffffff;
}

.hero-content {
  max-width: 800px;
  margin: 0 auto;
}

.hero-title {
  font-size: 48px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 24px;
  line-height: 1.2;
}

.hero-description {
  font-size: 20px;
  color: #6b7280;
  margin-bottom: 48px;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  
  .btn-primary {
    padding: 14px 32px;
    background: #2563eb;
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
    
    &:hover {
      background: #1d4ed8;
    }
  }
  
  .btn-secondary {
    padding: 14px 32px;
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    color: #374151;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    
    &:hover {
      border-color: #2563eb;
      color: #2563eb;
    }
  }
}

// 特性区域
.features-section {
  padding: 80px 24px;
  background: #f9fafb;
}

.container {
  max-width: 1280px;
  margin: 0 auto;
}

.section-header {
  text-align: center;
  margin-bottom: 64px;
}

.section-title {
  font-size: 36px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 16px;
}

.section-subtitle {
  font-size: 18px;
  color: #6b7280;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 32px;
}

.feature-card {
  background: #ffffff;
  padding: 32px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  text-align: center;
  transition: all 0.2s;
  
  &:hover {
    border-color: #2563eb;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
  }
}

.feature-icon {
  font-size: 48px;
  margin-bottom: 20px;
}

.feature-title {
  font-size: 20px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 12px;
}

.feature-description {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
}

// 关于区域
.about-section {
  padding: 80px 24px;
  background: #ffffff;
}

.about-content {
  max-width: 800px;
  margin: 0 auto;
}

.about-text {
  text-align: center;
}

.about-title {
  font-size: 36px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 24px;
}

.about-description {
  font-size: 16px;
  color: #6b7280;
  line-height: 1.8;
  margin-bottom: 32px;
}

.about-features {
  list-style: none;
  padding: 0;
  display: inline-block;
  text-align: left;
  
  li {
    padding: 8px 0;
    color: #374151;
    font-size: 15px;
    
    &::before {
      content: '✓';
      color: #10b981;
      font-weight: bold;
      margin-right: 12px;
    }
  }
}

// 页脚
.footer {
  background: #f9fafb;
  border-top: 1px solid #e5e7eb;
  padding: 64px 24px 32px;
}

.footer-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 64px;
  margin-bottom: 48px;
}

.footer-info {
  .footer-title {
    font-size: 20px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 12px;
  }
  
  .footer-description {
    color: #6b7280;
    font-size: 14px;
    line-height: 1.6;
  }
}

.footer-links {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  
  .link-group {
    h4 {
      color: #111827;
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 16px;
    }
    
    ul {
      list-style: none;
      padding: 0;
      margin: 0;
      
      li {
        margin-bottom: 8px;
        font-size: 14px;
        color: #6b7280;
        
        a {
          color: #6b7280;
          text-decoration: none;
          transition: color 0.2s;
          
          &:hover {
            color: #2563eb;
          }
        }
      }
    }
  }
}

.footer-bottom {
  text-align: center;
  padding-top: 32px;
  border-top: 1px solid #e5e7eb;
  
  p {
    color: #9ca3af;
    font-size: 14px;
    margin: 0;
  }
}

</style>
