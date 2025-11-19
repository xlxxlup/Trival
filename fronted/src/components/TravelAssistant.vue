<script setup>
import { reactive, ref } from 'vue'
import { generateTravelPlan, resumeTravelPlan } from '../services/api'

const form = reactive({
	origin:'',
	destination: '',
	date: '',
	days: 3,
	budget: '',
	preferences: '',
	people: 1
})

const loading = ref(false)
const errorMessage = ref('')
const planResult = ref(null)

// 人工介入相关状态
const sessionId = ref('')
const needIntervention = ref(false)
const interventionRequest = ref(null)
const interventionResponse = reactive({
	text_input: '',
	selected_options: []
})

async function onSubmit() {
	errorMessage.value = ''
	planResult.value = null
	needIntervention.value = false
	interventionRequest.value = null
	loading.value = true
	try {
		const payload = {
			origin: form.origin,
			destination: form.destination,
			date: form.date,
			days: Number(form.days),
			budget: Number(form.budget) || 0,
			preferences: form.preferences,
			people: Number(form.people) || 1
		}
		const data = await generateTravelPlan(payload)
		handleResponse(data)
	} catch (err) {
		errorMessage.value = err?.message || '请求失败'
	} finally {
		loading.value = false
	}
}

function handleResponse(data) {
	sessionId.value = data.session_id

	if (data.need_intervention) {
		// 需要人工介入
		needIntervention.value = true
		interventionRequest.value = data.intervention_request
		// 重置用户响应
		interventionResponse.text_input = ''
		interventionResponse.selected_options = []
	} else {
		// 已完成
		needIntervention.value = false
		interventionRequest.value = null
		planResult.value = data
	}
}

async function onInterventionSubmit() {
	errorMessage.value = ''
	loading.value = true
	try {
		const response = {
			text_input: interventionResponse.text_input || null,
			selected_options: interventionResponse.selected_options.length > 0
				? interventionResponse.selected_options
				: null
		}
		const data = await resumeTravelPlan(sessionId.value, response)
		handleResponse(data)
	} catch (err) {
		errorMessage.value = err?.message || '请求失败'
	} finally {
		loading.value = false
	}
}

function toggleOption(optionId) {
	const index = interventionResponse.selected_options.indexOf(optionId)
	if (index === -1) {
		// 单选模式下，清除之前的选择
		if (interventionRequest.value?.question_type === 'single_choice') {
			interventionResponse.selected_options = [optionId]
		} else {
			interventionResponse.selected_options.push(optionId)
		}
	} else {
		interventionResponse.selected_options.splice(index, 1)
	}
}

function isOptionSelected(optionId) {
	return interventionResponse.selected_options.includes(optionId)
}
</script>

