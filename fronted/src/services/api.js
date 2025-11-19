const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000';

export async function generateTravelPlan(payload) {
	const response = await fetch(`${API_BASE}/travel`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(payload)
	});

	if (!response.ok) {
		const text = await response.text();
		throw new Error(`Request failed: ${response.status} ${text}`);
	}

	return await response.json();
}

export async function resumeTravelPlan(sessionId, interventionResponse) {
	const response = await fetch(`${API_BASE}/resume`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({
			session_id: sessionId,
			text_input: interventionResponse.text_input || null,
			selected_options: interventionResponse.selected_options || null
		})
	});

	if (!response.ok) {
		const text = await response.text();
		throw new Error(`Request failed: ${response.status} ${text}`);
	}

	return await response.json();
}


