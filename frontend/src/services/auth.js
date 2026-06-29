import { API_BASE_URL } from "@/config/env";
import { apiRequest } from "./apiClient";

/** Obtain a JWT access token via form-encoded credentials. */
export async function login(email, password) {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const res = await fetch(`${API_BASE_URL}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail || "Error al iniciar sesión";
    const error = new Error(typeof detail === "string" ? detail : detail.message);
    error.status = res.status;
    error.detail = detail;
    throw error;
  }
  return data;
}

/** Fetch the currently authenticated user profile. */
export async function getCurrentUser() {
  return apiRequest("/auth/me");
}

export async function completeFirstLogin(payload) {
  const res = await fetch(`${API_BASE_URL}/auth/first-login/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "No se pudo cambiar la contraseña");
  return data;
}

export async function requestPasswordReset(email) {
  return apiRequest("/auth/password-reset/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(payload) {
  const res = await fetch(`${API_BASE_URL}/auth/password-reset/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "No se pudo recuperar la contraseña");
  return data;
}
