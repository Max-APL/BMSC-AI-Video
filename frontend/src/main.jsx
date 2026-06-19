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
  Edit2,
  FileText,
  FileVideo,
  FolderOpen,
  Gauge,
  Loader2,
  MessageSquareText,
  PlayCircle,
  RefreshCcw,
  Search,
  Send,
  ShieldCheck,
  Trash2,
  UploadCloud,
  Users,
  Shield,
  X,
  Plus
} from "lucide-react";
import bmscLogo from "./assets/bmsc-logo.png";
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

function formatDateTime(value) {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-BO", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

async function apiRequest(path, options = {}) {
  const token = localStorage.getItem("bmsc_token");
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  options.headers = headers;

  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  
  if (response.status === 401) {
    localStorage.removeItem("bmsc_token");
    window.location.reload();
  }
  
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

function MarkdownDocument({ content, assetBaseUrl = "" }) {
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
        if (block.type === "h4") return <h4 key={index}>{renderInlineMarkdown(block.text)}</h4>;
        if (block.type === "image") {
          const src = resolveManualImageUrl(assetBaseUrl, block.src);
          if (!src) return null;
          return (
            <figure className="manual-figure" key={index}>
              <img src={src} alt={block.alt || "Captura del manual"} loading="lazy" />
              {block.alt && <figcaption>{block.alt}</figcaption>}
            </figure>
          );
        }
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => <li key={itemIndex}>{renderInlineMarkdown(item)}</li>)}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={index} start={block.start || 1}>
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

  const lines = content.split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const line = rawLine.trim();
    const nextLine = (lines[index + 1] || "").trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    if (/^(={3,}|-{3,})$/.test(nextLine)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h2", text: line.replace(/^#+\s*/, "").trim() });
      index += 1;
      continue;
    }
    const imageMatch = line.match(/^!\[(.*?)\]\((.*?)\)$/);
    if (imageMatch) {
      flushParagraph();
      flushList();
      blocks.push({ type: "image", alt: imageMatch[1].trim(), src: imageMatch[2].trim() });
      continue;
    }
    if (line.startsWith("# ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h1", text: line.slice(2).trim() });
      continue;
    }
    if (line.startsWith("## ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h2", text: line.slice(3).trim() });
      continue;
    }
    if (line.startsWith("### ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h3", text: line.slice(4).trim() });
      continue;
    }
    if (line.startsWith("#### ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h4", text: line.slice(5).trim() });
      continue;
    }
    if (line.startsWith("- ") || line.startsWith("* ") || line.startsWith("+ ")) {
      flushParagraph();
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(line.slice(2).trim());
      continue;
    }
    const numberMatch = line.match(/^(\d+)\.\s+/);
    if (numberMatch) {
      flushParagraph();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", start: Number(numberMatch[1]) || 1, items: [] };
      }
      list.items.push(line.replace(/^\d+\.\s+/, "").trim());
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return blocks;
}

