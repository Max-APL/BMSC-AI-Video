import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Edit2, PlayCircle, RefreshCcw, Trash2, UploadCloud } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import { EmptyState } from "@/components/common/EmptyState";
import { EditVideoModal } from "@/components/modals/EditVideoModal";
import { DeleteVideoModal } from "@/components/modals/DeleteVideoModal";
import { formatDate, formatSeconds } from "@/utils/format";
import { useAuth } from "@/context/AuthContext";
import { useVideos } from "@/context/VideosContext";
import { useAreas } from "@/context/AreasContext";
import { uploadVideo, updateVideo, deleteVideo } from "@/services/videos";
import { assignVideoSubarea } from "@/services/areas";
import "./UploadPage.css";

export function UploadPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const { videos, uploading, setUploading, error, setError, loading, setLoading, loadVideos } =
    useVideos();
  const { areas } = useAreas();
  const fileInputRef = useRef(null);

  const [uploadSubareaId, setUploadSubareaId] = useState("");
  const [editingVideo, setEditingVideo] = useState(null);
  const [editFilename, setEditFilename] = useState("");
  const [editSubarea, setEditSubarea] = useState("");
  const [videoToDelete, setVideoToDelete] = useState(null);

  const recentVideos = [...videos]
    .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
    .slice(0, 5);

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const metadata = await uploadVideo(file);
      if (uploadSubareaId) {
        await assignVideoSubarea(metadata.id, uploadSubareaId);
      }
      navigate(`/videos/${metadata.id}`);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleSaveEdit() {
    if (!editingVideo) return;
    setLoading(true);
    try {
      await updateVideo(editingVideo.id, {
        original_filename: editFilename.trim(),
        subarea_id: editSubarea || "",
      });
      setEditingVideo(null);
      await loadVideos();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmDelete() {
    if (!videoToDelete) return;
    setLoading(true);
    try {
      await deleteVideo(videoToDelete.id);
      setVideoToDelete(null);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Topbar />
      <section className="upload-page">
        {hasPermission("upload_video") ? (
          <>
            <div className="upload-hero">
              <div>
                <span className="eyebrow">Nuevo material</span>
                <h2>Cargar video de capacitación</h2>
                <p>
                  El archivo quedará en el historial y luego podrá gestionarse
                  desde su expediente individual.
                </p>
              </div>
              <button
                className="primary-button"
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                <UploadCloud size={18} />
                {uploading ? "Subiendo..." : "Seleccionar archivo"}
              </button>
            </div>

            <input
              ref={fileInputRef}
              className="hidden-input"
              type="file"
              accept="video/*,audio/*,.mkv,.mvk"
              onChange={handleFileChange}
            />

            <div className="upload-subarea-selector">
              <label className="upload-subarea-label">
                Asignar a subárea (Opcional):
              </label>
              <select
                value={uploadSubareaId}
                onChange={(e) => setUploadSubareaId(e.target.value)}
                className="upload-subarea-select"
              >
                <option value="">Sin asignar</option>
                {areas.map((area) => (
                  <optgroup key={area.id} label={area.name}>
                    {area.subareas.map((sub) => (
                      <option key={sub.id} value={sub.id}>
                        {sub.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </>
        ) : (
          <div className="upload-hero upload-restricted">
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
              <p>
                Seguimiento de los archivos ingresados y su estado de
                procesamiento.
              </p>
            </div>
            <button
              className="icon-button light"
              type="button"
              onClick={() => loadVideos()}
              title="Actualizar historial"
            >
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
                      {formatSeconds(video.duration_seconds)} · Cargado{" "}
                      {formatDate(video.created_at)}
                      {video.subarea_id &&
                        (() => {
                          let subName = "";
                          areas.forEach((a) =>
                            a.subareas.forEach((s) => {
                              if (s.id === video.subarea_id)
                                subName = `${a.name} > ${s.name}`;
                            })
                          );
                          return subName ? ` · ${subName}` : "";
                        })()}
                    </span>
                    {video.status === "processing" && (
                      <ProgressBar value={video.processing_progress} />
                    )}
                  </div>
                  <StatusPill status={video.status} stage={video.processing_stage} />
                  <div className="history-row-actions">
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
                      onClick={() => navigate(`/videos/${video.id}`)}
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

      <EditVideoModal
        video={editingVideo}
        filename={editFilename}
        subarea={editSubarea}
        onFilenameChange={setEditFilename}
        onSubareaChange={setEditSubarea}
        onSave={handleSaveEdit}
        onClose={() => setEditingVideo(null)}
        loading={loading}
      />

      <DeleteVideoModal
        video={videoToDelete}
        onConfirm={handleConfirmDelete}
        onClose={() => setVideoToDelete(null)}
        loading={loading}
      />
    </>
  );
}
