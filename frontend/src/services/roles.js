import { apiRequest } from "./apiClient";

export const listRoles = () => apiRequest("/roles");

export const createRole = (payload) =>
  apiRequest("/roles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const updateRole = (id, payload) =>
  apiRequest(`/roles/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
