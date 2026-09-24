import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      {
        // ★ 首页默认直达 BY FAB 总览（2026-09-08 用户要求进页面第一页是 BYfab 总览）
        path: '',
        redirect: '/by-fab'
      },
      {
        // ★ 主控看板独立路由（原挂在 '/' 下；'/' 现为重定向，故菜单需改指这里）
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue')
      },
      {
        path: 'by-fab',
        name: 'ByFab',
        component: () => import('../views/ByFabView.vue')
      },
      {
        path: 'warning',
        name: 'Warning',
        component: () => import('../views/WarningView.vue')
      },
      {
        path: 'decision-review',
        name: 'DecisionReview',
        component: () => import('../views/DecisionReviewView.vue')
      },
      {
        path: 'preplan',
        name: 'Preplan',
        component: () => import('../views/PreplanView.vue')
      },
      {
        path: 'entry-table',
        name: 'EntryTable',
        component: () => import('../views/EntryTableView.vue')
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('../views/HistoryView.vue')
      },
      {
        path: 'robot-automation',
        name: 'RobotAutomation',
        component: () => import('../views/RobotAutomationView.vue')
      },
      {
        // ★ 2026-09-24：Excel 处理测试（Dify workflow 文件中继）
        path: 'excel-flow',
        name: 'ExcelFlow',
        component: () => import('../views/ExcelFlowView.vue')
      },
      {
        // ★ 2026-09-16：QC_AI_TEAM · AI Agent 专案登记（由纯前端 localStorage 版改为前后端版）
        path: 'qc-ai-team',
        name: 'QcAiTeamView',
        component: () => import('../views/QcAiTeamView.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/SettingsView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
