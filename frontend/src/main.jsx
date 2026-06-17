import React from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileText,
  FileVideo,
  Gauge,
  Loader2,
  MessageSquareText,
  PlayCircle,
  RefreshCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const statusLabels = {
  uploaded: "Subido",
  processing: "Procesando",
  ready: "Listo",
  failed: "Falló",
};

const stageLabels = {
  queued: "En cola",
  starting: "Iniciando",
  extracting_audio: "Extrayendo audio",
  transcribing: "Transcribiendo",
  indexing: "Indexando",
  ready: "Listo",
  failed: "Falló",
  interrupted: "Interrumpido",
};

const manualStatusLabels = {
  queued: "En cola",
  processing: "Generando",
  ready: "Listo",
  failed: "Falló",
};

function cx(...classes) {
  return classes.filter(Boolean).join(" ");
}

function formatSeconds(seconds) {
  if (seconds === null || seconds === undefined) return "Sin duración";
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatDate(value) {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-BO", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
  }).format(new Date(value));
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail = payload?.detail || `Error ${response.status}`;
    throw new Error(detail);
  }
  return payload;
}

function StatusPill({ status, stage }) {
  const label = stageLabels[stage] || manualStatusLabels[status] || statusLabels[status] || "Sin estado";
  return (
    <span className={cx("status-pill", status)}>
      <span className="status-dot" />
      {label}
    </span>
  );
}

function ProgressBar({ value = 0 }) {
  const progress = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div className="progress-shell" aria-label={`Progreso ${progress}%`}>
      <div className="progress-fill" style={{ width: `${progress}%` }} />
    </div>
  );
}

function EmptyState({ icon: Icon, title, body }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={22} />
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function MarkdownDocument({ content }) {
  const blocks = React.useMemo(() => parseMarkdown(content || ""), [content]);
  if (!content) {
    return (
      <div className="manual-document empty-document">
        <p>El contenido aparecerá aquí mientras se genera el manual.</p>
      </div>
    );
  }
  return (
    <div className="manual-document">
      {blocks.map((block, index) => {
        if (block.type === "h1") return <h1 key={index}>{renderInlineMarkdown(block.text)}</h1>;
        if (block.type === "h2") return <h2 key={index}>{renderInlineMarkdown(block.text)}</h2>;
        if (block.type === "h3") return <h3 key={index}>{renderInlineMarkdown(block.text)}</h3>;
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => <li key={itemIndex}>{renderInlineMarkdown(item)}</li>)}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={index}>
              {block.items.map((item, itemIndex) => <li key={itemIndex}>{renderInlineMarkdown(item)}</li>)}
            </ol>
          );
        }
        return <p key={index}>{renderInlineMarkdown(block.text)}</p>;
      })}
    </div>
  );
}

function parseMarkdown(content) {
  const blocks = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "p", text: paragraph.join(" ").trim() });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push(list);
      list = null;
    }
  };

  content.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }
    if (line.startsWith("# ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h1", text: line.slice(2).trim() });
      return;
    }
    if (line.startsWith("## ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h2", text: line.slice(3).trim() });
      return;
    }
    if (line.startsWith("### ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h3", text: line.slice(4).trim() });
      return;
    }
    if (line.startsWith("- ")) {
      flushParagraph();
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(line.slice(2).trim());
      return;
    }
    if (/^\d+\.\s+/.test(line)) {
      flushParagraph();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", items: [] };
      }
      list.items.push(line.replace(/^\d+\.\s+/, "").trim());
      return;
    }
    flushList();
    paragraph.push(line);
  });
  flushParagraph();
  flushList();
  return blocks;
}

