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
  if (!res.ok) throw new Error(data.detail || "Error al iniciar sesión");
  return data.access_token;
}

/** Fetch the currently authenticated user profile. */
export async function getCurrentUser() {
  return apiRequest("/auth/me");
}
