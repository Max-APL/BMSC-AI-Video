import { apiRequest } from "./apiClient";

export const listUsers = () => apiRequest("/users");

export const createUser = (payload) =>
  apiRequest("/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const updateUser = (id, payload) =>
  apiRequest(`/users/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteUser = (id) =>
  apiRequest(`/users/${id}`, {
    method: "DELETE",
  });

export const resetUserPassword = (userId) =>
  apiRequest(`/users/${userId}/reset-password`, {
    method: "POST",
  });

export const unlockUser = (userId) =>
  apiRequest(`/users/${userId}/unlock`, {
    method: "POST",
  });
