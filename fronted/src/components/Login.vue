<template>
  <div class="login-container">
    <h1>登录</h1>
    <el-form label-width="80px">
      <el-form-item label="用户名">
        <el-input v-model="loginForm.username" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input type="password" v-model="loginForm.password" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="login">登录</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { reactive } from 'vue';

export default {
  setup() {
    const loginForm = reactive({
      username: '',
      password: ''
    });

    const login = () => {
      // TODO: implement login logic
      console.log('Login:', loginForm);
    };

    return {
      loginForm,
      login
    };
  }
};
</script>

<style scoped>
.login-container {
  width: 400px;
  margin: 100px auto;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 5px;
}
</style>