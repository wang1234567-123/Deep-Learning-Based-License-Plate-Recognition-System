import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";
import { useUserStore } from "@/stores/hertz_user";
import { adminMenuRoutes, UserRole } from "./admin_menu";
import { userRoutes } from "./user_menu_ai";
import { hasModuleSelection } from "@/config/hertz_modules";

// 固定路由配置
const fixedRoutes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/login",
  },
  {
    path: "/home",
    name: "Home",
    component: () => import("@/views/Home.vue"),
    meta: {
      title: "首页",
      requiresAuth: false,
    },
    children: [...generateDynamicRoutes("public")],
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/Login.vue"),
    meta: {
      title: "登录",
      requiresAuth: false,
    },
  },
  {
    path: "/template/modules",
    name: "ModuleSetup",
    component: () => import("@/views/ModuleSetup.vue"),
    meta: {
      title: "模块配置",
      requiresAuth: false,
    },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("@/views/register.vue"),
    meta: {
      title: "注册",
      requiresAuth: false,
    },
  },
  // 管理端路由 - 从admin_menu.ts导入
  adminMenuRoutes,
];

// 动态生成路由配置
function generateDynamicRoutes(targetDir: string = ""): RouteRecordRaw[] {
  if (!targetDir) {
    return [];
  }
  const viewsContext = import.meta.glob("@/views/**/*.vue", { eager: true });

  return Object.entries(viewsContext)
    .map(([path, component]) => {
      const relativePath = path.match(/\/views\/(.+?)\.vue$/)?.[1];
      if (!relativePath) return null;

      const fileName = relativePath.replace(".vue", "");
      const routeName = fileName.split("/").pop()!;

      // 过滤条件
      if (targetDir && !fileName.startsWith(targetDir)) {
        return null;
      }

      // 生成路径和标题
      const routePath = `/${fileName.replace(/([A-Z])/g, "$1").toLowerCase()}`;
      const requiresAuth =
        (!routePath.startsWith("/demo") && !routePath.startsWith("/public")) || routePath.startsWith("/user_pages")&& routePath.startsWith("/admin_page");
      const pageTitle = (component as any)?.default?.title;

      // 根据路径设置角色权限
      let roles: UserRole[] = [];
      if (routePath.startsWith("/admin_page")) {
        roles = [UserRole.ADMIN, UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN];
      } else if (routePath.startsWith("/user_pages")) {
        roles = [UserRole.NORMAL_USER, UserRole.ADMIN, UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN];
      } else if (routePath.startsWith("/demo")) {
        roles = []; // demo页面不需要特定角色
      }

      return {
        path: routePath,
        name: routeName,
        component: () => import(/* @vite-ignore */ path),
        meta: { 
          title: pageTitle, 
          requiresAuth,
          roles: requiresAuth ? roles : []
        },
      };
    })
    .filter(Boolean) as RouteRecordRaw[];
}

// 合并固定路由和动态路由
const routes: RouteRecordRaw[] = [
  ...fixedRoutes,
  ...userRoutes, // 用户菜单路由 - 现在通过统一配置自动生成
  ...generateDynamicRoutes("demo"), // 生成demo文件夹的路由
  ...generateDynamicRoutes("admin_page"),//生成admin_page文件夹的路由
  // 404页面始终放在最后
  {
    path: "/:pathMatch(.*)*",
    name: "NotFound",
    component: () => import("@/views/NotFound.vue"),
    meta: {
      title: "页面未找到",
      requiresAuth: false,
    },
  },
];

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    } else {
      return { top: 0 };
    }
  },
});

// 递归打印路由信息
function printRoute(route: RouteRecordRaw, level: number = 0) {
  const indent = "  ".repeat(level);
  const meta = route.meta || {};
  const icon = meta.requiresAuth ? "🔒" : "🔓";
  const auth = meta.requiresAuth ? "需要登录" : "公开访问";
  const title = meta.title || "未命名路由";
  console.log(`${indent}${icon} ${route.path} → ${title} (${auth})`);

  // 递归打印子路由
  if (route.children && route.children.length > 0) {
    route.children.forEach((child) => printRoute(child, level + 1));
  }
}

// 路由调试信息
function logRouteInfo() {
  console.log("🚀 系统路由配置:");
  console.log("📋 路由列表:");

  routes.forEach((route) => printRoute(route));

  console.log("  ❓ /:pathMatch(.*)* → NotFound (页面未找到)");
  console.log("✅ 路由配置完成!");
}

// 重定向计数器，防止无限重定向
let redirectCount = 0;
const MAX_REDIRECTS = 3;

