import { API_BASE_URL } from "@/config/env";
import { apiRequest } from "./apiClient";

export const listVideos = () => apiRequest("/videos");

export const getVideo = (id) => apiRequest(`/videos/${id}`);

export const uploadVideo = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest("/videos", { method: "POST", body: formData });
};

export const updateVideo = (id, payload) =>
  apiRequest(`/videos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteVideo = (id) =>
  apiRequest(`/videos/${id}`, { method: "DELETE" });

export const reprocessVideo = (id) =>
  apiRequest(`/videos/${id}/process`, { method: "POST" });

export const reindexVideo = (id) =>
  apiRequest(`/videos/${id}/index`, { method: "POST" });

export const getTranscript = (id) => apiRequest(`/videos/${id}/transcript`);

export const askVideo = (id, question) =>
  apiRequest(`/videos/${id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: question.trim(),
      top_k: 5,
      min_score: 0,
      mode: "llm",
    }),
  });

/** Returns a direct URL to stream the video (used in <video src>). */
export const mediaUrl = (id) => `${API_BASE_URL}/videos/${id}/media`;