<template>
	<div class="assistant">
		<h1>旅游攻略助手</h1>

		<!-- 主表单 -->
		<form v-if="!needIntervention" class="assistant-form" @submit.prevent="onSubmit">
			<div class="field">
				<label>出发地</label>
				<input v-model="form.origin" placeholder="如：北京、上海、成都" required />
			</div>
			<div class="field">
				<label>目的地</label>
				<input v-model="form.destination" placeholder="如：北京、上海、成都" required />
			</div>
			<div class="field">
				<label>出发日期</label>
				<input type="date" v-model="form.date" required />
			</div>
			<div class="field">
				<label>天数</label>
				<input type="number" v-model.number="form.days" min="1" />
			</div>
			<div class="field">
				<label>出行人数</label>
				<input type="number" v-model.number="form.people" min="1" />
			</div>
			<div class="field">
				<label>预算（元）</label>
				<input type="number" v-model.number="form.budget" placeholder="如：3000" />
			</div>
			<div class="field">
				<label>偏好与需求</label>
				<textarea v-model="form.preferences" rows="3" placeholder="如：美食、亲子、自然、夜生活" />
			</div>
			<button type="submit" :disabled="loading">{{ loading ? '生成中...' : '生成攻略' }}</button>
		</form>

		<!-- 人工介入表单 -->
		<div v-if="needIntervention" class="intervention-panel">
			<h2>需要您的确认</h2>
			<p class="intervention-message">{{ interventionRequest?.message }}</p>

			<!-- 显示当前规划 -->
			<div v-if="interventionRequest?.current_plan" class="current-plan">
				<h3>当前规划：</h3>
				<ul>
					<li v-for="(step, index) in interventionRequest.current_plan" :key="index">
						{{ step }}
					</li>
				</ul>
			</div>

			<!-- 文本输入 -->
			<div v-if="interventionRequest?.question_type === 'text'" class="field">
				<label>请输入您的反馈或补充信息：</label>
				<textarea
					v-model="interventionResponse.text_input"
					rows="4"
					placeholder="请输入您的想法..."
				/>
			</div>

			<!-- 选项选择 -->
			<div v-if="interventionRequest?.options" class="options-group">
				<label>请选择：</label>
				<div
					v-for="option in interventionRequest.options"
					:key="option.id"
					class="option-item"
					:class="{ selected: isOptionSelected(option.id) }"
					@click="toggleOption(option.id)"
				>
					<span class="option-indicator">
						{{ isOptionSelected(option.id) ? '✓' : '○' }}
					</span>
					<span class="option-text">{{ option.text }}</span>
				</div>
			</div>

			<div class="intervention-actions">
				<button
					type="button"
					@click="onInterventionSubmit"
					:disabled="loading"
				>
					{{ loading ? '处理中...' : '确认并继续' }}
				</button>
			</div>
		</div>

		<p v-if="errorMessage" class="error">{{ errorMessage }}</p>

		<div v-if="planResult && !needIntervention" class="result">
			<h2>生成结果</h2>

			<!-- 规划列表 -->
			<div v-if="planResult.replan" class="result-section">
				<h3>旅游规划</h3>
				<ul>
					<li v-for="(item, index) in planResult.replan" :key="index">{{ item }}</li>
				</ul>
			</div>

			<!-- 旅游攻略信息 -->
			<div v-if="planResult.amusement_info" class="result-section">
				<h3>详细攻略</h3>
				<pre>{{ JSON.stringify(planResult.amusement_info, null, 2) }}</pre>
			</div>
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

/* 人工介入样式 */
.intervention-panel {
	background: #f8fafc;
	border: 2px solid #6366f1;
	border-radius: 12px;
	padding: 20px;
	margin-bottom: 16px;
}

.intervention-panel h2 {
	color: #6366f1;
	margin-bottom: 12px;
	font-size: 18px;
}

.intervention-message {
	font-size: 16px;
	color: #334155;
	margin-bottom: 16px;
	line-height: 1.5;
}

.current-plan {
	background: white;
	border: 1px solid #e2e8f0;
	border-radius: 8px;
	padding: 12px;
	margin-bottom: 16px;
}

.current-plan h3 {
	font-size: 14px;
	color: #64748b;
	margin-bottom: 8px;
}

.current-plan ul {
	margin: 0;
	padding-left: 20px;
}

.current-plan li {
	margin-bottom: 4px;
	color: #475569;
}

.options-group {
	margin-bottom: 16px;
}

.options-group label {
	display: block;
	margin-bottom: 12px;
}

.option-item {
	display: flex;
	align-items: center;
	padding: 12px 16px;
	background: white;
	border: 2px solid #e2e8f0;
	border-radius: 8px;
	margin-bottom: 8px;
	cursor: pointer;
	transition: all 0.2s;
}

.option-item:hover {
	border-color: #6366f1;
}

.option-item.selected {
	border-color: #6366f1;
	background: #eef2ff;
}

.option-indicator {
	margin-right: 12px;
	font-size: 16px;
	color: #6366f1;
}

.option-text {
	flex: 1;
	color: #334155;
}

.intervention-actions {
	margin-top: 16px;
}

.result-section {
	margin-bottom: 20px;
}

.result-section h3 {
	font-size: 16px;
	color: #334155;
	margin-bottom: 12px;
}

.result-section ul {
	background: #f1f5f9;
	padding: 16px 16px 16px 36px;
	border-radius: 8px;
	margin: 0;
}

.result-section li {
	margin-bottom: 8px;
	color: #475569;
}
</style>