function resolveManualImageUrl(assetBaseUrl, src) {
  if (!assetBaseUrl || !src) return "";
  if (/^https?:\/\//i.test(src)) return src;
  const cleaned = String(src).replace(/^\/+/, "").split("/").map(encodeURIComponent).join("/");
  return `${assetBaseUrl.replace(/\/$/, "")}/${cleaned}`;
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

function Login({ onLogin }) {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email.endsWith("@bmsc.com.bo")) {
      setError("Solo se permiten correos corporativos @bmsc.com.bo");
      return;
    }
    setLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);
      const res = await fetch(`${API_BASE_URL}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error al iniciar sesión");
      onLogin(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <img className="brand-logo" src={bmscLogo} alt="Mercantil Santa Cruz" />
        <h2>Centro IA Video</h2>
        <p>Inicia sesión para gestionar el material audiovisual y los manuales operativos.</p>
        <form onSubmit={handleSubmit} className="login-form">
          <input type="email" placeholder="Correo electrónico (@bmsc.com.bo)" value={email} onChange={e => setEmail(e.target.value)} required />
          <input type="password" placeholder="Contraseña" value={password} onChange={e => setPassword(e.target.value)} required />
          {error && <div className="alert"><AlertCircle size={15}/>{error}</div>}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Iniciando..." : "Ingresar"}
          </button>
        </form>
      </div>
    </div>
  );
}

function App() {
  const [token, setToken] = React.useState(localStorage.getItem("bmsc_token") || "");
  const [currentUser, setCurrentUser] = React.useState(null);

  const [videos, setVideos] = React.useState([]);
  const [selectedId, setSelectedId] = React.useState(null);
  const [transcript, setTranscript] = React.useState([]);
  const [question, setQuestion] = React.useState("desde donde descargo la app de banca movil?");
  const [answer, setAnswer] = React.useState(null);
  const [activeTab, setActiveTab] = React.useState("assistant");
  const [activeView, setActiveView] = React.useState("dashboard");
  const [isRoleModalOpen, setIsRoleModalOpen] = React.useState(false);
  const [editingRoleId, setEditingRoleId] = React.useState(null);
  
  const closeRoleModal = () => {
    setIsRoleModalOpen(false);
    setEditingRoleId(null);
    setNewRoleName("");
    setNewRolePerms([]);
    setNewRoleAreas(["*"]);
  };
  const [quickSearch, setQuickSearch] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [generatingManual, setGeneratingManual] = React.useState(false);
  const [manuals, setManuals] = React.useState([]);
  const [manualMode, setManualMode] = React.useState("extractive");
  const [manualPreview, setManualPreview] = React.useState(null);
  const [manualToDelete, setManualToDelete] = React.useState(null);
  const [error, setError] = React.useState("");
  const [playerError, setPlayerError] = React.useState("");
  const fileInputRef = React.useRef(null);
  const videoRef = React.useRef(null);

  const [areas, setAreas] = React.useState([]);
  const [uploadSubareaId, setUploadSubareaId] = React.useState("");
  const [newAreaName, setNewAreaName] = React.useState("");
  const [newSubareaNames, setNewSubareaNames] = React.useState({});
  
  const [roles, setRoles] = React.useState([]);
  const [usersList, setUsersList] = React.useState([]);
  
  const [newRoleName, setNewRoleName] = React.useState("");
  const [newRolePerms, setNewRolePerms] = React.useState([]);
  const [newRoleAreas, setNewRoleAreas] = React.useState(["*"]);
  const [newUserEmail, setNewUserEmail] = React.useState("");
  const [newUserPass, setNewUserPass] = React.useState("");
  const [newUserRole, setNewUserRole] = React.useState("");
  
  const availablePermissions = [
    { id: "view_dashboard", label: "Ver Dashboard" },
    { id: "view_videos", label: "Ver Gestión de Videos" },
    { id: "view_library", label: "Ver Biblioteca" },
    { id: "view_organization", label: "Ver Organización" },
    { id: "view_users", label: "Ver Usuarios" },
    { id: "view_roles", label: "Ver Roles" },
    { id: "upload_video", label: "Subir Videos" },
    { id: "generate_manual", label: "Generar Manuales" },
    { id: "manage_organization", label: "Gestionar Áreas" },
    { id: "manage_users", label: "Gestionar Usuarios" },
    { id: "manage_roles", label: "Gestionar Roles" }
  ];
  
  const [editingVideo, setEditingVideo] = React.useState(null);
  const [editFilename, setEditFilename] = React.useState("");
  const [editSubarea, setEditSubarea] = React.useState("");
  
  const [videoToDelete, setVideoToDelete] = React.useState(null);
  const [selectedOrgArea, setSelectedOrgArea] = React.useState(null);
  const [selectedOrgSubarea, setSelectedOrgSubarea] = React.useState(null);
  const [libraryFilterArea, setLibraryFilterArea] = React.useState(null);
  const [libraryFilterSubarea, setLibraryFilterSubarea] = React.useState(null);

  const selectedVideo = videos.find((video) => video.id === selectedId) || null;
  const mediaUrl = selectedVideo ? `${API_BASE_URL}/videos/${selectedVideo.id}/media` : "";

  const loadVideos = React.useCallback(async ({ silent = false } = {}) => {
    if (!token) return;
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
      if (err.message !== "Error 401") setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadAreas = React.useCallback(async () => {
    if (!token) return;
    try {
      const data = await apiRequest("/areas");
      setAreas(data);
    } catch (err) {
      // ignore silently for now
    }
  }, [token]);

  const loadManuals = React.useCallback(async (videoId, { silent = false } = {}) => {
    if (!videoId || !token) return;
    try {
      const data = await apiRequest(`/videos/${videoId}/manuals`);
      setManuals(
        [...data].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
      );
    } catch (err) {
      if (!silent) setError(err.message);
    }
  }, []);

  const loadCurrentUser = React.useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) {
        if (res.status === 401) {
            setToken("");
            localStorage.removeItem("bmsc_token");
        }
        throw new Error("Error fetching user info");
      }
      const data = await res.json();
      setCurrentUser(data);
    } catch (err) {
      console.error(err);
    }
  }, [token]);

  const loadRoles = React.useCallback(async () => {
    if (!token) return;
    try {
      const data = await apiRequest("/roles");
      setRoles(data);
    } catch (err) {}
  }, [token]);

  const loadUsersList = React.useCallback(async () => {
    if (!token) return;
    try {
      const data = await apiRequest("/users");
      setUsersList(data);
    } catch (err) {}
  }, [token]);

  React.useEffect(() => {
    if (token) {
      loadCurrentUser();
      loadVideos();
      loadAreas();
      loadRoles();
      loadUsersList();
    }
  }, [loadCurrentUser, loadVideos, loadAreas, loadRoles, loadUsersList, token]);

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
      
      if (uploadSubareaId) {
        await apiRequest(`/areas/videos/${metadata.id}/subarea?subarea_id=${uploadSubareaId}`, {
          method: "PUT"
        });
      }
      
      setSelectedId(metadata.id);
      setActiveView("video");
      setActiveTab("assistant");
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
      setActiveView("video");
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
        include_screenshots: true,
      };
      if (manualMode === "llm") {
        body.provider = "llama_cpp";
      }
      const manual = await apiRequest(`/videos/${selectedVideo.id}/manuals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setManualPreview({ metadata: manual, content: "" });
      setActiveTab("manuals");
      setActiveView("video");
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
      setActiveTab("manuals");
      setActiveView("video");
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
      setActiveView("library");
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const readyCount = videos.filter((video) => video.status === "ready").length;
  const processingCount = videos.filter((video) => video.status === "processing").length;
  const failedCount = videos.filter((video) => video.status === "failed").length;
  const totalDurationSeconds = videos.reduce((total, video) => total + Number(video.duration_seconds || 0), 0);
  const totalSegments = videos.reduce((total, video) => total + Number(video.segment_count || 0), 0);
  const totalChunks = videos.reduce((total, video) => total + Number(video.chunk_count || 0), 0);
  const loadedHistory = [...videos]
    .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  const recentVideos = loadedHistory.slice(0, 5);
  const filteredQuickVideos = videos.filter((video) =>
    video.original_filename.toLowerCase().includes(quickSearch.trim().toLowerCase())
  );
  const latestManual = manuals[0] || null;
  const selectedVideoIsReady = selectedVideo?.status === "ready";

  const hasPermission = React.useCallback((perm) => {
    if (!currentUser || !currentUser.permissions) return false;
    return currentUser.permissions.includes(perm);
  }, [currentUser]);

  const viewTitles = {
    dashboard: {
      eyebrow: "Panel principal",
      title: "Centro de capacitación inteligente",
      description: "Vista general de videos cargados, procesamiento y contenido indexado.",
    },
    upload: {
      eyebrow: "Carga de video",
      title: "Ingreso de material audiovisual",
      description: "Carga nuevos videos y revisa el historial reciente de procesamiento.",
    },
    library: {
      eyebrow: "Biblioteca",
      title: "Repositorio audiovisual",
      description: "Explora todos los videos disponibles y abre la gestión individual de cada material.",
    },
    organization: {
      eyebrow: "Configuración",
      title: "Organización",
      description: "Gestiona la estructura de áreas y subáreas de la institución.",
    },
    users: {
      eyebrow: "Administración",
      title: "Usuarios",
      description: "Gestión de cuentas y accesos.",
    },
    roles: {
      eyebrow: "Seguridad",
      title: "Roles y Permisos",
      description: "Definición de permisos granulares.",
    },
    video: {
      eyebrow: "Expediente del video",
      title: selectedVideo?.original_filename || "Video seleccionado",
      description: "Reproductor, consulta con fuentes, manuales y transcripción pertenecen a este video.",
    },
  };
  const currentView = viewTitles[activeView] || viewTitles.dashboard;
  const navigationItems = [
    ...(hasPermission("view_dashboard") ? [{ id: "dashboard", label: "Panel principal", icon: Gauge }] : []),
    ...(hasPermission("view_videos") ? [{ id: "upload", label: "Gestión de videos", icon: UploadCloud }] : []),
    ...(hasPermission("view_library") ? [{ id: "library", label: "Biblioteca", icon: FileVideo, badge: videos.length }] : []),
    ...(hasPermission("view_organization") ? [{ id: "organization", label: "Organización", icon: Database }] : []),
    ...(hasPermission("view_users") ? [{ id: "users", label: "Usuarios", icon: Users }] : []),
    ...(hasPermission("view_roles") ? [{ id: "roles", label: "Roles", icon: Shield }] : [])
  ];

  function openView(viewId) {
    setActiveView(viewId);
  }

  function renderNoSelection(moduleLabel = "este módulo") {
    return (
      <section className="selection-required">
        <div className="selection-required-icon">
          <FileVideo size={24} />
        </div>
        <span className="eyebrow">Selección requerida</span>
        <h2>Selecciona un video para usar {moduleLabel}.</h2>
        <p>Elige un registro desde la biblioteca o carga un nuevo material de capacitación.</p>
        <button className="primary-button" type="button" onClick={() => openView("library")}>
          <FileVideo size={18} />
          Ir a biblioteca
        </button>
      </section>
    );
  }

  function renderVideoPlayer(className = "") {
    if (!selectedVideo) return null;
    return (
      <section className={cx("player-surface", className)}>
        <div className="player-header">
          <div>
            <span className="eyebrow">Video seleccionado</span>
            <h3>{selectedVideo.original_filename}</h3>
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
          <p className="player-note">Los botones de reproducción en fuentes y transcripción saltan a este video en el momento exacto.</p>
        )}
      </section>
    );
  }

  if (!token) {
    return <Login onLogin={(t) => { setToken(t); localStorage.setItem("bmsc_token", t); }} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src={bmscLogo} alt="Mercantil Santa Cruz" />
          <div className="brand-copy">
            <p>Centro IA Video</p>
            <span>Mercantil Santa Cruz</span>
          </div>
        </div>

        <nav className="module-nav" aria-label="Módulos administrativos">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                type="button"
                key={item.id}
                className={cx("module-nav-item", activeView === item.id && "active")}
                onClick={() => openView(item.id)}
                disabled={item.disabled}
              >
                <Icon size={18} />
                <span>{item.label}</span>
                {item.badge !== undefined && <strong>{item.badge}</strong>}
              </button>
            );
          })}
        </nav>

        <input ref={fileInputRef} className="hidden-input" type="file" accept="video/*,audio/*,.mkv,.mvk" onChange={handleUpload} />

        <div className="sidebar-title">
          <span>Biblioteca rápida</span>
          <button type="button" className="icon-button" onClick={() => loadVideos()} title="Actualizar videos">
            <RefreshCcw size={16} />
          </button>
        </div>

        <label className="quick-search">
          <Search size={15} />
          <input
            value={quickSearch}
            onChange={(event) => setQuickSearch(event.target.value)}
            placeholder="Buscar video..."
          />
        </label>

        <div className="video-list">
          {videos.length === 0 && (
            <EmptyState
              icon={FileVideo}
              title="Sin videos"
              body="Carga una capacitación para comenzar."
            />
          )}
          {videos.length > 0 && filteredQuickVideos.length === 0 && (
            <EmptyState
              icon={Search}
              title="Sin resultados"
              body="Prueba con otro nombre de video."
            />
          )}
          {filteredQuickVideos.map((video) => (
            <button
              type="button"
              key={video.id}
              className={cx("video-item", selectedId === video.id && "active")}
              onClick={() => {
                setSelectedId(video.id);
                setActiveView("video");
                setActiveTab("assistant");
              }}
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

        <div className="user-profile" style={{
          marginTop: 'auto',
          padding: '16px',
          borderTop: '1px solid var(--line)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--primary-color)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', flexShrink: 0 }}>
              {currentUser?.email?.charAt(0).toUpperCase() || "U"}
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: '13px', fontWeight: 'bold', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={currentUser?.email}>{currentUser?.email}</div>
              <div style={{ fontSize: '11px', color: 'var(--muted)' }}>{currentUser?.role}</div>
            </div>
          </div>
          <button 
            type="button" 
            className="secondary-button compact" 
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => {
              localStorage.removeItem("bmsc_token");
              setToken("");
              setCurrentUser(null);
            }}
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">{currentView.eyebrow}</span>
            <h1>{currentView.title}</h1>
            <p>{currentView.description}</p>
          </div>
          <div className="topbar-actions">
            <div className="bank-chip">
              <ShieldCheck size={15} />
              Entorno institucional
            </div>
            <div className="api-chip">
              <Database size={15} />
              {API_BASE_URL.replace(/^https?:\/\//, "")}
            </div>
            {activeView === "video" && (
              <button className="secondary-button" type="button" onClick={handleReindex} disabled={!selectedVideo || loading}>
                <RefreshCcw size={16} />
                Reindexar
              </button>
            )}
          </div>
        </header>

        {error && (
          <div className="alert">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <>
            {activeView === "dashboard" && (
              <section className="dashboard-home">
                <div className="dashboard-kpis">
                  <div>
                    <span className="eyebrow">Estado general</span>
                    <h2>Resumen operativo</h2>
                    <p>Información consolidada de todos los videos cargados en la plataforma.</p>
                  </div>
                  <div className="dashboard-kpi-grid">
                    <div className="metric-card compact-metric">
                      <span>Total videos</span>
                      <strong>{videos.length}</strong>
                      <small>{readyCount} listos para consulta</small>
                    </div>
                    <div className="metric-card compact-metric">
                      <span>En proceso</span>
                      <strong>{processingCount}</strong>
                      <small>{failedCount ? `${failedCount} con error` : "Sin errores activos"}</small>
                    </div>
                    <div className="metric-card compact-metric">
                      <span>Transcripción</span>
                      <strong>{totalSegments}</strong>
                      <small>{totalChunks} fragmentos indexados</small>
                    </div>
                    <div className="metric-card compact-metric">
                      <span>Duración</span>
                      <strong>{formatSeconds(totalDurationSeconds)}</strong>
                      <small>Material audiovisual total</small>
                    </div>
                  </div>
                </div>

                <section className="library-surface">
                  <div className="library-header">
                    <div>
                      <span className="eyebrow">Actividad reciente</span>
                      <h2>Últimos videos cargados</h2>
                      <p>Accesos rápidos al expediente de los materiales más recientes.</p>
                    </div>
                    <button className="secondary-button" type="button" onClick={() => setActiveView("library")}>
                      <FileVideo size={16} />
                      Ver biblioteca
                    </button>
                  </div>

                  <div className="history-list">
                    {recentVideos.length === 0 ? (
                      <EmptyState
                        icon={FileVideo}
                        title="Sin actividad"
                        body="Carga el primer video desde la página de carga."
                      />
                    ) : (
                      loadedHistory.map((video) => (
                        <article key={video.id} className="history-row">
                          <div>
                            <strong>{video.original_filename}</strong>
                            <span>{formatSeconds(video.duration_seconds)} · {formatDate(video.created_at)} · {video.segment_count} segmentos</span>
                          </div>
                          <StatusPill status={video.status} stage={video.processing_stage} />
                          <button
                            className="secondary-button compact"
                            type="button"
                            onClick={() => {
                              setSelectedId(video.id);
                              setActiveView("video");
                              setActiveTab("assistant");
                            }}
                          >
                            <PlayCircle size={15} />
                            Abrir
                          </button>
                        </article>
                      ))
                    )}
                  </div>
                </section>
              </section>
            )}

            {activeView === "upload" && (
              <section className="upload-page">
                {hasPermission("upload_video") ? (
                  <>
                    <div className="upload-hero">
                      <div>
                        <span className="eyebrow">Nuevo material</span>
                        <h2>Cargar video de capacitación</h2>
                        <p>El archivo quedará en el historial y luego podrá gestionarse desde su expediente individual.</p>
                      </div>
                      <button className="primary-button" type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                        <UploadCloud size={18} />
                        {uploading ? "Subiendo..." : "Seleccionar archivo"}
                      </button>
                    </div>

                    <div style={{ padding: "0 22px", marginTop: "-10px", marginBottom: "10px" }}>
                      <label style={{ display: "block", marginBottom: "6px", fontSize: "14px", fontWeight: "bold", color: "var(--ink-700)" }}>Asignar a subárea (Opcional):</label>
                      <select 
                        value={uploadSubareaId} 
                        onChange={e => setUploadSubareaId(e.target.value)}
                        style={{ padding: "8px", borderRadius: "6px", border: "1px solid var(--line)", width: "100%", maxWidth: "300px" }}
                      >
                        <option value="">Sin asignar</option>
                        {areas.map(area => (
                          <optgroup key={area.id} label={area.name}>
                            {area.subareas.map(sub => (
                              <option key={sub.id} value={sub.id}>{sub.name}</option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </div>
                  </>
                ) : (
                  <div className="upload-hero" style={{ justifyContent: "center", textAlign: "center" }}>
                    <div>
                      <span className="eyebrow">Acceso Restringido</span>
                      <h2>No tienes permisos para subir videos</h2>
                      <p>Contacta a un administrador si crees que esto es un error.</p>
                    </div>
                  </div>
                )}

                <section className="library-surface">
                  <div className="library-header">
                    <div>
                      <span className="eyebrow">Historial</span>
                      <h2>Videos cargados</h2>
                      <p>Seguimiento de los archivos ingresados y su estado de procesamiento.</p>
                    </div>
                    <button className="icon-button light" type="button" onClick={() => loadVideos()} title="Actualizar historial">
                      <RefreshCcw size={16} />
                    </button>
                  </div>

                  <div className="history-list">
                    {videos.length === 0 ? (
                      <EmptyState
                        icon={UploadCloud}
                        title="Sin cargas"
                        body="Carga un video para iniciar el historial."
                      />
                    ) : (
                      recentVideos.map((video) => (
                        <article key={video.id} className="history-row">
                          <div>
                            <strong>{video.original_filename}</strong>
                            <span>
                              {formatSeconds(video.duration_seconds)} · Cargado {formatDate(video.created_at)}
                              {video.subarea_id && (() => {
                                let subName = "";
                                areas.forEach(a => a.subareas.forEach(s => { if(s.id === video.subarea_id) subName = `${a.name} > ${s.name}`; }));
                                return subName ? ` · ${subName}` : "";
                              })()}
                            </span>
                            {video.status === "processing" && <ProgressBar value={video.processing_progress} />}
                          </div>
                          <StatusPill status={video.status} stage={video.processing_stage} />
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              className="secondary-button compact"
                              type="button"
                              onClick={() => {
                                setEditingVideo(video);
                                setEditFilename(video.original_filename);
                                setEditSubarea(video.subarea_id || "");
                              }}
                            >
                              <Edit2 size={15} /> Editar
                            </button>
                            <button
                              className="danger-button compact"
                              type="button"
                              onClick={() => setVideoToDelete(video)}
                            >
                              <Trash2 size={15} />
                            </button>
                            <button
                              className="secondary-button compact"
                              type="button"
                              onClick={() => {
                                setSelectedId(video.id);
                                setActiveView("video");
                                setActiveTab("assistant");
                              }}
                            >
                              <PlayCircle size={15} /> Abrir
                            </button>
                          </div>
                        </article>
                      ))
                    )}
                  </div>
                </section>
              </section>
            )}
            {activeView === "library" && (
              <section className="library-surface" style={{ display: "flex", gap: "24px", padding: "24px", minHeight: "calc(100vh - 40px)" }}>
                <div style={{ flex: "0 0 300px", borderRight: "1px solid var(--line)", paddingRight: "24px", overflowY: "auto" }}>
                  <div className="library-header" style={{ marginBottom: "24px" }}>
                    <div>
                      <span className="eyebrow">Navegación</span>
                      <h2>Filtros</h2>
                    </div>
                  </div>
                  
                  <div className="org-grid" style={{ gridTemplateColumns: "1fr" }}>
                    <div className="area-card" style={{ marginBottom: "16px", cursor: "pointer", borderColor: !libraryFilterArea ? "var(--green-600)" : "var(--line)" }} onClick={() => { setLibraryFilterArea(null); setLibraryFilterSubarea(null); }}>
                      <h3>Todos los videos</h3>
                    </div>

                    {areas.map(area => (
                      <div className="area-card" key={area.id} style={{ marginBottom: "16px", cursor: "pointer", borderColor: libraryFilterArea?.id === area.id ? "var(--green-600)" : "var(--line)" }} onClick={() => { setLibraryFilterArea(area); setLibraryFilterSubarea(null); }}>
                        <h3>{area.name} <span>({area.subareas.length})</span></h3>
                        <div className="subarea-list">
                          {area.subareas.map(sub => (
                            <div 
                              className="subarea-item" 
                              key={sub.id} 
                              onClick={(e) => { e.stopPropagation(); setLibraryFilterArea(area); setLibraryFilterSubarea(sub); }}
                              style={{ 
                                background: libraryFilterSubarea?.id === sub.id ? "var(--green-100)" : "var(--surface-soft)",
                                color: libraryFilterSubarea?.id === sub.id ? "var(--green-900)" : "inherit",
                                fontWeight: libraryFilterSubarea?.id === sub.id ? "bold" : "normal"
                              }}
                            >
                              {sub.name}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ flex: 1, paddingLeft: "12px", overflowY: "auto" }}>
                  <div className="library-header" style={{ marginBottom: "24px" }}>
                    <div>
                      <span className="eyebrow">{libraryFilterArea ? libraryFilterArea.name : "Gestión de archivos"}</span>
                      <h2>{libraryFilterSubarea ? libraryFilterSubarea.name : (libraryFilterArea ? "Todos los videos del área" : "Biblioteca de capacitaciones")}</h2>
                      <p>Administra los materiales disponibles para consulta, documentación y revisión operativa.</p>
                    </div>
                    <div className="library-mini-stats" aria-label="Resumen de biblioteca">
                      <span><strong>{videos.filter(v => {
                        if (libraryFilterSubarea) return v.subarea_id === libraryFilterSubarea.id;
                        if (libraryFilterArea) {
                          const subIds = libraryFilterArea.subareas.map(s => s.id);
                          return subIds.includes(v.subarea_id);
                        }
                        return true;
                      }).length}</strong> Total</span>
                    </div>
                  </div>

                  <div className="library-grid">
                    {videos
                      .filter(v => {
                        if (libraryFilterSubarea) return v.subarea_id === libraryFilterSubarea.id;
                        if (libraryFilterArea) {
                          const subIds = libraryFilterArea.subareas.map(s => s.id);
                          return subIds.includes(v.subarea_id);
                        }
                        return true;
                      })
                      .map((video) => (
                      <article key={video.id} className={cx("library-card", selectedId === video.id && "active")} style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0, gap: 0 }}>
                        <div style={{ backgroundColor: 'var(--surface-soft)', padding: '24px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', borderBottom: '1px solid var(--line)', position: 'relative' }}>
                          <div style={{ background: 'white', padding: '12px', borderRadius: '50%', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
                            <PlayCircle size={32} color="var(--green-600)" />
                          </div>
                          <div style={{ position: 'absolute', top: '12px', right: '12px' }}>
                            <StatusPill status={video.status} stage={video.processing_stage} />
                          </div>
                          <div style={{ position: 'absolute', bottom: '12px', right: '12px', background: 'rgba(0,0,0,0.6)', color: 'white', padding: '2px 6px', borderRadius: '4px', fontSize: '12px', fontWeight: 'bold' }}>
                            {formatSeconds(video.duration_seconds)}
                          </div>
                        </div>

                        <div style={{ padding: '16px', minWidth: 0 }}>
                          <h3 style={{ margin: '0 0 12px 0', fontSize: '15px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--ink-900)' }} title={video.original_filename}>
                            {video.original_filename}
                          </h3>
                          
                          <div style={{ fontSize: '13px', color: 'var(--muted)', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Clock3 size={14} /> {formatDate(video.created_at)}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Database size={14} /> 
                              {video.subarea_id ? (() => {
                                let subName = "Sin área";
                                areas.forEach(a => a.subareas.forEach(s => { if(s.id === video.subarea_id) subName = `${a.name} > ${s.name}`; }));
                                return subName;
                              })() : "Sin área asignada"}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <FileText size={14} /> {video.segment_count} segmentos indexados
                            </div>
                          </div>

                          {video.status === "processing" && <ProgressBar value={video.processing_progress} />}
                          
                          <button
                            className="secondary-button"
                            style={{ width: '100%', justifyContent: 'center', marginTop: video.status === "processing" ? '12px' : '0' }}
                            type="button"
                            onClick={() => {
                              setSelectedId(video.id);
                              setActiveView("video");
                              setActiveTab("assistant");
                            }}
                          >
                            <FolderOpen size={16} />
                            Abrir expediente
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {activeView === "organization" && (
              <section className="library-surface">
                <div className="library-header">
                  <div>
                    <span className="eyebrow">Configuración</span>
                    <h2>Estructura Organizacional</h2>
                    <p>Gestiona áreas y subáreas para clasificar el contenido de la institución.</p>
                  </div>
                </div>

                <div className="library-grid" style={{ marginTop: '24px' }}>
                  <div className="area-card" style={{ background: "var(--green-50)", borderStyle: "dashed", borderColor: "var(--green-300)" }}>
                    <h3 style={{ color: "var(--green-900)" }}>Nueva Área</h3>
                    <form className="add-form" onSubmit={async (e) => {
                      e.preventDefault();
                      if (!newAreaName.trim()) return;
                      setLoading(true);
                      try {
                        await apiRequest("/areas", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ name: newAreaName.trim() })
                        });
                        setNewAreaName("");
                        await loadAreas();
                      } catch (err) {
                        setError(err.message);
                      } finally {
                        setLoading(false);
                      }
                    }}>
                      <input placeholder="Nombre del área..." value={newAreaName} onChange={e => setNewAreaName(e.target.value)} disabled={loading} />
                      <button className="primary-button compact" type="submit" disabled={loading || !newAreaName.trim()}>Crear</button>
                    </form>
                  </div>

                  {areas.map(area => (
                    <div className="area-card" key={area.id} style={{ borderColor: "var(--line)" }}>
                      <h3>{area.name} <span>({area.subareas.length})</span></h3>
                      <div className="subarea-list">
                        {area.subareas.map(sub => (
                          <div 
                            className="subarea-item" 
                            key={sub.id} 
                            style={{ background: "var(--surface-soft)" }}
                          >
                            {sub.name}
                          </div>
                        ))}
                      </div>
                      <form className="add-form" onSubmit={async (e) => {
                        e.preventDefault();
                        const subName = newSubareaNames[area.id] || "";
                        if (!subName.trim()) return;
                        setLoading(true);
                        try {
                          await apiRequest(`/areas/${area.id}/subareas`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name: subName.trim() })
                          });
                          setNewSubareaNames(prev => ({ ...prev, [area.id]: "" }));
                          await loadAreas();
                        } catch (err) {
                          setError(err.message);
                        } finally {
                          setLoading(false);
                        }
                      }}>
                        <input 
                          placeholder="Nueva subárea..." 
                          value={newSubareaNames[area.id] || ""} 
                          onChange={e => setNewSubareaNames(prev => ({ ...prev, [area.id]: e.target.value }))} 
                          disabled={loading} 
                        />
                        <button className="secondary-button compact" type="submit" disabled={loading || !newSubareaNames[area.id]?.trim()}>Añadir</button>
                      </form>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {activeView === "roles" && (
              <section className="organization-page">
                {/* Clean Top Action Bar */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                  <div>
                    <h2 style={{ margin: 0, color: 'var(--green-950)' }}>Roles y Permisos</h2>
                    <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: '14px' }}>
                      Gestiona el nivel de acceso y las áreas permitidas para los usuarios de la plataforma.
                    </p>
                  </div>
                  <button className="primary-button" onClick={() => {
                    setEditingRoleId(null);
                    setNewRoleName("");
                    setNewRolePerms([]);
                    setNewRoleAreas(["*"]);
                    setIsRoleModalOpen(true);
                  }}>
                    <Plus size={18} />
                    Añadir Rol
                  </button>
                </div>

                {/* Grid of existing roles */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
                  {roles.map(r => {
                    const isGlobal = r.allowed_areas && r.allowed_areas.includes("*");
                    return (
                      <div className="role-card-premium" key={r.id}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--line)', paddingBottom: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Shield size={20} color="var(--green-800)" />
                            <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--ink-900)' }}>{r.name}</h3>
                          </div>
                          {isGlobal ? (
                            <span style={{ fontSize: '10px', background: 'var(--green-700)', color: 'white', padding: '4px 8px', borderRadius: '12px', fontWeight: 'bold' }}>Acceso Global</span>
                          ) : (
                            <span style={{ fontSize: '10px', background: 'var(--gold-600)', color: 'white', padding: '4px 8px', borderRadius: '12px', fontWeight: 'bold' }}>Por Áreas</span>
                          )}
                          <button 
                            className="icon-button" 
                            style={{ width: '28px', height: '28px', marginLeft: 'auto' }} 
                            onClick={() => {
                              setEditingRoleId(r.id);
                              setNewRoleName(r.name);
                              setNewRolePerms(r.permissions);
                              setNewRoleAreas(r.allowed_areas || ["*"]);
                              setIsRoleModalOpen(true);
                            }}
                            title="Editar Rol"
                          >
                            <Edit2 size={14} />
                          </button>
                        </div>
                        
                        <div>
                          <span style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 'bold', textTransform: 'uppercase', display: 'block', marginBottom: '8px' }}>Permisos Asignados</span>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {r.permissions.map(pId => {
                              const pDef = availablePermissions.find(x => x.id === pId);
                              return (
                                <span className="role-chip" key={pId}>
                                  {pDef ? pDef.label : pId}
                                </span>
                              );
                            })}
                            {r.permissions.length === 0 && <span style={{fontSize:'12px', color:'var(--muted)'}}>Sin permisos</span>}
                          </div>
                        </div>
                        
                        {!isGlobal && r.allowed_areas && r.allowed_areas.length > 0 && (
                          <div style={{ marginTop: 'auto', paddingTop: '12px', borderTop: '1px dashed var(--line)' }}>
                            <span style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 'bold', textTransform: 'uppercase', display: 'block', marginBottom: '8px' }}>Áreas Autorizadas</span>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {r.allowed_areas.map(aId => {
                                const aDef = areas.find(x => x.id === aId);
                                return (
                                  <span className="role-chip" key={aId} style={{ background: 'var(--green-50)', borderColor: 'var(--green-100)', color: 'var(--green-800)' }}>
                                    {aDef ? aDef.name : "Desconocida"}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* ROLE CREATION MODAL */}
                {isRoleModalOpen && (
                  <div className="modal-overlay" onClick={closeRoleModal}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                      <div className="modal-header">
                        <h2>{editingRoleId ? 'Editar Rol' : 'Crear Nuevo Rol'}</h2>
                        <button className="close-btn" onClick={closeRoleModal}>
                          <X size={20} />
                        </button>
                      </div>

                      <form onSubmit={async (e) => {
                        e.preventDefault();
                        if (!newRoleName.trim()) return;
                        setLoading(true);
                        try {
                          if (editingRoleId) {
                            await apiRequest(`/roles/${editingRoleId}`, {
                              method: 'PUT',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ name: newRoleName.trim(), permissions: newRolePerms, allowed_areas: newRoleAreas })
                            });
                          } else {
                            await apiRequest('/roles', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ name: newRoleName.trim(), permissions: newRolePerms, allowed_areas: newRoleAreas })
                            });
                          }
                          closeRoleModal();
                          await loadRoles();
                        } catch(err) { setError(err.message); }
                        finally { setLoading(false); }
                      }} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                        
                        <label style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--ink-700)' }}>Nombre del Rol</span>
                          <input 
                            placeholder="Ej. Administrador de RRHH..." 
                            value={newRoleName} 
                            onChange={e => setNewRoleName(e.target.value)} 
                            disabled={loading} 
                            required 
                            style={{ width: '100%', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--line)', outline: 'none', transition: 'border 0.2s', fontSize: '14px' }}
                            onFocus={e => e.target.style.borderColor = 'var(--green-700)'}
                            onBlur={e => e.target.style.borderColor = 'var(--line)'}
                          />
                        </label>

                        <div>
                          <span style={{ fontSize: '13px', fontWeight: 'bold', borderBottom: '1px solid var(--line)', paddingBottom: '6px', display: 'block', marginBottom: '16px', color: 'var(--ink-700)' }}>Permisos del Sistema</span>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '12px' }}>
                            {availablePermissions.map(p => (
                              <label key={p.id} className={`toggle-label ${newRolePerms.includes(p.id) ? 'active' : ''}`}>
                                <div className="toggle-text-group">
                                  <span className="toggle-title">{p.label}</span>
                                </div>
                                <input 
                                  type="checkbox" 
                                  className="hidden-input"
                                  checked={newRolePerms.includes(p.id)}
                                  onChange={e => {
                                    if (e.target.checked) setNewRolePerms([...newRolePerms, p.id]);
                                    else setNewRolePerms(newRolePerms.filter(x => x !== p.id));
                                  }}
                                />
                                <div className="toggle-switch"></div>
                              </label>
                            ))}
                          </div>
                        </div>

                        <div>
                          <span style={{ fontSize: '13px', fontWeight: 'bold', borderBottom: '1px solid var(--line)', paddingBottom: '6px', display: 'block', marginBottom: '16px', color: 'var(--ink-700)' }}>Acceso a Áreas Específicas</span>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '12px' }}>
                            <label className={`toggle-label ${newRoleAreas.includes("*") ? 'active' : ''}`}>
                              <div className="toggle-text-group">
                                <span className="toggle-title">Todas las Áreas</span>
                                <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Acceso Global</span>
                              </div>
                              <input 
                                type="checkbox" 
                                className="hidden-input"
                                checked={newRoleAreas.includes("*")}
                                onChange={e => {
                                  if (e.target.checked) setNewRoleAreas(["*"]);
                                  else setNewRoleAreas([]);
                                }}
                              />
                              <div className="toggle-switch"></div>
                            </label>

                            {areas.map(area => {
                              const isGlobal = newRoleAreas.includes("*");
                              const isChecked = isGlobal || newRoleAreas.includes(area.id);
                              return (
                                <label key={area.id} className={`toggle-label ${isChecked ? 'active' : ''} ${isGlobal ? 'disabled' : ''}`}>
                                  <div className="toggle-text-group">
                                    <span className="toggle-title">{area.name}</span>
                                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Área Específica</span>
                                  </div>
                                  <input 
                                    type="checkbox" 
                                    className="hidden-input"
                                    checked={isChecked}
                                    disabled={isGlobal}
                                    onChange={e => {
                                      if (e.target.checked) setNewRoleAreas([...newRoleAreas, area.id]);
                                      else setNewRoleAreas(newRoleAreas.filter(x => x !== area.id));
                                    }}
                                  />
                                  <div className="toggle-switch"></div>
                                </label>
                              );
                            })}
                          </div>
                        </div>

                        <div style={{ borderTop: '1px solid var(--line)', paddingTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
                          <button type="button" className="secondary-button" onClick={closeRoleModal}>Cancelar</button>
                          <button type="submit" className="primary-button" disabled={loading || !newRoleName.trim()}>{editingRoleId ? 'Actualizar Rol' : 'Guardar Rol'}</button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}
              </section>
            )}

            {activeView === "users" && (
              <section className="organization-page">
                <div className="upload-hero">
                  <div>
                    <span className="eyebrow">Administración</span>
                    <h2>Gestión de Usuarios</h2>
                    <p>Administra los accesos de los colaboradores al centro de capacitación inteligente.</p>
                  </div>
                </div>
                <div className="org-grid">
                  <div className="area-card" style={{ borderColor: "var(--primary-color)", gridColumn: "1 / -1", maxWidth: "600px" }}>
                    <h3>Crear Nuevo Usuario</h3>
                    <form className="add-form" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }} onSubmit={async (e) => {
                      e.preventDefault();
                      if (!newUserEmail.trim() || !newUserPass || !newUserRole) return;
                      setLoading(true);
                      try {
                        await apiRequest('/users', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ email: newUserEmail.trim(), password: newUserPass, role_id: newUserRole })
                        });
                        setNewUserEmail("");
                        setNewUserPass("");
                        setNewUserRole("");
                        await loadUsersList();
                      } catch(err) { setError(err.message); }
                      finally { setLoading(false); }
                    }}>
                      <input type="email" placeholder="Correo corporativo (@bmsc.com.bo)" value={newUserEmail} onChange={e => setNewUserEmail(e.target.value)} disabled={loading} required />
                      <input type="password" placeholder="Contraseña temporal" value={newUserPass} onChange={e => setNewUserPass(e.target.value)} disabled={loading} required />
                      <select value={newUserRole} onChange={e => setNewUserRole(e.target.value)} disabled={loading} style={{ padding: "8px", borderRadius: "6px", border: "1px solid var(--line)" }} required>
                        <option value="">Seleccionar rol...</option>
                        {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </select>
                      <button className="primary-button compact" type="submit" disabled={loading || !newUserEmail.trim() || !newUserPass || !newUserRole}>Crear Usuario</button>
                    </form>
                  </div>

                  {usersList.map(u => (
                    <div className="area-card" key={u.id} style={{ borderColor: "var(--line)" }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Users size={20} color="var(--primary-color)" />
                        <h3 style={{ margin: 0, wordBreak: 'break-all' }}>{u.email}</h3>
                      </div>
                      <div style={{ marginTop: '12px' }}>
                        <span style={{ fontSize: '12px', background: 'var(--surface-soft)', padding: '4px 8px', borderRadius: '4px', fontWeight: 'bold' }}>
                          Rol: {u.role?.name || "Sin Rol"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {activeView === "video" && selectedVideo && (
              <>
                {renderVideoPlayer("context-player video-first-player")}

                <section className="module-launch-grid video-detail-tabs">
                  <button
                    className={cx("module-card", activeTab === "assistant" && "active")}
                    type="button"
                    onClick={() => setActiveTab("assistant")}
                  >
                    <div className="module-card-icon">
                      <Bot size={20} />
                    </div>
                    <div>
                      <strong>Consultar contenido</strong>
                      <span>{selectedVideoIsReady ? "Disponible con fuentes del video" : "Disponible al finalizar indexación"}</span>
                    </div>
                    <ArrowRight size={18} />
                  </button>
                  <button
                    className={cx("module-card", activeTab === "manuals" && "active")}
                    type="button"
                    onClick={() => setActiveTab("manuals")}
                  >
                    <div className="module-card-icon">
                      <BookOpen size={20} />
                    </div>
                    <div>
                      <strong>Manuales del Video</strong>
                      <span>{latestManual ? `Último: ${latestManual.title}` : "Sin manuales generados"}</span>
                    </div>
                    <ArrowRight size={18} />
                  </button>
                  <button
                    className={cx("module-card", activeTab === "transcript" && "active")}
                    type="button"
                    onClick={() => setActiveTab("transcript")}
                  >
                    <div className="module-card-icon">
                      <PlayCircle size={20} />
                    </div>
                    <div>
                      <strong>Transcripción</strong>
                      <span>{transcript.length} segmentos de transcripción</span>
                    </div>
                    <ArrowRight size={18} />
                  </button>
                </section>
              </>
            )}

            {activeView === "video" && activeTab === "manuals" && selectedVideo && (
              <>
              <section className="manual-surface">
              <div className="manual-header">
                <div>
                  <span className="eyebrow">Documentación</span>
                  <h3>Manuales y Guías</h3>
                </div>
                
                {hasPermission("generate_manual") && (
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <div className="segmented-control" style={{ marginRight: '8px' }}>
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
                )}
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
                            {manual.screenshot_count ? ` · ${manual.screenshot_count} capturas` : ""}
                            {" · "}
                            Creado {formatDateTime(manual.created_at)}
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
                        <button className="secondary-button compact" type="button" onClick={() => {
                          if (!selectedVideo) return;
                          setManualToDelete(manual);
                        }} disabled={loading}>
                          <Trash2 size={15} />
                          Eliminar
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
                          ? `Vista previa renderizada · Creado ${formatDateTime(manualPreview.metadata.created_at)}`
                          : `${manualPreview.metadata.current_section || "Generando"} · ${Math.round(manualPreview.metadata.progress || 0)}% · Creado ${formatDateTime(manualPreview.metadata.created_at)}`}
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
                  <MarkdownDocument
                    content={manualPreview.content || ""}
                    assetBaseUrl={`${API_BASE_URL}/videos/${selectedVideo.id}/manuals/${manualPreview.metadata.id}/assets`}
                  />
                </div>
              )}
            </section>
              </>
            )}

            {activeView === "video" && activeTab === "transcript" && selectedVideo && (
              <>
              <section className="transcript-surface">
                <div className="panel-heading">
                  <h3>Transcripción por timestamp</h3>
                  <span>{transcript.length}</span>
                </div>
                <div className="transcript-list transcript-list-standalone">
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
              </section>
              </>
            )}

            {activeView === "video" && activeTab === "assistant" && selectedVideo && (
              <>
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

            {activeView === "video" && selectedVideo && (
              <section className="video-summary compact-video-summary">
                <div className="summary-main">
                  <div className="summary-icon">
                    <PlayCircle size={24} />
                  </div>
                  <div>
                    <div className="summary-title-row">
                      <h2>Resumen técnico</h2>
                      <StatusPill status={selectedVideo.status} stage={selectedVideo.processing_stage} />
                    </div>
                    <p>
                      {formatSeconds(selectedVideo.duration_seconds)} · {selectedVideo.segment_count} segmentos · {selectedVideo.chunk_count} fragmentos indexados
                    </p>
                  </div>
                </div>

                <div className="video-compact-meta">
                  <div>
                    <span>Progreso</span>
                    <strong>{Math.round(selectedVideo.processing_progress || 0)}%</strong>
                    <ProgressBar value={selectedVideo.processing_progress} />
                  </div>
                  <div>
                    <span>Avance</span>
                    <strong>{selectedVideo.transcribed_timecode || "00:00:00.000"}</strong>
                    <small>{selectedVideo.progress_updated_at ? `Actualizado ${formatDate(selectedVideo.progress_updated_at)}` : "Sin avance"}</small>
                  </div>
                  <div>
                    <span>Audio</span>
                    <strong>{selectedVideo.audio_extraction_backend || "Pendiente"}</strong>
                    <small>{selectedVideo.language ? `Idioma ${selectedVideo.language}` : "Idioma por detectar"}</small>
                  </div>
                  <div>
                    <span>Manuales</span>
                    <strong>{manuals.length}</strong>
                    <small>{latestManual ? `Último ${formatDate(latestManual.created_at)}` : "Sin documentos"}</small>
                  </div>
                </div>

                <div className="summary-actions">
                  <button className="secondary-button" type="button" onClick={handleReprocess} disabled={loading}>
                    <RefreshCcw size={16} />
                    Reprocesar
                  </button>
                  <button className="danger-button" type="button" onClick={() => setVideoToDelete(selectedVideo)} disabled={loading}>
                    <Trash2 size={16} />
                    Eliminar
                  </button>
                </div>
              </section>
            )}

            {editingVideo && (
              <div className="modal-overlay" onClick={() => setEditingVideo(null)}>
                <div className="modal-content" onClick={e => e.stopPropagation()}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: 'var(--ink-900)' }}>
                    <Edit2 size={24} />
                    <h2 style={{ margin: 0 }}>Editar Video</h2>
                  </div>
                  <div style={{ marginBottom: '24px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>Nombre del video</label>
                    <input 
                      value={editFilename} 
                      onChange={e => setEditFilename(e.target.value)} 
                      style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--line)' }}
                    />
                    
                    <label style={{ display: 'block', marginTop: '16px', marginBottom: '8px', fontWeight: 'bold' }}>Subárea asignada</label>
                    <select 
                      value={editSubarea} 
                      onChange={e => setEditSubarea(e.target.value)}
                      style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--line)' }}
                    >
                      <option value="">Sin asignar</option>
                      {areas.map(area => (
                        <optgroup key={area.id} label={area.name}>
                          {area.subareas.map(sub => (
                            <option key={sub.id} value={sub.id}>{sub.name}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <div className="modal-actions">
                    <button className="secondary-button" type="button" onClick={() => setEditingVideo(null)} disabled={loading}>
                      Cancelar
                    </button>
                    <button 
                      className="primary-button" 
                      type="button" 
                      disabled={loading || !editFilename.trim()}
                      onClick={async () => {
                        setLoading(true);
                        try {
                          await apiRequest(`/videos/${editingVideo.id}`, {
                            method: "PUT",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ 
                              original_filename: editFilename.trim(),
                              subarea_id: editSubarea || ""
                            })
                          });
                          setEditingVideo(null);
                          await loadVideos();
                        } catch (err) {
                          setError(err.message);
                        } finally {
                          setLoading(false);
                        }
                      }}
                    >
                      {loading ? <Loader2 className="spin" size={15} /> : "Guardar cambios"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {videoToDelete && (
              <div className="modal-overlay" onClick={() => setVideoToDelete(null)}>
                <div className="modal-content" onClick={e => e.stopPropagation()}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: 'var(--danger)' }}>
                    <AlertCircle size={24} />
                    <h2 style={{ margin: 0 }}>Eliminar video</h2>
                  </div>
                  <div style={{ marginBottom: '24px' }}>
                    <p>¿Estás seguro de que quieres eliminar permanentemente el video <strong>"{videoToDelete.original_filename}"</strong>?</p>
                    <p style={{ color: 'var(--muted)', fontSize: '14px', marginTop: '8px' }}>Esta acción borrará también todas las transcripciones y manuales asociados. No se puede deshacer.</p>
                  </div>
                  <div className="modal-actions">
                    <button className="secondary-button" type="button" onClick={() => setVideoToDelete(null)} disabled={loading}>
                      Cancelar
                    </button>
                    <button 
                      className="danger-button" 
                      type="button" 
                      disabled={loading}
                      onClick={async () => {
                        setLoading(true);
                        try {
                          await apiRequest(`/videos/${videoToDelete.id}`, { method: "DELETE" });
                          setVideoToDelete(null);
                          if (selectedId === videoToDelete.id) {
                            setSelectedId(null);
                            setActiveView("dashboard");
                          }
                          await loadVideos();
                        } catch (err) {
                          setError(err.message);
                        } finally {
                          setLoading(false);
                        }
                      }}
                    >
                      {loading ? <Loader2 className="spin" size={15} /> : "Sí, eliminar"}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
      </main>

      {manualToDelete && (
        <div className="modal-overlay" onClick={() => setManualToDelete(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: 'var(--danger)' }}>
              <AlertCircle size={24} />
              <h2 style={{ margin: 0 }}>Eliminar manual</h2>
            </div>
            <div className="modal-body" style={{ marginBottom: '24px' }}>
              <p>¿Estás seguro de que quieres eliminar permanentemente el manual <strong>"{manualToDelete.title}"</strong>?</p>
              <p style={{ color: 'var(--muted)', fontSize: '14px', marginTop: '8px' }}>Esta acción borrará el archivo de texto y sus imágenes adjuntas. No se puede deshacer.</p>
            </div>
            <div className="modal-actions">
              <button className="secondary-button" type="button" onClick={() => setManualToDelete(null)} disabled={loading}>
                Cancelar
              </button>
              <button className="danger-button" type="button" onClick={async () => {
                setLoading(true);
                setError("");
                try {
                  await apiRequest(`/videos/${selectedVideo.id}/manuals/${manualToDelete.id}`, { method: "DELETE" });
                  if (manualPreview?.metadata?.id === manualToDelete.id) {
                    setManualPreview(null);
                  }
                  await loadManuals(selectedVideo.id, { silent: true });
                  setManualToDelete(null);
                } catch (err) {
                  setError(err.message);
                } finally {
                  setLoading(false);
                }
              }} disabled={loading}>
                {loading ? <Loader2 className="spin" size={17} /> : <Trash2 size={17} />}
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
