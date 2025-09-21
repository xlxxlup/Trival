const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000';

export async function generateTravelPlan(payload) {
	const response = await fetch(`${API_BASE}/travel/plan`, {
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


