import { useState, useCallback, useEffect } from "react";
import {
  listManuals,
  generateManual,
  getManual,
  deleteManual,
  downloadManual,
  manualAssetsUrl,
} from "@/services/manuals";

const GENERATING_STATUSES = new Set(["processing", "queued"]);

function sortManuals(manuals) {
  return [...manuals].sort(
    (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
  );
}

function upsertManual(manuals, manual) {
  if (!manual) return manuals;
  const exists = manuals.some((item) => item.id === manual.id);
  const next = exists
    ? manuals.map((item) => (item.id === manual.id ? { ...item, ...manual } : item))
    : [manual, ...manuals];
  return sortManuals(next);
}

function mergeManualsWithActiveState(serverManuals, previousManuals, activeManual) {
  let next = sortManuals(serverManuals);
  const preserveIfMissing = (manual) => {
    if (!manual || !GENERATING_STATUSES.has(manual.status)) return;
    if (next.some((item) => item.id === manual.id)) return;
    next = upsertManual(next, manual);
  };

  previousManuals.forEach(preserveIfMissing);
  preserveIfMissing(activeManual);
  return next;
}

/**
 * Manages manual state for a given video: list, polling, preview,
 * and CRUD handlers.
 */
export function useManuals(videoId, { setError, setLoading } = {}) {
  const [manuals, setManuals] = useState([]);
  const [manualMode, setManualMode] = useState("llm");
  const [manualQualityMode, setManualQualityMode] = useState("quality");
  const [manualPreview, setManualPreview] = useState(null);
  const [manualToDelete, setManualToDelete] = useState(null);
  const [generatingManual, setGeneratingManual] = useState(false);

  const loadManuals = useCallback(
    async ({ silent = false } = {}) => {
      if (!videoId) return;
      try {
        const data = await listManuals(videoId);
        setManuals((prev) => mergeManualsWithActiveState(data, prev, null));
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

  // Keep only the selected in-progress manual fresh.
  useEffect(() => {
    if (!videoId || !manualPreview?.metadata?.id) return;
    if (!GENERATING_STATUSES.has(manualPreview.metadata.status)) return;

    let cancelled = false;
    const refreshPreview = async () => {
      try {
        const data = await getManual(videoId, manualPreview.metadata.id, true);
        if (cancelled) return;
        setManualPreview(data);
        setManuals((prev) => upsertManual(prev, data.metadata));
      } catch (err) {
        console.error("manual live refresh failed", err);
      }
    };

    refreshPreview();
    const interval = window.setInterval(refreshPreview, 3500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [videoId, manualPreview?.metadata?.id, manualPreview?.metadata?.status]);

  const handleGenerateManual = useCallback(async () => {
    if (!videoId) return;
    setGeneratingManual(true);
    if (setError) setError("");
    setManualPreview(null);
    try {
      const manual = await generateManual(videoId, manualMode, manualQualityMode);
      setManualPreview({ metadata: manual, content: "" });
      setManuals((prev) => upsertManual(prev, manual));
      await loadManuals({ silent: true });
    } catch (err) {
      if (setError) setError(err.message);
    } finally {
      setGeneratingManual(false);
    }
  }, [videoId, manualMode, manualQualityMode, setError, loadManuals]);

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
        setManuals((prev) => prev.filter((item) => item.id !== manual.id));
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
    manualQualityMode,
    setManualQualityMode,
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
