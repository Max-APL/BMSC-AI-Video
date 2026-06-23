import React, { useRef } from "react";
import { useNavigate, useMatch } from "react-router-dom";
import {
  Database,
  FileVideo,
  Gauge,
  RefreshCcw,
  Search,
  Shield,
  UploadCloud,
  Users,
} from "lucide-react";
import bmscLogo from "@/assets/bmsc-logo.png";
import { cx } from "@/utils/cx";
import { formatDate, formatSeconds } from "@/utils/format";
import { useAuth } from "@/context/AuthContext";
import { useVideos } from "@/context/VideosContext";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import { EmptyState } from "@/components/common/EmptyState";
import { uploadVideo } from "@/services/videos";
import { assignVideoSubarea } from "@/services/areas";
import { useAreas } from "@/context/AreasContext";
import "./Sidebar.css";

export function Sidebar() {
  const navigate = useNavigate();
  const { currentUser, logout, hasPermission } = useAuth();
  const { videos, uploading, setUploading, setError, quickSearch, setQuickSearch, filteredQuickVideos, loadVideos } =
    useVideos();
  const { areas } = useAreas();
  const fileInputRef = useRef(null);

  // Detect active video from URL
  const videoMatch = useMatch("/videos/:id");
  const currentVideoId = videoMatch?.params?.id;

  const navigationItems = [
    ...(hasPermission("view_dashboard")
      ? [{ id: "dashboard", label: "Panel principal", icon: Gauge, path: "/" }]
      : []),
    ...(hasPermission("view_videos")
      ? [{ id: "upload", label: "Gestión de videos", icon: UploadCloud, path: "/upload" }]
      : []),
    ...(hasPermission("view_library")
      ? [
          {
            id: "library",
            label: "Biblioteca",
            icon: FileVideo,
            badge: videos.length,
            path: "/library",
          },
        ]
      : []),
    ...(hasPermission("view_organization")
      ? [{ id: "organization", label: "Organización", icon: Database, path: "/organization" }]
      : []),
    ...(hasPermission("view_users")
      ? [{ id: "users", label: "Usuarios", icon: Users, path: "/users" }]
      : []),
    ...(hasPermission("view_roles")
      ? [{ id: "roles", label: "Roles", icon: Shield, path: "/roles" }]
      : []),
  ];

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const metadata = await uploadVideo(file);
      // Assign to first available subarea only if there are areas (simple default)
      // The full subarea selection is in UploadPage
      navigate(`/videos/${metadata.id}`);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="brand">
        <img className="brand-logo" src={bmscLogo} alt="Mercantil Santa Cruz" />
        <div className="brand-copy">
          <p>Centro IA Video</p>
          <span>Mercantil Santa Cruz</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="module-nav" aria-label="Módulos administrativos">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          // Determine active: "/" only matches exactly
          const isActive =
            item.path === "/"
              ? window.location.pathname === "/"
              : window.location.pathname.startsWith(item.path);
          return (
            <button
              type="button"
              key={item.id}
              className={cx("module-nav-item", isActive && "active")}
              onClick={() => navigate(item.path)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
              {item.badge !== undefined && <strong>{item.badge}</strong>}
            </button>
          );
        })}
      </nav>

      {/* Hidden file input (quick upload from sidebar) */}
      <input
        ref={fileInputRef}
        className="hidden-input"
        type="file"
        accept="video/*,audio/*,.mkv,.mvk"
        onChange={handleFileChange}
      />

      {/* Quick library title */}
      <div className="sidebar-title">
        <span>Biblioteca rápida</span>
        <button
          type="button"
          className="icon-button"
          onClick={() => loadVideos()}
          title="Actualizar videos"
        >
          <RefreshCcw size={16} />
        </button>
      </div>

      {/* Search */}
      <label className="quick-search">
        <Search size={15} />
        <input
          value={quickSearch}
          onChange={(e) => setQuickSearch(e.target.value)}
          placeholder="Buscar video..."
        />
      </label>

      {/* Video list */}
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
            className={cx("video-item", currentVideoId === video.id && "active")}
            onClick={() => navigate(`/videos/${video.id}`)}
          >
            <div className="video-item-top">
              <FileVideo size={18} />
              <StatusPill status={video.status} stage={video.processing_stage} />
            </div>
            <strong>{video.original_filename}</strong>
            <span>
              {formatSeconds(video.duration_seconds)} · {formatDate(video.created_at)}
            </span>
            {video.status === "processing" && (
              <ProgressBar value={video.processing_progress} />
            )}
          </button>
        ))}
      </div>

      {/* User profile */}
      <div className="user-profile">
        <div className="user-profile-row">
          <div className="user-avatar">
            {currentUser?.email?.charAt(0).toUpperCase() || "U"}
          </div>
          <div className="user-info">
            <div className="user-email" title={currentUser?.email}>
              {currentUser?.email}
            </div>
            <div className="user-role">{currentUser?.role}</div>
          </div>
        </div>
        <button
          type="button"
          className="secondary-button compact user-logout"
          onClick={logout}
        >
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
