import { apiRequest } from "./apiClient";

export const listUsers = () => apiRequest("/users");

export const createUser = (payload) =>
  apiRequest("/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
