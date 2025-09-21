<script setup>
import TravelAssistant from './components/TravelAssistant.vue'
</script>

<template>
  <el-menu mode="horizontal">
    <el-menu-item index="1"><router-link to="/">首页</router-link></el-menu-item>
    <el-menu-item index="2"><router-link to="/login">登录</router-link></el-menu-item>
    <el-menu-item index="3"><router-link to="/register">注册</router-link></el-menu-item>
  </el-menu>
  <router-view />
</template>

<style>
/* 可以添加一些全局样式，例如 OpenAI 风格的颜色 */
body {
  font-family: sans-serif;
  background-color: #f0f0f0;
}

a {
  text-decoration: none;
  color: #333;
}
</style>
