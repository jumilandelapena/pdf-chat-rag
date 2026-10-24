/** Base URL of the backend. The Vite dev server and nginx both proxy `/api` to it. */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')
