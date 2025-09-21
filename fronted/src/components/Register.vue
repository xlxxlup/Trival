<template>
  <div class="register-container">
    <h1>注册</h1>
    <el-form label-width="80px">
      <el-form-item label="用户名">
        <el-input v-model="registerForm.username" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input type="password" v-model="registerForm.password" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="register">注册</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { reactive } from 'vue';

export default {
  setup() {
    const registerForm = reactive({
      username: '',
      password: ''
    });

    const register = () => {
      // TODO: implement register logic
      console.log('Register:', registerForm);
    };

    return {
      registerForm,
      register
    };
  }
};
</script>

<style scoped>
.register-container {
  width: 400px;
  margin: 100px auto;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 5px;
}
</style>