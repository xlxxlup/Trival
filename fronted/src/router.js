import { createRouter, createWebHistory } from 'vue-router'
import Home from './components/TravelAssistant.vue' // 假设 TravelAssistant.vue 是你的主页
import Login from './components/Login.vue'
import Register from './components/Register.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/login', component: Login },
  { path: '/register', component: Register }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router