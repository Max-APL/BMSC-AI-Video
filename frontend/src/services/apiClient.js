import { API_BASE_URL } from "@/config/env";

/**
 * Central fetch wrapper.
 * Reads the bearer token from localStorage, handles 401 by clearing it,
 * and throws on non-2xx responses with the detail message from the API.
 */
export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem("bmsc_token");
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  options.headers = headers;

  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;

  if (response.status === 401) {
    localStorage.removeItem("bmsc_token");
    window.location.reload();
  }

  if (!response.ok) {
    const detail = payload?.detail || `Error ${response.status}`;
    throw new Error(detail);
  }
  return payload;
}
