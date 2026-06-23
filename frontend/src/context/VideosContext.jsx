import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from "react";
import { listVideos } from "@/services/videos";
import { useAuth } from "./AuthContext";

const VideosContext = createContext(null);

export function VideosProvider({ children }) {
  const { token } = useAuth();

  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [quickSearch, setQuickSearch] = useState("");

  const loadVideos = useCallback(
    async ({ silent = false } = {}) => {
      if (!token) return;
      try {
        if (!silent) setLoading(true);
        const data = await listVideos();
        setVideos(data);
        setError("");
      } catch (err) {
        if (err.message !== "Error 401") setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [token]
  );

  // Initial load
  useEffect(() => {
    if (token) loadVideos();
  }, [token, loadVideos]);

  // Polling every 4 s
  useEffect(() => {
    const interval = window.setInterval(
      () => loadVideos({ silent: true }),
      4000
    );
    return () => window.clearInterval(interval);
  }, [loadVideos]);

  const filteredQuickVideos = videos.filter((v) =>
    v.original_filename
      .toLowerCase()
      .includes(quickSearch.trim().toLowerCase())
  );

  return (
    <VideosContext.Provider
      value={{
        videos,
        loading,
        setLoading,
        error,
        setError,
        uploading,
        setUploading,
        quickSearch,
        setQuickSearch,
        filteredQuickVideos,
        loadVideos,
      }}
    >
      {children}
    </VideosContext.Provider>
  );
}

export function useVideos() {
  const ctx = useContext(VideosContext);
  if (!ctx) throw new Error("useVideos must be used inside VideosProvider");
  return ctx;
}