function renderInlineMarkdown(text) {
  const parts = String(text).split(/(\*\*.+?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function App() {
  const [videos, setVideos] = React.useState([]);
  const [selectedId, setSelectedId] = React.useState(null);
  const [transcript, setTranscript] = React.useState([]);
  const [question, setQuestion] = React.useState("desde donde descargo la app de banca movil?");
  const [answer, setAnswer] = React.useState(null);
  const [activeTab, setActiveTab] = React.useState("assistant");
  const [loading, setLoading] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [generatingManual, setGeneratingManual] = React.useState(false);
  const [manuals, setManuals] = React.useState([]);
  const [manualMode, setManualMode] = React.useState("extractive");
  const [manualModel, setManualModel] = React.useState("llama3.1:8b");
  const [manualPreview, setManualPreview] = React.useState(null);
  const [error, setError] = React.useState("");
  const [playerError, setPlayerError] = React.useState("");
  const fileInputRef = React.useRef(null);
  const videoRef = React.useRef(null);

  const selectedVideo = videos.find((video) => video.id === selectedId) || null;
  const mediaUrl = selectedVideo ? `${API_BASE_URL}/videos/${selectedVideo.id}/media` : "";

  const loadVideos = React.useCallback(async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoading(true);
      const data = await apiRequest("/videos");
      setVideos(data);
      setSelectedId((current) => {
        if (current && data.some((video) => video.id === current)) return current;
        return data[0]?.id || null;
      });
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadManuals = React.useCallback(async (videoId, { silent = false } = {}) => {
    if (!videoId) return;
    try {
      const data = await apiRequest(`/videos/${videoId}/manuals`);
      setManuals(data);
    } catch (err) {
      if (!silent) setError(err.message);
    }
  }, []);

  React.useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  React.useEffect(() => {
    const interval = window.setInterval(() => loadVideos({ silent: true }), 4000);
    return () => window.clearInterval(interval);
  }, [loadVideos]);

  React.useEffect(() => {
    setAnswer(null);
    setTranscript([]);
    setManuals([]);
    setManualPreview(null);
    setPlayerError("");
    if (selectedId) loadManuals(selectedId, { silent: true });
  }, [selectedId]);

  React.useEffect(() => {
    if (!selectedId) return undefined;
    const interval = window.setInterval(() => loadManuals(selectedId, { silent: true }), 5000);
    return () => window.clearInterval(interval);
  }, [selectedId, loadManuals]);

  React.useEffect(() => {
    if (!selectedId) return;
    const activeManual =
      manuals.find((manual) => manual.status === "processing" || manual.status === "queued") ||
      ((manualPreview?.metadata?.status === "processing" || manualPreview?.metadata?.status === "queued")
        ? manualPreview.metadata
        : null);
    if (!activeManual) return;

    let cancelled = false;
    apiRequest(`/videos/${selectedId}/manuals/${activeManual.id}?include_content=true`)
      .then((data) => {
        if (!cancelled) setManualPreview(data);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [manuals, selectedId]);

  React.useEffect(() => {
    if (!selectedId) return;
    if (!selectedVideo || selectedVideo.status !== "ready") return;

    let cancelled = false;

    apiRequest(`/videos/${selectedId}/transcript`)
      .then((data) => {
        if (!cancelled) setTranscript(data.segments || []);
      })
      .catch(() => {
        if (!cancelled) setTranscript([]);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId, selectedVideo?.status, selectedVideo?.segment_count]);

  function seekVideoTo(seconds) {
    const player = videoRef.current;
    if (!player) return;

    const targetTime = Math.max(0, Number(seconds) || 0);
    setPlayerError("");

    const applySeek = () => {
      try {
        player.currentTime = targetTime;
      } catch {
        return;
      }
      const playAttempt = player.play();
      if (playAttempt?.catch) playAttempt.catch(() => {});
    };

    if (Number.isNaN(player.duration)) {
      player.addEventListener("loadedmetadata", applySeek, { once: true });
      player.load();
    } else {
      applySeek();
    }

    player.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    setError("");

    try {
      const metadata = await apiRequest("/videos", {
        method: "POST",
        body: formData,
      });
      setSelectedId(metadata.id);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleAsk(event) {
    event.preventDefault();
    if (!selectedVideo || !question.trim()) return;

    setLoading(true);
    setError("");
    try {
      const data = await apiRequest(`/videos/${selectedVideo.id}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.trim(),
          top_k: 5,
          min_score: 0,
        }),
      });
      setAnswer(data);
      setActiveTab("assistant");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleReindex() {
    if (!selectedVideo) return;
    setLoading(true);
    setError("");
    try {
      await apiRequest(`/videos/${selectedVideo.id}/index`, { method: "POST" });
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleReprocess() {
    if (!selectedVideo) return;
    setLoading(true);
    setError("");
    try {
      await apiRequest(`/videos/${selectedVideo.id}/process`, { method: "POST" });
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateManual() {
    if (!selectedVideo) return;

    setGeneratingManual(true);
    setError("");
    setManualPreview(null);
    try {
      const body = {
        mode: manualMode,
        format: "markdown",
        include_timestamps: true,
      };
      if (manualMode === "llm") {
        body.provider = "ollama";
        body.model = manualModel.trim() || "llama3.1:8b";
      }
      const manual = await apiRequest(`/videos/${selectedVideo.id}/manuals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setManualPreview({ metadata: manual, content: "" });
      await loadManuals(selectedVideo.id, { silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setGeneratingManual(false);
    }
  }

  async function handlePreviewManual(manual) {
    if (!selectedVideo) return;
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest(`/videos/${selectedVideo.id}/manuals/${manual.id}?include_content=true`);
      setManualPreview(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleDownloadManual(manual, format = "markdown") {
    if (!selectedVideo) return;
    window.open(`${API_BASE_URL}/videos/${selectedVideo.id}/manuals/${manual.id}/download?format=${format}`, "_blank", "noopener,noreferrer");
  }

  async function handleDelete() {
    if (!selectedVideo) return;
    const confirmed = window.confirm(`Eliminar "${selectedVideo.original_filename}"?`);
    if (!confirmed) return;

    setLoading(true);
    setError("");
    try {
      await fetch(`${API_BASE_URL}/videos/${selectedVideo.id}`, { method: "DELETE" });
      setSelectedId(null);
      setAnswer(null);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={21} />
          </div>
          <div>
            <p>BMSC AI Video</p>
            <span>Consulta capacitaciones</span>
          </div>
        </div>

        <button className="upload-zone" type="button" onClick={() => fileInputRef.current?.click()}>
          <UploadCloud size={25} />
          <strong>{uploading ? "Subiendo..." : "Cargar video"}</strong>
          <span>MP4, MKV o audio compatible</span>
        </button>
        <input ref={fileInputRef} className="hidden-input" type="file" accept="video/*,audio/*,.mkv,.mvk" onChange={handleUpload} />

        <div className="sidebar-title">
          <span>Biblioteca</span>
          <button type="button" className="icon-button" onClick={() => loadVideos()} title="Actualizar videos">
            <RefreshCcw size={16} />
          </button>
        </div>

        <div className="video-list">
          {videos.length === 0 && (
            <EmptyState
              icon={FileVideo}
              title="Sin videos"
              body="Carga una capacitación para comenzar."
            />
          )}
          {videos.map((video) => (
            <button
              type="button"
              key={video.id}
              className={cx("video-item", selectedId === video.id && "active")}
              onClick={() => setSelectedId(video.id)}
            >
              <div className="video-item-top">
                <FileVideo size={18} />
                <StatusPill status={video.status} stage={video.processing_stage} />
              </div>
              <strong>{video.original_filename}</strong>
              <span>{formatSeconds(video.duration_seconds)} · {formatDate(video.created_at)}</span>
              {video.status === "processing" && <ProgressBar value={video.processing_progress} />}
            </button>
          ))}
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">Backend local · IA opcional</span>
            <h1>Asistente de video para capacitación</h1>
          </div>
          <div className="topbar-actions">
            <div className="api-chip">
              <Database size={15} />
              {API_BASE_URL.replace(/^https?:\/\//, "")}
            </div>
            <button className="secondary-button" type="button" onClick={handleReindex} disabled={!selectedVideo || loading}>
              <RefreshCcw size={16} />
              Reindexar
            </button>
          </div>
        </header>

        {error && (
          <div className="alert">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {!selectedVideo ? (
          <section className="welcome-surface">
            <div className="welcome-copy">
              <span className="eyebrow">Listo para probar</span>
              <h2>Carga un video y consulta su contenido por minuto exacto.</h2>
              <p>La app transcribe localmente, construye un índice de búsqueda y responde con evidencia del video.</p>
              <button className="primary-button" type="button" onClick={() => fileInputRef.current?.click()}>
                <UploadCloud size={18} />
                Cargar primer video
              </button>
            </div>
            <div className="welcome-metrics">
              <div><ShieldCheck size={20} /><span>Local first</span></div>
              <div><Gauge size={20} /><span>Progreso visible</span></div>
              <div><MessageSquareText size={20} /><span>Respuesta extractiva</span></div>
            </div>
          </section>
        ) : (
          <>
            <section className="video-summary">
              <div className="summary-main">
                <div className="summary-icon">
                  <PlayCircle size={26} />
                </div>
                <div>
                  <div className="summary-title-row">
                    <h2>{selectedVideo.original_filename}</h2>
                    <StatusPill status={selectedVideo.status} stage={selectedVideo.processing_stage} />
                  </div>
                  <p>
                    {formatSeconds(selectedVideo.duration_seconds)} · {selectedVideo.segment_count} segmentos · {selectedVideo.chunk_count} fragmentos indexados
                  </p>
                </div>
              </div>

              <div className="summary-grid">
                <div className="metric-card">
                  <span>Progreso</span>
                  <strong>{Math.round(selectedVideo.processing_progress || 0)}%</strong>
                  <ProgressBar value={selectedVideo.processing_progress} />
                </div>
                <div className="metric-card">
                  <span>Avance</span>
                  <strong>{selectedVideo.transcribed_timecode || "00:00:00.000"}</strong>
                  <small>{selectedVideo.progress_updated_at ? `Actualizado ${formatDate(selectedVideo.progress_updated_at)}` : "Sin avance"}</small>
                </div>
                <div className="metric-card">
                  <span>Audio</span>
                  <strong>{selectedVideo.audio_extraction_backend || "Pendiente"}</strong>
                  <small>{selectedVideo.language ? `Idioma ${selectedVideo.language}` : "Idioma por detectar"}</small>
                </div>
              </div>

              <div className="summary-actions">
                <button className="secondary-button" type="button" onClick={handleReprocess} disabled={loading}>
                  <RefreshCcw size={16} />
                  Reprocesar
                </button>
                <button className="danger-button" type="button" onClick={handleDelete} disabled={loading}>
                  <Trash2 size={16} />
                  Eliminar
                </button>
              </div>
            </section>

            <section className="manual-surface">
              <div className="manual-header">
                <div>
                  <span className="eyebrow">Manuales</span>
                  <h3>Generador de documentos</h3>
                </div>
                <button className="icon-button light" type="button" onClick={() => loadManuals(selectedVideo.id)} title="Actualizar manuales">
                  <RefreshCcw size={16} />
                </button>
              </div>

              <div className="manual-controls">
                <div className="segmented-control">
                  <button
                    type="button"
                    className={cx(manualMode === "extractive" && "active")}
                    onClick={() => setManualMode("extractive")}
                  >
                    <FileText size={16} />
                    Sin LLM
                  </button>
                  <button
                    type="button"
                    className={cx(manualMode === "llm" && "active")}
                    onClick={() => setManualMode("llm")}
                  >
                    <Bot size={16} />
                    LLM local
                  </button>
                </div>

                {manualMode === "llm" && (
                  <input
                    className="manual-model-input"
                    value={manualModel}
                    onChange={(event) => setManualModel(event.target.value)}
                    placeholder="Modelo Ollama"
                  />
                )}

                <button
                  className="primary-button"
                  type="button"
                  onClick={handleGenerateManual}
                  disabled={selectedVideo.status !== "ready" || generatingManual}
                >
                  {generatingManual ? <Loader2 className="spin" size={17} /> : <BookOpen size={17} />}
                  Generar manual
                </button>
              </div>

              <div className="manual-list">
                {manuals.length === 0 ? (
                  <EmptyState
                    icon={BookOpen}
                    title="Sin manuales"
                    body="Genera una versión extractiva o una versión redactada con LLM local."
                  />
                ) : (
                  manuals.map((manual) => (
                    <article key={manual.id} className="manual-card">
                      <div className="manual-card-main">
                        <div className="manual-card-icon">
                          <BookOpen size={18} />
                        </div>
                        <div>
                          <strong>{manual.title}</strong>
                          <span>
                            {manual.mode === "llm" ? `LLM · ${manual.model || "modelo local"}` : "Extractivo sin LLM"}
                            {" · "}
                            {manual.section_count} secciones · {manual.word_count} palabras
                          </span>
                        </div>
                      </div>
                      <div className="manual-card-actions">
                        <StatusPill status={manual.status} stage={manualStatusLabels[manual.status]} />
                        <button className="secondary-button compact" type="button" onClick={() => handlePreviewManual(manual)} disabled={manual.status === "failed" || loading}>
                          <FileText size={15} />
                          Ver
                        </button>
                        <button className="secondary-button compact" type="button" onClick={() => handleDownloadManual(manual, "docx")} disabled={manual.status !== "ready"}>
                          <Download size={15} />
                          DOCX
                        </button>
                        <button className="secondary-button compact" type="button" onClick={() => handleDownloadManual(manual, "pdf")} disabled={manual.status !== "ready"}>
                          <Download size={15} />
                          PDF
                        </button>
                      </div>
                      {(manual.status === "processing" || manual.status === "queued") && (
                        <div className="manual-generation-status">
                          <div>
                            <span>{manual.current_section || "Preparando generación"}</span>
                            <strong>{Math.round(manual.progress || 0)}%</strong>
                          </div>
                          <ProgressBar value={manual.progress} />
                          {manual.last_generated_text && <p>{manual.last_generated_text}</p>}
                        </div>
                      )}
                      {manual.error && <p className="manual-error">{manual.error}</p>}
                    </article>
                  ))
                )}
              </div>

              {manualPreview?.metadata && (
                <div className="manual-preview">
                  <div className="manual-preview-header">
                    <div>
                      <strong>{manualPreview.metadata.filename}</strong>
                      <span>
                        {manualPreview.metadata.status === "ready"
                          ? "Vista previa renderizada"
                          : `${manualPreview.metadata.current_section || "Generando"} · ${Math.round(manualPreview.metadata.progress || 0)}%`}
                      </span>
                    </div>
                    <div className="manual-download-group">
                      <button className="secondary-button compact" type="button" onClick={() => handleDownloadManual(manualPreview.metadata, "markdown")} disabled={manualPreview.metadata.status !== "ready"}>
                        <Download size={15} />
                        MD
                      </button>
                      <button className="secondary-button compact" type="button" onClick={() => handleDownloadManual(manualPreview.metadata, "docx")} disabled={manualPreview.metadata.status !== "ready"}>
                        <Download size={15} />
                        DOCX
                      </button>
                      <button className="secondary-button compact" type="button" onClick={() => handleDownloadManual(manualPreview.metadata, "pdf")} disabled={manualPreview.metadata.status !== "ready"}>
                        <Download size={15} />
                        PDF
                      </button>
                    </div>
                  </div>
                  {(manualPreview.metadata.status === "processing" || manualPreview.metadata.status === "queued") && (
                    <div className="manual-live-strip">
                      <ProgressBar value={manualPreview.metadata.progress} />
                      <p>{manualPreview.metadata.last_generated_text || "Esperando las primeras palabras del modelo..."}</p>
                    </div>
                  )}
                  <MarkdownDocument content={manualPreview.content || ""} />
                </div>
              )}
            </section>

            <section className="player-surface">
              <div className="player-header">
                <div>
                  <span className="eyebrow">Reproductor</span>
                  <h3>Video de capacitación</h3>
                </div>
                <span>{formatSeconds(selectedVideo.duration_seconds)}</span>
              </div>

              <div className="video-frame">
                <video
                  key={selectedVideo.id}
                  ref={videoRef}
                  controls
                  preload="metadata"
                  src={mediaUrl}
                  crossOrigin="anonymous"
                  onLoadedMetadata={() => setPlayerError("")}
                  onError={() => setPlayerError("El navegador no pudo reproducir este archivo. Si es MKV o usa un codec no soportado, prueba con MP4 H.264/AAC para reproducción embebida.")}
                />
              </div>

              {playerError ? (
                <div className="inline-warning">
                  <AlertCircle size={17} />
                  <span>{playerError}</span>
                </div>
              ) : (
                <p className="player-note">Usa los botones de reproducción en las fuentes para saltar al momento exacto del video.</p>
              )}
            </section>

            <section className="workspace">
              <div className="assistant-panel">
                <div className="panel-tabs">
                  <button type="button" className={cx(activeTab === "assistant" && "active")} onClick={() => setActiveTab("assistant")}>
                    <Bot size={16} />
                    Asistente
                  </button>
                  <button type="button" className={cx(activeTab === "transcript" && "active")} onClick={() => setActiveTab("transcript")}>
                    <Search size={16} />
                    Transcripción
                  </button>
                </div>

                {activeTab === "assistant" ? (
                  <div className="assistant-content">
                    <form className="question-box" onSubmit={handleAsk}>
                      <Search size={18} />
                      <input
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        placeholder="Pregunta sobre el video..."
                        disabled={selectedVideo.status !== "ready"}
                      />
                      <button className="send-button" type="submit" disabled={selectedVideo.status !== "ready" || loading}>
                        {loading ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
                      </button>
                    </form>

                    {selectedVideo.status !== "ready" && (
                      <div className="processing-note">
                        <Clock3 size={18} />
                        <span>El video estará disponible para preguntas cuando termine la indexación.</span>
                      </div>
                    )}

                    {!answer && selectedVideo.status === "ready" && (
                      <EmptyState
                        icon={Bot}
                        title="Haz una pregunta"
                        body="El asistente responderá citando el fragmento del video donde encontró evidencia."
                      />
                    )}

                    {answer && (
                      <div className="answer-card">
                        <div className="answer-header">
                          <div>
                            <span className="eyebrow">Respuesta</span>
                            <h3>{answer.question}</h3>
                          </div>
                          <span className="confidence">{Math.round((answer.confidence || 0) * 100)}%</span>
                        </div>
                        <p>{answer.answer}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="transcript-list">
                    {transcript.length === 0 ? (
                      <EmptyState
                        icon={Search}
                        title="Transcripción no disponible"
                        body="Cuando el video esté listo, aquí verás los segmentos con timestamps."
                      />
                    ) : (
                      transcript.map((segment) => (
                        <article key={segment.id} className="transcript-row">
                          <button
                            type="button"
                            className="timestamp-button"
                            onClick={() => seekVideoTo(segment.start_seconds)}
                            title={`Reproducir desde ${segment.start_timecode}`}
                          >
                            <PlayCircle size={15} />
                            {segment.start_timecode}
                          </button>
                          <p>{segment.text}</p>
                        </article>
                      ))
                    )}
                  </div>
                )}
              </div>

              <aside className="sources-panel">
                <div className="panel-heading">
                  <h3>Fuentes</h3>
                  <span>{answer?.sources?.length || 0}</span>
                </div>
                {!answer?.sources?.length ? (
                  <EmptyState
                    icon={ArrowRight}
                    title="Sin fuentes"
                    body="Las evidencias aparecerán después de preguntar."
                  />
                ) : (
                  <div className="source-list">
                    {answer.sources.map((source) => (
                      <article key={source.id} className="source-card">
                        <div className="source-card-top">
                          <span>{source.start_timecode} - {source.end_timecode}</span>
                          <div className="source-actions">
                            <strong>{Math.round(source.score * 100)}%</strong>
                            <button
                              type="button"
                              className="source-play-button"
                              onClick={() => seekVideoTo(source.start_seconds)}
                              title={`Reproducir desde ${source.start_timecode}`}
                              aria-label={`Reproducir fuente desde ${source.start_timecode}`}
                            >
                              <PlayCircle size={16} />
                            </button>
                          </div>
                        </div>
                        <p>{source.text}</p>
                      </article>
                    ))}
                  </div>
                )}
              </aside>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