// 路由守卫
router.beforeEach((to, _from, next) => {
  const userStore = useUserStore();
  
  // 调试信息
  console.log('🛡️ 路由守卫检查');
  console.log('📍 目标路由:', to.path, to.name);
  console.log('🔐 需要认证:', to.meta.requiresAuth);
  console.log('👤 用户登录状态:', userStore.isLoggedIn);
  console.log('🎫 Token:', userStore.token ? '存在' : '不存在');
  console.log('📋 用户信息:', userStore.userInfo);
  console.log('🔄 重定向计数:', redirectCount);
  
  // 模板模式：首次必须先完成模块选择
  const isTemplateMode = import.meta.env.VITE_TEMPLATE_SETUP_MODE === 'true';
  if (isTemplateMode && to.name !== "ModuleSetup") {
    if (!hasModuleSelection()) {
      console.log('🧩 模板模式开启，尚未选择模块，重定向到模块配置页');
      next({ name: "ModuleSetup", query: { redirect: to.fullPath } });
      return;
    }
  }
  
  // 设置页面标题
  if (to.meta.title) {
    const appTitle = import.meta.env.VITE_APP_TITLE || '深度学习车牌识别';
    document.title = `${to.meta.title} - ${appTitle}`;
  }

  // 检查是否需要登录
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    console.log('❌ 需要登录但用户未登录，重定向到登录页');
    redirectCount++;
    if (redirectCount > MAX_REDIRECTS) {
      console.log('⚠️ 重定向次数过多，强制跳转到首页');
      redirectCount = 0;
      next({ name: "Home" });
      return;
    }
    next({ name: "Login", query: { redirect: to.fullPath } });
    return;
  }

  // 已登录用户访问登录页，根据角色重定向到对应首页
  if (to.name === "Login" && userStore.isLoggedIn) {
    const userRole = userStore.userInfo?.roles?.[0]?.role_code;
    console.log('🔄 路由守卫 - 已登录用户访问登录页');
    console.log('👤 当前用户角色:', userRole);
    console.log('📋 用户信息:', userStore.userInfo);
    
    // 重置重定向计数器
    redirectCount = 0;
    
    // 仅管理员角色进入管理端，其余（含未定义）进入用户端
    const adminRoles = [UserRole.ADMIN, UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN];
    const isAdmin = adminRoles.includes(userRole as UserRole);
    if (isAdmin) {
      console.log('➡️ 重定向到管理端首页');
      next({ name: "Admin" });
    } else {
      console.log('➡️ 重定向到用户端首页');
      next({ name: "UserDashboard" });
    }
    return;
  }

  // 检查角色权限
  if (to.meta.requiresAuth && to.meta.roles && Array.isArray(to.meta.roles)) {
    const userRole = userStore.userInfo?.roles?.[0]?.role_code;
    
    // 特殊处理：如果是管理端路由，使用自定义权限检查
    let hasPermission = false;
    if (to.path.startsWith('/admin')) {
      // 管理端路由：仅 admin/system_admin/super_admin 可访问
      const adminRoles = [UserRole.ADMIN, UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN];
      hasPermission = adminRoles.includes(userRole as UserRole);
    } else {
      // 其他路由：使用原有的角色检查逻辑
      hasPermission = to.meta.roles.length === 0 || to.meta.roles.includes(userRole as UserRole);
    }
    
    console.log('🔐 路由权限检查');
    console.log('📍 目标路由:', to.path, to.name);
    console.log('🎭 需要的角色:', to.meta.roles);
    console.log('👤 用户角色:', userRole);
    console.log('🏢 是否为管理端路由:', to.path.startsWith('/admin'));
    console.log('✅ 是否有权限:', hasPermission);
    
    if (!hasPermission) {
      console.log('❌ 权限不足，准备重定向');
      
      // 增加重定向计数
      redirectCount++;
      
      // 防止无限重定向
      if (redirectCount > MAX_REDIRECTS) {
        console.log('⚠️ 重定向次数过多，强制跳转到首页');
        redirectCount = 0;
        next({ name: "Home" });
        return;
      }
      
      // 防止无限重定向：检查是否已经在重定向过程中
      if (to.name === 'Admin' || to.name === 'UserDashboard') {
        console.log('⚠️ 检测到重定向循环，强制跳转到首页');
        redirectCount = 0;
        next({ name: "Home" });
        return;
      }
      
      // 没有权限，根据用户角色重定向到对应首页
      // 只有normal_user角色跳转到用户端，其他角色（包括未定义的）都跳转到管理端
      if (userRole === 'normal_user') {
        console.log('➡️ 重定向到用户端首页');
        next({ name: "UserDashboard" });
      } else {
        console.log('➡️ 重定向到管理端首页 (角色:', userRole || '未定义', ')');
        next({ name: "Admin" });
      }
      return;
    }
  }

  // 成功通过所有检查，重置重定向计数器
  redirectCount = 0;
  next();
});

// 路由错误处理
router.onError((error) => {
  console.error("路由错误:", error);
});

// 输出路由信息
try {
  logRouteInfo();
} catch (error) {
  console.error("打印路由信息失败:", error);
}

export default router;
