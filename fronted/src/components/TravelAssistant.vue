<script setup>
import { reactive, ref } from 'vue'
import { generateTravelPlan, resumeTravelPlan, submitFeedback } from '../services/api'

const form = reactive({
	origin:'沈阳',
	destination: '长沙',
	date: '',
	days: 4,
	budget: 5000,
	preferences: '我要坐飞机往返。在规划时，始终都不需要考虑总的预算问题，只需要给出规划即可。',
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

// 反馈调整相关状态
const feedbackText = ref('')
const feedbackLoading = ref(false)

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

async function onFeedbackSubmit() {
	errorMessage.value = ''
	feedbackLoading.value = true
	try {
		const data = await submitFeedback(sessionId.value, feedbackText.value)
		// 清空反馈输入
		feedbackText.value = ''
		// 处理响应
		handleResponse(data)
	} catch (err) {
		errorMessage.value = err?.message || '提交反馈失败'
	} finally {
		feedbackLoading.value = false
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

			<!-- 文本输入 - 始终显示，让用户可以补充信息 -->
			<div class="field text-input-field">
				<label>
					{{ interventionRequest?.question_type === 'text'
						? '请输入您的反馈或补充信息：'
						: '补充说明（可选）：' }}
				</label>
				<textarea
					v-model="interventionResponse.text_input"
					rows="4"
					:placeholder="interventionRequest?.question_type === 'text'
						? '请输入您的想法...'
						: '如有其他需求或想法，请在此补充...'"
				/>
				<p class="input-hint">
					💡 您可以在此补充任何额外的信息、特殊要求或想法
				</p>
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

			<!-- 旅游攻略信息 - 友好展示 -->
			<div v-if="planResult.amusement_info" class="result-section">
				<h3>✈️ 详细攻略</h3>

				<!-- 基本信息 -->
				<div class="info-card">
					<h4>📍 基本信息</h4>
					<div class="info-row">
						<span class="label">目的地：</span>
						<span>{{ planResult.amusement_info.destination }}</span>
					</div>
					<div class="info-row">
						<span class="label">出行日期：</span>
						<span>{{ planResult.amusement_info.travel_dates }}</span>
					</div>
					<div class="info-row">
						<span class="label">行程天数：</span>
						<span>{{ planResult.amusement_info.duration }}天</span>
					</div>
					<div class="info-row summary">
						<span class="label">行程概要：</span>
						<span>{{ planResult.amusement_info.summary }}</span>
					</div>
				</div>

				<!-- 交通信息 -->
				<div v-if="planResult.amusement_info.transportation" class="info-card">
					<h4>🚄 交通信息</h4>

					<!-- 去程火车 -->
					<div v-if="planResult.amusement_info.transportation.outbound && planResult.amusement_info.transportation.outbound.length > 0">
						<h5>去程车次</h5>
						<div class="train-list">
							<div v-for="(train, idx) in planResult.amusement_info.transportation.outbound" :key="idx" class="train-item">
								<div class="train-no">{{ train.train_no }}</div>
								<div class="train-details">
									<div>{{ train.from_station }} → {{ train.to_station }}</div>
									<div>{{ train.departure_time }} - {{ train.arrival_time }} ({{ train.duration }})</div>
									<div v-if="train.second_class_price">二等座：¥{{ train.second_class_price }}</div>
								</div>
							</div>
						</div>
					</div>

					<!-- 返程火车 -->
					<div v-if="planResult.amusement_info.transportation.return_trip && planResult.amusement_info.transportation.return_trip.length > 0">
						<h5>返程车次</h5>
						<div class="train-list">
							<div v-for="(train, idx) in planResult.amusement_info.transportation.return_trip" :key="idx" class="train-item">
								<div class="train-no">{{ train.train_no }}</div>
								<div class="train-details">
									<div>{{ train.from_station }} → {{ train.to_station }}</div>
									<div>{{ train.departure_time }} - {{ train.arrival_time }} ({{ train.duration }})</div>
									<div v-if="train.second_class_price">二等座：¥{{ train.second_class_price }}</div>
								</div>
							</div>
						</div>
					</div>

					<!-- 当地交通 -->
					<div v-if="planResult.amusement_info.transportation.local_transport" class="local-transport">
						<h5>当地交通建议</h5>
						<p>{{ planResult.amusement_info.transportation.local_transport }}</p>
					</div>
				</div>

				<!-- 住宿信息 -->
				<div v-if="planResult.amusement_info.accommodation && planResult.amusement_info.accommodation.length > 0" class="info-card">
					<h4>🏨 住宿推荐</h4>
					<div class="hotel-list">
						<div v-for="(hotel, idx) in planResult.amusement_info.accommodation.slice(0, 3)" :key="idx" class="hotel-item">
							<div class="hotel-name">{{ hotel.hotel_name }}</div>
							<div class="hotel-details">
								<span v-if="hotel.hotel_star">⭐ {{ hotel.hotel_star }}</span>
								<span v-if="hotel.rating">评分：{{ hotel.rating }}</span>
								<span v-if="hotel.price_per_night">¥{{ hotel.price_per_night }}/晚</span>
							</div>
							<div v-if="hotel.address" class="hotel-address">📍 {{ hotel.address }}</div>
						</div>
					</div>
				</div>

				<!-- 天气信息 -->
				<div v-if="planResult.amusement_info.weather && planResult.amusement_info.weather.length > 0" class="info-card">
					<h4>🌤️ 天气预报</h4>
					<div class="weather-list">
						<div v-for="(day, idx) in planResult.amusement_info.weather" :key="idx" class="weather-item">
							<div class="weather-date">{{ day.date }}</div>
							<div class="weather-desc">{{ day.weather_desc }}</div>
							<div class="weather-temp" v-if="day.temperature_high && day.temperature_low">
								{{ day.temperature_low }}°C ~ {{ day.temperature_high }}°C
							</div>
						</div>
					</div>
				</div>

				<!-- 每日详细行程 -->
				<div v-if="planResult.amusement_info.daily_itinerary && planResult.amusement_info.daily_itinerary.length > 0" class="info-card daily-itinerary-section">
					<h4>📅 每日详细行程</h4>
					<div class="daily-itinerary-list">
						<div v-for="(dayPlan, idx) in planResult.amusement_info.daily_itinerary" :key="idx" class="daily-itinerary-item">
							<div class="day-header">
								<span class="day-number">第{{ dayPlan.day }}天</span>
								<span class="day-date">{{ dayPlan.date }}</span>
							</div>
							<div class="day-content">
								<div v-if="dayPlan.morning" class="time-slot">
									<div class="time-label">🌅 上午</div>
									<div class="time-content">{{ dayPlan.morning }}</div>
								</div>
								<div v-if="dayPlan.afternoon" class="time-slot">
									<div class="time-label">☀️ 下午</div>
									<div class="time-content">{{ dayPlan.afternoon }}</div>
								</div>
								<div v-if="dayPlan.evening" class="time-slot">
									<div class="time-label">🌙 晚上</div>
									<div class="time-content">{{ dayPlan.evening }}</div>
								</div>
								<div v-if="dayPlan.meals && dayPlan.meals.length > 0" class="meals-section">
									<div class="meals-label">🍽️ 餐饮安排</div>
									<ul class="meals-list">
										<li v-for="(meal, mealIdx) in dayPlan.meals" :key="mealIdx">{{ meal }}</li>
									</ul>
								</div>
								<div v-if="dayPlan.pois && dayPlan.pois.length > 0" class="day-pois">
									<div class="pois-label">📍 涉及景点/POI</div>
									<div class="pois-grid">
										<div v-for="(poi, poiIdx) in dayPlan.pois" :key="poiIdx" class="day-poi-item">
											<span class="poi-name-small">{{ poi.name }}</span>
											<span v-if="poi.rating" class="poi-rating-small">⭐{{ poi.rating }}</span>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- 景点信息 -->
				<div v-if="planResult.amusement_info.attractions && planResult.amusement_info.attractions.length > 0" class="info-card">
					<h4>🎯 主要景点</h4>
					<div class="poi-list">
						<div v-for="(poi, idx) in planResult.amusement_info.attractions.slice(0, 5)" :key="idx" class="poi-item">
							<div class="poi-name">{{ poi.name }}</div>
							<div v-if="poi.rating" class="poi-rating">⭐ {{ poi.rating }}</div>
							<div v-if="poi.address" class="poi-address">📍 {{ poi.address }}</div>
							<div v-if="poi.description" class="poi-desc">{{ poi.description }}</div>
						</div>
					</div>
				</div>

				<!-- 餐厅推荐 -->
				<div v-if="planResult.amusement_info.restaurants && planResult.amusement_info.restaurants.length > 0" class="info-card">
					<h4>🍽️ 餐厅推荐</h4>
					<div class="poi-list">
						<div v-for="(poi, idx) in planResult.amusement_info.restaurants.slice(0, 5)" :key="idx" class="poi-item">
							<div class="poi-name">{{ poi.name }}</div>
							<div v-if="poi.rating" class="poi-rating">⭐ {{ poi.rating }}</div>
							<div v-if="poi.avg_cost" class="poi-cost">人均：¥{{ poi.avg_cost }}</div>
							<div v-if="poi.address" class="poi-address">📍 {{ poi.address }}</div>
						</div>
					</div>
				</div>

				<!-- 夜生活 -->
				<div v-if="planResult.amusement_info.bars_nightlife && planResult.amusement_info.bars_nightlife.length > 0" class="info-card">
					<h4>🌃 酒吧与夜生活</h4>
					<div class="poi-list">
						<div v-for="(poi, idx) in planResult.amusement_info.bars_nightlife.slice(0, 5)" :key="idx" class="poi-item">
							<div class="poi-name">{{ poi.name }}</div>
							<div v-if="poi.rating" class="poi-rating">⭐ {{ poi.rating }}</div>
							<div v-if="poi.opening_hours" class="poi-hours">⏰ {{ poi.opening_hours }}</div>
							<div v-if="poi.address" class="poi-address">📍 {{ poi.address }}</div>
						</div>
					</div>
				</div>

				<!-- 预算明细 -->
				<div v-if="planResult.amusement_info.budget_breakdown" class="info-card">
					<h4>💰 预算明细</h4>
					<div class="budget-list">
						<div v-if="planResult.amusement_info.budget_breakdown.transportation" class="budget-item">
							<span>交通费用：</span>
							<span>¥{{ planResult.amusement_info.budget_breakdown.transportation }}</span>
						</div>
						<div v-if="planResult.amusement_info.budget_breakdown.accommodation" class="budget-item">
							<span>住宿费用：</span>
							<span>¥{{ planResult.amusement_info.budget_breakdown.accommodation }}</span>
						</div>
						<div v-if="planResult.amusement_info.budget_breakdown.meals" class="budget-item">
							<span>餐饮费用：</span>
							<span>¥{{ planResult.amusement_info.budget_breakdown.meals }}</span>
						</div>
						<div v-if="planResult.amusement_info.budget_breakdown.attractions" class="budget-item">
							<span>景点门票：</span>
							<span>¥{{ planResult.amusement_info.budget_breakdown.attractions }}</span>
						</div>
						<div v-if="planResult.amusement_info.budget_breakdown.entertainment" class="budget-item">
							<span>娱乐费用：</span>
							<span>¥{{ planResult.amusement_info.budget_breakdown.entertainment }}</span>
						</div>
						<div class="budget-item total">
							<span>总计：</span>
							<span>¥{{ planResult.amusement_info.budget_breakdown.total }}</span>
						</div>
					</div>
				</div>

				<!-- 旅行贴士 -->
				<div v-if="planResult.amusement_info.tips && planResult.amusement_info.tips.length > 0" class="info-card">
					<h4>💡 旅行贴士</h4>
					<ul class="tips-list">
						<li v-for="(tip, idx) in planResult.amusement_info.tips" :key="idx">{{ tip }}</li>
					</ul>
				</div>
			</div>

			<!-- 反馈调整区域 -->
			<div v-if="planResult && !needIntervention" class="feedback-section">
				<div class="info-card feedback-card">
					<h4>💬 对计划有想法？</h4>
					<p class="feedback-hint">如果您对这个计划有任何想法或建议，请告诉我们，我们会根据您的反馈进行调整。</p>
					<div class="feedback-input">
						<textarea
							v-model="feedbackText"
							rows="3"
							placeholder="例如：酒店太贵了，换个便宜点的；或者：这个景点不去，换成其他地方..."
							class="feedback-textarea"
						/>
					</div>
					<button
						type="button"
						@click="onFeedbackSubmit"
						:disabled="feedbackLoading || !feedbackText.trim()"
						class="feedback-button"
					>
						{{ feedbackLoading ? '调整中...' : '根据反馈调整计划' }}
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
.assistant {
	max-width: 860px;
	margin: 0 auto;
	padding: 24px 16px;
	background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
	min-height: 100vh;
	border-radius: 0;
}

.assistant h1 {
	font-size: 28px;
	margin-bottom: 20px;
	color: white;
	text-align: center;
	text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
	font-weight: 700;
	letter-spacing: 1px;
}

.assistant-form {
	display: grid;
	grid-template-columns: 1fr;
	gap: 14px;
	margin-bottom: 20px;
	background: white;
	border-radius: 16px;
	padding: 28px;
	box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
	animation: slideIn 0.4s ease-out;
}

@keyframes slideIn {
	from {
		opacity: 0;
		transform: translateY(-20px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

.field {
	display: flex;
	flex-direction: column;
}

label {
	font-weight: 600;
	margin-bottom: 8px;
	color: #374151;
	font-size: 14px;
	transition: color 0.2s;
}

input, textarea, button {
	font-size: 14px;
}

input, textarea {
	padding: 12px 14px;
	border: 2px solid #e5e7eb;
	border-radius: 10px;
	outline: none;
	transition: all 0.3s ease;
	background: #f9fafb;
}

input:focus, textarea:focus {
	border-color: #667eea;
	background: white;
	box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

input:hover, textarea:hover {
	border-color: #a5b4fc;
}

button {
	padding: 12px 20px;
	border: none;
	background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
	color: white;
	border-radius: 10px;
	cursor: pointer;
	font-weight: 600;
	font-size: 15px;
	transition: all 0.3s ease;
	box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

button:hover:not(:disabled) {
	transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

button:active:not(:disabled) {
	transform: translateY(0);
	box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

button:disabled {
	opacity: 0.6;
	cursor: not-allowed;
	transform: none;
}

.error {
	color: #ef4444;
	margin: 12px 0;
	background: #fef2f2;
	padding: 14px 18px;
	border-radius: 10px;
	border-left: 4px solid #ef4444;
	font-weight: 500;
	box-shadow: 0 2px 8px rgba(239, 68, 68, 0.15);
	animation: shake 0.4s ease-in-out;
}

@keyframes shake {
	0%, 100% { transform: translateX(0); }
	25% { transform: translateX(-5px); }
	75% { transform: translateX(5px); }
}

/* 人工介入样式 */
.intervention-panel {
	background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%);
	border: 2px solid #667eea;
	border-radius: 16px;
	padding: 24px;
	margin-bottom: 20px;
	box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
	animation: slideIn 0.4s ease-out;
}

.intervention-panel h2 {
	color: #667eea;
	margin-bottom: 14px;
	font-size: 20px;
	font-weight: 700;
}

.intervention-message {
	font-size: 16px;
	color: #334155;
	margin-bottom: 18px;
	line-height: 1.6;
	background: rgba(102, 126, 234, 0.08);
	padding: 14px 16px;
	border-radius: 8px;
	border-left: 4px solid #667eea;
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
	padding: 14px 18px;
	background: white;
	border: 2px solid #e2e8f0;
	border-radius: 10px;
	margin-bottom: 10px;
	cursor: pointer;
	transition: all 0.3s ease;
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.option-item:hover {
	border-color: #667eea;
	transform: translateX(4px);
	box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.option-item.selected {
	border-color: #667eea;
	background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
	box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
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

.text-input-field {
	margin-top: 16px;
}

.input-hint {
	font-size: 12px;
	color: #64748b;
	margin-top: 6px;
	margin-bottom: 0;
	font-style: italic;
}

.intervention-actions {
	margin-top: 16px;
}

/* 结果展示样式 */
.result {
	margin-top: 24px;
	background: white;
	border-radius: 16px;
	padding: 28px;
	box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
	animation: fadeIn 0.5s ease-out;
}

@keyframes fadeIn {
	from {
		opacity: 0;
		transform: translateY(20px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

.result h2 {
	font-size: 24px;
	color: #667eea;
	margin-bottom: 24px;
	border-bottom: 3px solid #667eea;
	padding-bottom: 10px;
	font-weight: 700;
}

.result-section {
	margin-bottom: 24px;
}

.result-section h3 {
	font-size: 19px;
	color: #667eea;
	margin-bottom: 18px;
	display: flex;
	align-items: center;
	gap: 8px;
	font-weight: 700;
}

.result-section > ul {
	background: #f1f5f9;
	padding: 16px 16px 16px 36px;
	border-radius: 8px;
	margin: 0;
	list-style: decimal;
}

.result-section > ul li {
	margin-bottom: 8px;
	color: #475569;
	line-height: 1.6;
}

/* 信息卡片样式 */
.info-card {
	background: #ffffff;
	border: 2px solid #e2e8f0;
	border-radius: 14px;
	padding: 22px;
	margin-bottom: 18px;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	transition: all 0.3s ease;
}

.info-card:hover {
	box-shadow: 0 6px 20px rgba(102, 126, 234, 0.12);
	border-color: #c7d2fe;
}

.info-card h4 {
	font-size: 17px;
	color: #667eea;
	margin-bottom: 18px;
	display: flex;
	align-items: center;
	gap: 8px;
	border-bottom: 2px solid #e0e7ff;
	padding-bottom: 10px;
	font-weight: 700;
}

.info-card h5 {
	font-size: 14px;
	color: #475569;
	margin: 16px 0 12px 0;
}

/* 基本信息行 */
.info-row {
	display: flex;
	margin-bottom: 10px;
	line-height: 1.6;
}

.info-row .label {
	font-weight: 600;
	color: #64748b;
	min-width: 100px;
}

.info-row.summary {
	flex-direction: column;
}

.info-row.summary .label {
	margin-bottom: 4px;
}

/* 火车票列表 */
.train-list {
	display: grid;
	gap: 12px;
}

.train-item {
	display: flex;
	gap: 14px;
	padding: 14px;
	background: linear-gradient(135deg, #f8fafc 0%, #f0f9ff 100%);
	border-radius: 10px;
	border: 2px solid #e2e8f0;
	transition: all 0.3s ease;
}

.train-item:hover {
	border-color: #667eea;
	box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
	transform: translateY(-2px);
}

.train-no {
	font-size: 19px;
	font-weight: bold;
	color: #667eea;
	min-width: 90px;
}

.train-details {
	flex: 1;
	font-size: 14px;
	color: #475569;
	line-height: 1.6;
}

/* 酒店列表 */
.hotel-list {
	display: grid;
	gap: 12px;
}

.hotel-item {
	padding: 16px;
	background: linear-gradient(135deg, #fff7ed 0%, #fef3c7 100%);
	border-radius: 10px;
	border: 2px solid #fde68a;
	transition: all 0.3s ease;
}

.hotel-item:hover {
	box-shadow: 0 6px 16px rgba(251, 191, 36, 0.2);
	transform: translateY(-2px);
	border-color: #fbbf24;
}

.hotel-name {
	font-size: 17px;
	font-weight: 700;
	color: #78350f;
	margin-bottom: 10px;
}

.hotel-details {
	display: flex;
	gap: 12px;
	font-size: 13px;
	color: #64748b;
	margin-bottom: 6px;
}

.hotel-address {
	font-size: 13px;
	color: #64748b;
}

/* 天气列表 */
.weather-list {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
	gap: 12px;
}

.weather-item {
	padding: 14px;
	background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
	border-radius: 10px;
	text-align: center;
	border: 2px solid #bae6fd;
	transition: all 0.3s ease;
}

.weather-item:hover {
	transform: translateY(-3px);
	box-shadow: 0 6px 16px rgba(14, 165, 233, 0.25);
	border-color: #0ea5e9;
}

.weather-date {
	font-size: 14px;
	color: #0369a1;
	margin-bottom: 8px;
	font-weight: 700;
}

.weather-desc {
	font-size: 15px;
	color: #0c4a6e;
	margin-bottom: 4px;
}

.weather-temp {
	font-size: 13px;
	color: #0c4a6e;
}

/* POI列表（景点/餐厅/酒吧） */
.poi-list {
	display: grid;
	gap: 12px;
}

.poi-item {
	padding: 16px;
	background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
	border-radius: 10px;
	border: 2px solid #fde047;
	transition: all 0.3s ease;
}

.poi-item:hover {
	box-shadow: 0 6px 16px rgba(251, 191, 36, 0.25);
	transform: translateY(-2px);
	border-color: #fbbf24;
}

.poi-name {
	font-size: 16px;
	font-weight: 700;
	color: #78350f;
	margin-bottom: 8px;
}

.poi-rating, .poi-cost, .poi-hours {
	font-size: 13px;
	color: #92400e;
	margin-bottom: 4px;
}

.poi-address {
	font-size: 12px;
	color: #a16207;
	margin-top: 6px;
}

.poi-desc {
	font-size: 13px;
	color: #92400e;
	margin-top: 8px;
	line-height: 1.5;
}

/* 预算列表 */
.budget-list {
	display: grid;
	gap: 10px;
}

.budget-item {
	display: flex;
	justify-content: space-between;
	padding: 12px 16px;
	background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
	border-radius: 8px;
	font-size: 14px;
	color: #166534;
	border: 2px solid #bbf7d0;
	transition: all 0.3s ease;
	font-weight: 600;
}

.budget-item:hover {
	box-shadow: 0 4px 12px rgba(34, 197, 94, 0.2);
	transform: translateX(4px);
}

.budget-item.total {
	background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
	font-weight: 800;
	font-size: 17px;
	border: 3px solid #22c55e;
	box-shadow: 0 4px 16px rgba(34, 197, 94, 0.25);
}

/* 贴士列表 */
.tips-list {
	list-style: none;
	padding: 0;
	margin: 0;
}

.tips-list li {
	padding: 12px 16px;
	margin-bottom: 10px;
	background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
	border-left: 4px solid #ef4444;
	border-radius: 8px;
	color: #991b1b;
	font-size: 14px;
	line-height: 1.6;
	font-weight: 500;
	transition: all 0.3s ease;
}

.tips-list li:hover {
	box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
	transform: translateX(4px);
}

.local-transport {
	margin-top: 16px;
}

.local-transport p {
	padding: 14px 16px;
	background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
	border-radius: 10px;
	color: #475569;
	line-height: 1.6;
	margin: 10px 0 0 0;
	border: 2px solid #cbd5e1;
	font-weight: 500;
}

/* 每日详细行程样式 */
.daily-itinerary-section {
	background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
	border: 3px solid #0ea5e9;
	box-shadow: 0 8px 24px rgba(14, 165, 233, 0.2);
}

.daily-itinerary-list {
	display: grid;
	gap: 16px;
}

.daily-itinerary-item {
	background: white;
	border-radius: 14px;
	overflow: hidden;
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
	border: 2px solid #e0f2fe;
	transition: all 0.3s ease;
}

.daily-itinerary-item:hover {
	box-shadow: 0 6px 24px rgba(14, 165, 233, 0.2);
	transform: translateY(-2px);
}

.day-header {
	background: linear-gradient(90deg, #0ea5e9 0%, #06b6d4 100%);
	color: white;
	padding: 14px 18px;
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.day-number {
	font-size: 19px;
	font-weight: 800;
	letter-spacing: 0.5px;
}

.day-date {
	font-size: 15px;
	opacity: 0.95;
	font-weight: 500;
}

.day-content {
	padding: 18px;
}

.time-slot {
	margin-bottom: 16px;
	padding: 14px;
	background: linear-gradient(135deg, #f8fafc 0%, #f0f9ff 100%);
	border-radius: 10px;
	border-left: 4px solid #0ea5e9;
	transition: all 0.3s ease;
}

.time-slot:hover {
	box-shadow: 0 4px 12px rgba(14, 165, 233, 0.15);
}

.time-label {
	font-size: 14px;
	font-weight: 600;
	color: #0369a1;
	margin-bottom: 6px;
}

.time-content {
	font-size: 14px;
	color: #334155;
	line-height: 1.6;
}

.meals-section {
	margin-top: 12px;
	padding: 12px;
	background: #fef3c7;
	border-radius: 8px;
	border-left: 3px solid #f59e0b;
}

.meals-label {
	font-size: 14px;
	font-weight: 600;
	color: #92400e;
	margin-bottom: 8px;
}

.meals-list {
	list-style: none;
	padding: 0;
	margin: 0;
}

.meals-list li {
	font-size: 13px;
	color: #78350f;
	padding: 4px 0;
	padding-left: 16px;
	position: relative;
}

.meals-list li::before {
	content: "•";
	position: absolute;
	left: 0;
	color: #f59e0b;
	font-weight: bold;
}

.day-pois {
	margin-top: 12px;
	padding: 12px;
	background: #f0fdf4;
	border-radius: 8px;
	border-left: 3px solid #10b981;
}

.pois-label {
	font-size: 14px;
	font-weight: 600;
	color: #065f46;
	margin-bottom: 8px;
}

.pois-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
	gap: 8px;
}

.day-poi-item {
	display: flex;
	flex-direction: column;
	gap: 2px;
	padding: 8px;
	background: white;
	border-radius: 6px;
	border: 1px solid #d1fae5;
}

.poi-name-small {
	font-size: 13px;
	color: #065f46;
	font-weight: 500;
}

.poi-rating-small {
	font-size: 11px;
	color: #059669;
}

/* 反馈调整区域样式 */
.feedback-section {
	margin-top: 24px;
}

.feedback-card {
	background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
	border: 2px solid #f59e0b;
}

.feedback-card h4 {
	color: #92400e;
	border-bottom-color: #fbbf24;
}

.feedback-hint {
	font-size: 14px;
	color: #78350f;
	margin-bottom: 16px;
	line-height: 1.6;
}

.feedback-input {
	margin-bottom: 16px;
}

.feedback-textarea {
	width: 100%;
	padding: 12px 14px;
	border: 2px solid #fbbf24;
	border-radius: 8px;
	font-size: 14px;
	font-family: inherit;
	resize: vertical;
	min-height: 80px;
	transition: border-color 0.2s;
}

.feedback-textarea:focus {
	outline: none;
	border-color: #f59e0b;
	box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.2);
}

.feedback-button {
	width: 100%;
	padding: 12px 14px;
	background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
	color: white;
	border: none;
	border-radius: 8px;
	font-size: 15px;
	font-weight: 600;
	cursor: pointer;
	transition: all 0.2s;
}

.feedback-button:hover:not(:disabled) {
	background: linear-gradient(90deg, #d97706 0%, #b45309 100%);
	transform: translateY(-1px);
	box-shadow: 0 4px 12px rgba(217, 119, 6, 0.3);
}

.feedback-button:active:not(:disabled) {
	transform: translateY(0);
}

.feedback-button:disabled {
	opacity: 0.6;
	cursor: not-allowed;
	transform: none;
}
</style>


