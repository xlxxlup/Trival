<script setup>
import { reactive, ref } from 'vue'
import { generateTravelPlan } from '../services/api'

const form = reactive({
	origin:'',
	destination: '',
	days: 3,
	budget: '',
	preferences: ''
})

const loading = ref(false)
const errorMessage = ref('')
const planResult = ref(null)

async function onSubmit() {
	errorMessage.value = ''
	planResult.value = null
	loading.value = true
	try {
		const payload = {
			destination: form.destination,
			days: Number(form.days),
			budget: form.budget,
			preferences: form.preferences
		}
		const data = await generateTravelPlan(payload)
		planResult.value = data
	} catch (err) {
		errorMessage.value = err?.message || '请求失败'
	} finally {
		loading.value = false
	}
}
</script>

<template>
	<div class="assistant">
		<h1>旅游攻略助手</h1>
		<form class="assistant-form" @submit.prevent="onSubmit">
			<div class="field">
				<label>出发地</label>
				<input v-model="form.origin" placeholder="如：北京、上海、成都" required />
			</div>
			<div class="field">
				<label>目的地</label>
				<input v-model="form.destination" placeholder="如：北京、上海、成都" required />
			</div>
			<div class="field">
				<label>天数</label>
				<input type="number" v-model.number="form.days" min="1" />
			</div>
			<div class="field">
				<label>预算</label>
				<input v-model="form.budget" placeholder="如：1000-3000 元" />
			</div>
			<div class="field">
				<label>偏好与需求</label>
				<textarea v-model="form.preferences" rows="3" placeholder="如：美食、亲子、自然、夜生活" />
			</div>
			<button type="submit" :disabled="loading">{{ loading ? '生成中...' : '生成攻略' }}</button>
		</form>

		<p v-if="errorMessage" class="error">{{ errorMessage }}</p>

		<div v-if="planResult" class="result">
			<h2>生成结果</h2>
			<pre>{{ planResult }}</pre>
		</div>
	</div>
</template>

<style scoped>
.assistant {
	max-width: 860px;
	margin: 0 auto;
	padding: 24px 16px;
}

.assistant h1 {
	font-size: 24px;
	margin-bottom: 16px;
}

.assistant-form {
	display: grid;
	grid-template-columns: 1fr;
	gap: 12px;
	margin-bottom: 16px;
}

.field {
	display: flex;
	flex-direction: column;
}

label {
	font-weight: 600;
	margin-bottom: 6px;
}

input, textarea, button {
	font-size: 14px;
}

input, textarea {
	padding: 10px 12px;
	border: 1px solid #e5e7eb;
	border-radius: 8px;
	outline: none;
}

button {
	padding: 10px 14px;
	border: 1px solid #6366f1;
	background: #6366f1;
	color: white;
	border-radius: 8px;
	cursor: pointer;
}

button:disabled {
	opacity: .7;
	cursor: not-allowed;
}

.error {
	color: #ef4444;
	margin: 8px 0;
}

.result pre {
	background: #0b1020;
	color: #d1e7ff;
	padding: 12px;
	border-radius: 8px;
	overflow-x: auto;
}
</style>


