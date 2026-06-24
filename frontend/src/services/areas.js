import { apiRequest } from "./apiClient";

export const listAreas = () => apiRequest("/areas");

export const createArea = (name) =>
  apiRequest("/areas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

export const createSubarea = (areaId, name) =>
  apiRequest(`/areas/${areaId}/subareas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

export const assignVideoSubarea = (videoId, subareaId) =>
  apiRequest(`/areas/videos/${videoId}/subarea?subarea_id=${subareaId}`, {
    method: "PUT",
  });
