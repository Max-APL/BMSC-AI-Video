import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Edit2, FileVideo, PlayCircle, RefreshCcw, Trash2, UploadCloud, X } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import { EmptyState } from "@/components/common/EmptyState";
import { AreaAssignmentChip } from "@/components/common/AreaAssignmentChip";
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
  const canUploadVideo = hasPermission("upload_video");
  const canEditVideo = hasPermission("edit_video");
  const canDeleteVideo = hasPermission("delete_video");

  const [uploadSubareaId, setUploadSubareaId] = useState("");
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [editingVideo, setEditingVideo] = useState(null);
  const [editFilename, setEditFilename] = useState("");
  const [editSubarea, setEditSubarea] = useState("");
  const [videoToDelete, setVideoToDelete] = useState(null);

  const recentVideos = [...videos]
    .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
    .slice(0, 5);

  const availableSubareas = areas.flatMap((area) =>
    area.subareas.map((subarea) => ({
      id: subarea.id,
      label: `${area.name} > ${subarea.name}`,
    }))
  );
  const uploadRequiresAssignment = availableSubareas.length > 0;

  function getSubareaLabel(subareaId) {
    if (!subareaId) return "Sin área asignada";
    const match = availableSubareas.find((subarea) => subarea.id === subareaId);
    return match?.label || "Sin área asignada";
  }

  function closeUploadModal() {
    if (uploading) return;
    setIsUploadModalOpen(false);
    setUploadFile(null);
    setUploadSubareaId("");
  }

  async function handleUploadSubmit(event) {
    event.preventDefault();
    if (!uploadFile) return;
    if (uploadRequiresAssignment && !uploadSubareaId) return;
    setUploading(true);
    setError("");
    try {
      const metadata = await uploadVideo(uploadFile);
      if (uploadSubareaId) {
        await assignVideoSubarea(metadata.id, uploadSubareaId);
      }
      setIsUploadModalOpen(false);
      setUploadFile(null);
      setUploadSubareaId("");
      navigate(`/videos/${metadata.id}`);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleSaveEdit() {
    if (!editingVideo || !canEditVideo) return;
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
    if (!videoToDelete || !canDeleteVideo) return;
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
        {canUploadVideo ? (
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
                onClick={() => setIsUploadModalOpen(true)}
                disabled={uploading}
              >
                <UploadCloud size={18} />
                {uploading ? "Subiendo..." : "Subir video"}
              </button>
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
                    </span>
                    <AreaAssignmentChip
                      label={getSubareaLabel(video.subarea_id)}
                      unassigned={!video.subarea_id}
                    />
                    {video.status === "processing" && (
                      <ProgressBar value={video.processing_progress} />
                    )}
                  </div>
                  <StatusPill status={video.status} stage={video.processing_stage} />
                  <div className="history-row-actions">
                    {canEditVideo && (
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
                    )}
                    {canDeleteVideo && (
                      <button
                        className="danger-button compact"
                        type="button"
                        onClick={() => setVideoToDelete(video)}
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
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

      {isUploadModalOpen && (
        <div className="modal-overlay" onClick={closeUploadModal}>
          <div className="modal-content upload-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <UploadCloud size={24} />
                <div>
                  <h2>Subir video</h2>
                  <p>Selecciona el archivo y asígnalo al área correspondiente.</p>
                </div>
              </div>
              <button
                className="close-btn"
                type="button"
                onClick={closeUploadModal}
                disabled={uploading}
              >
                <X size={20} />
              </button>
            </div>

            <form className="upload-modal-form" onSubmit={handleUploadSubmit}>
              <label className="upload-file-drop">
                <FileVideo size={24} />
                <span>{uploadFile ? uploadFile.name : "Seleccionar archivo de video"}</span>
                <small>
                  {uploadFile
                    ? `${(uploadFile.size / (1024 * 1024)).toFixed(1)} MB`
                    : "Formatos compatibles: MP4, MKV y otros formatos de video"}
                </small>
                <input
                  type="file"
                  accept="video/*,audio/*,.mkv,.mvk"
                  onChange={(event) => setUploadFile(event.target.files?.[0] || null)}
                  disabled={uploading}
                />
              </label>

              <label className="field-group">
                <span>Área asignada</span>
                <select
                  value={uploadSubareaId}
                  onChange={(event) => setUploadSubareaId(event.target.value)}
                  disabled={uploading || availableSubareas.length === 0}
                  required={uploadRequiresAssignment}
                >
                  <option value="">
                    {availableSubareas.length === 0
                      ? "Sin áreas configuradas"
                      : "Seleccionar área y subárea"}
                  </option>
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
              </label>

              <div className="modal-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={closeUploadModal}
                  disabled={uploading}
                >
                  Cancelar
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={uploading || !uploadFile || (uploadRequiresAssignment && !uploadSubareaId)}
                >
                  <UploadCloud size={17} />
                  Subir video
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
