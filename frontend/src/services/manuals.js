import { API_BASE_URL } from "@/config/env";
import { apiRequest } from "./apiClient";

export const listManuals = (videoId) =>
  apiRequest(`/videos/${videoId}/manuals`);

export const generateManual = (videoId, mode) => {
  const body = {
    mode,
    format: "markdown",
    include_timestamps: true,
    include_screenshots: true,
  };
  return apiRequest(`/videos/${videoId}/manuals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
};

export const getManual = (videoId, manualId, includeContent = false) =>
  apiRequest(
    `/videos/${videoId}/manuals/${manualId}${includeContent ? "?include_content=true" : ""}`
  );

export const deleteManual = (videoId, manualId) =>
  apiRequest(`/videos/${videoId}/manuals/${manualId}`, { method: "DELETE" });

/** Opens the download in a new tab. */
export const downloadManual = (videoId, manualId, format = "markdown") => {
  window.open(
    `${API_BASE_URL}/videos/${videoId}/manuals/${manualId}/download?format=${format}`,
    "_blank",
    "noopener,noreferrer"
  );
};

/** Returns the base URL for manual asset images. */
export const manualAssetsUrl = (videoId, manualId) =>
  `${API_BASE_URL}/videos/${videoId}/manuals/${manualId}/assets`;
