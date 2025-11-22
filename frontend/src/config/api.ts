// API Configuration
// This file centralizes API endpoint configuration for the frontend

// Vite exposes env variables that start with VITE_ to the client
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

// Remove trailing slash if present
const baseURL = API_URL.replace(/\/$/, '')

export const config = {
  apiURL: baseURL,
  wsURL: baseURL.replace(/^http/, 'ws'), // Convert http:// to ws:// or https:// to wss://
}

// Helper to construct API endpoints
export const endpoints = {
  investigate: `${config.apiURL}/api/investigate`,
  ws: (sessionId: string) => `${config.wsURL}/api/ws/${sessionId}`,
}
