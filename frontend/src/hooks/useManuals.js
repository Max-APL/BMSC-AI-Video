import { useState, useCallback, useEffect } from "react";
import {
  listManuals,
  generateManual,
  getManual,
  deleteManual,
  downloadManual,
  manualAssetsUrl,
} from "@/services/manuals";

/**
 * Manages manual state for a given video: list, polling, preview,
 * and CRUD handlers.
 */
export function useManuals(videoId, { setError, setLoading } = {}) {
  const [manuals, setManuals] = useState([]);
  const [manualMode, setManualMode] = useState("llm");
  const [manualPreview, setManualPreview] = useState(null);
  const [manualToDelete, setManualToDelete] = useState(null);
  const [generatingManual, setGeneratingManual] = useState(false);

  const loadManuals = useCallback(
    async ({ silent = false } = {}) => {
      if (!videoId) return;
      try {
        const data = await listManuals(videoId);
        setManuals(
          [...data].sort(
            (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
          )
        );
      } catch (err) {
        if (!silent && setError) setError(err.message);
      }
    },
    [videoId, setError]
  );

  // Initial load & reset when videoId changes
  useEffect(() => {
    setManuals([]);
    setManualPreview(null);
    if (videoId) loadManuals({ silent: true });
  }, [videoId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling every 5 s
  useEffect(() => {
    if (!videoId) return;
    const interval = window.setInterval(
      () => loadManuals({ silent: true }),
      5000
    );
    return () => window.clearInterval(interval);
  }, [videoId, loadManuals]);

  // Refresh preview when manual list status/progress changes
  useEffect(() => {
    if (!videoId) return;

    const trackedId =
      manualPreview?.metadata?.id ??
      manuals.find((m) => m.status === "processing" || m.status === "queued")?.id;
    if (!trackedId) return;

    const listEntry = manuals.find((m) => m.id === trackedId);
    const previewStatus = manualPreview?.metadata?.status;
    const previewProgress = manualPreview?.metadata?.progress;

    const isGenerating = listEntry
      ? listEntry.status === "processing" || listEntry.status === "queued"
      : previewStatus === "processing" || previewStatus === "queued";
    const statusChanged = listEntry && listEntry.status !== previewStatus;
    const progressChanged = listEntry && listEntry.progress !== previewProgress;

    if (!isGenerating && !statusChanged && !progressChanged) return;

    let cancelled = false;
    getManual(videoId, trackedId, true)
      .then((data) => {
        if (!cancelled) setManualPreview(data);
      })
      .catch((err) => {
        console.error("manual preview refresh failed", err);
        if (!cancelled && listEntry) {
          setManualPreview((prev) => ({
            metadata: listEntry,
            content: prev?.content ?? "",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [manuals, videoId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerateManual = useCallback(async () => {
    if (!videoId) return;
    setGeneratingManual(true);
    if (setError) setError("");
    setManualPreview(null);
    try {
      const manual = await generateManual(videoId, manualMode);
      setManualPreview({ metadata: manual, content: "" });
      await loadManuals({ silent: true });
    } catch (err) {
      if (setError) setError(err.message);
    } finally {
      setGeneratingManual(false);
    }
  }, [videoId, manualMode, setError, loadManuals]);

  const handlePreviewManual = useCallback(
    async (manual) => {
      if (!videoId) return;
      if (setLoading) setLoading(true);
      if (setError) setError("");
      try {
        const data = await getManual(videoId, manual.id, true);
        setManualPreview(data);
      } catch (err) {
        if (setError) setError(err.message);
      } finally {
        if (setLoading) setLoading(false);
      }
    },
    [videoId, setLoading, setError]
  );

  const handleDownloadManual = useCallback(
    (manual, format = "markdown") => {
      if (!videoId) return;
      downloadManual(videoId, manual.id, format);
    },
    [videoId]
  );

  const handleDeleteManual = useCallback(
    async (manual) => {
      if (!videoId) return;
      if (setLoading) setLoading(true);
      if (setError) setError("");
      try {
        await deleteManual(videoId, manual.id);
        if (manualPreview?.metadata?.id === manual.id) setManualPreview(null);
        await loadManuals({ silent: true });
        setManualToDelete(null);
      } catch (err) {
        if (setError) setError(err.message);
      } finally {
        if (setLoading) setLoading(false);
      }
    },
    [videoId, manualPreview, setLoading, setError, loadManuals]
  );

  const getAssetsUrl = useCallback(
    (manualId) => manualAssetsUrl(videoId, manualId),
    [videoId]
  );

  return {
    manuals,
    manualMode,
    setManualMode,
    manualPreview,
    setManualPreview,
    manualToDelete,
    setManualToDelete,
    generatingManual,
    loadManuals,
    handleGenerateManual,
    handlePreviewManual,
    handleDownloadManual,
    handleDeleteManual,
    getAssetsUrl,
  };
}
