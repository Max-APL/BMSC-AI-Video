import React, { useState, useRef, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowRight, BookOpen, Bot, PlayCircle, RefreshCcw } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { VideoPlayer } from "@/components/video/VideoPlayer";
import { AssistantPanel } from "@/components/video/AssistantPanel";
import { TranscriptPanel } from "@/components/video/TranscriptPanel";
import { ManualsPanel } from "@/components/video/ManualsPanel";
import { VideoSummary } from "@/components/video/VideoSummary";
import { EditVideoModal } from "@/components/modals/EditVideoModal";
import { DeleteVideoModal } from "@/components/modals/DeleteVideoModal";
import { DeleteManualModal } from "@/components/modals/DeleteManualModal";
import { cx } from "@/utils/cx";
import { useAuth } from "@/context/AuthContext";
import { useVideos } from "@/context/VideosContext";
import { useAreas } from "@/context/AreasContext";
import { useManuals } from "@/hooks/useManuals";
import {
  reindexVideo,
  reprocessVideo,
  getTranscript,
  askVideo,
  updateVideo,
  deleteVideo,
  mediaUrl,
} from "@/services/videos";
import "./VideoDetailPage.css";

export function VideoDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const { videos, loading, setLoading, error, setError, loadVideos } = useVideos();
  const { areas } = useAreas();

  const video = videos.find((v) => v.id === id) || null;
  const videoSrc = id ? mediaUrl(id) : "";

  const videoRef = useRef(null);
  const [activeTab, setActiveTab] = useState("assistant");

  // Transcript
  const [transcript, setTranscript] = useState([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);

  // Edit / delete video
  const [editingVideo, setEditingVideo] = useState(null);
  const [editFilename, setEditFilename] = useState("");
  const [editSubarea, setEditSubarea] = useState("");
  const [videoToDelete, setVideoToDelete] = useState(null);

  const {
    manuals,
    manualMode,
    setManualMode,
    manualQualityMode,
    setManualQualityMode,
    manualPreview,
    manualToDelete,
    setManualToDelete,
    generatingManual,
    handleGenerateManual,
    handlePreviewManual,
    handleDownloadManual,
    handleDeleteManual,
    getAssetsUrl,
  } = useManuals(id, { setError, setLoading });

  // Load transcript when video is ready
  useEffect(() => {
    if (!id || !video || video.status !== "ready") return;
    let cancelled = false;
    getTranscript(id)
      .then((data) => {
        if (!cancelled) setTranscript(data.segments || []);
      })
      .catch(() => {
        if (!cancelled) setTranscript([]);
      });
    return () => {
      cancelled = true;
    };
  }, [id, video?.status, video?.segment_count]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset per-video state when id changes
  useEffect(() => {
    setAnswer(null);
    setQuestion("");
    setTranscript([]);
    setActiveTab("assistant");
  }, [id]);

  const seekVideoTo = useCallback((seconds) => {
    const player = videoRef.current;
    if (!player) return;
    const targetTime = Math.max(0, Number(seconds) || 0);

    const applySeek = () => {
      try {
        player.currentTime = targetTime;
      } catch {
        return;
      }
      const attempt = player.play();
      if (attempt?.catch) attempt.catch(() => {});
    };

    if (Number.isNaN(player.duration)) {
      player.addEventListener("loadedmetadata", applySeek, { once: true });
      player.load();
    } else {
      applySeek();
    }
    player.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  async function handleAsk(e) {
    e.preventDefault();
    if (!video || !question.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await askVideo(id, question);
      setAnswer(data);
      setActiveTab("assistant");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleReindex() {
    if (!video) return;
    setLoading(true);
    setError("");
    try {
      await reindexVideo(id);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleReprocess() {
    if (!video) return;
    setLoading(true);
    setError("");
    try {
      await reprocessVideo(id);
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
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
      navigate("/library");
      await loadVideos({ silent: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const latestManual = manuals[0] || null;
  const areaLabel =
    areas
      .flatMap((area) =>
        area.subareas.map((subarea) => ({
          id: subarea.id,
          label: `${area.name} > ${subarea.name}`,
        }))
      )
      .find((subarea) => subarea.id === video?.subarea_id)?.label ||
    "Sin área asignada";

  const reindexAction = (
    <button
      className="secondary-button"
      type="button"
      onClick={handleReindex}
      disabled={!video || loading}
    >
      <RefreshCcw size={16} />
      Reindexar
    </button>
  );

  if (!video) {
    return (
      <>
        <Topbar />
        <section className="selection-required">
          <div className="selection-required-icon">
            <PlayCircle size={24} />
          </div>
          <span className="eyebrow">Video no encontrado</span>
          <h2>El video solicitado no existe o aún está cargando.</h2>
          <p>
            Selecciona un video desde la biblioteca o espera a que los datos se
            actualicen.
          </p>
          <button
            className="primary-button"
            type="button"
            onClick={() => navigate("/library")}
          >
            Ir a biblioteca
          </button>
        </section>
      </>
    );
  }

  return (
    <>
      <Topbar actions={reindexAction} />

      {/* Video player */}
      <VideoPlayer
        video={video}
        mediaUrl={videoSrc}
        videoRef={videoRef}
        className="context-player video-first-player"
      />

      {/* Tab selector */}
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
            <span>
              {video.status === "ready"
                ? "Disponible con fuentes del video"
                : "Disponible al finalizar indexación"}
            </span>
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
            <span>
              {latestManual ? `Último: ${latestManual.title}` : "Sin manuales generados"}
            </span>
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

      {/* Tab content */}
      {activeTab === "manuals" && (
        <ManualsPanel
          video={video}
          manuals={manuals}
          manualMode={manualMode}
          setManualMode={setManualMode}
          manualQualityMode={manualQualityMode}
          setManualQualityMode={setManualQualityMode}
          manualPreview={manualPreview}
          generatingManual={generatingManual}
          loading={loading}
          hasGeneratePermission={hasPermission("generate_manual")}
          onGenerate={handleGenerateManual}
          onPreview={handlePreviewManual}
          onDownload={handleDownloadManual}
          onDeleteRequest={setManualToDelete}
          getAssetsUrl={getAssetsUrl}
        />
      )}

      {activeTab === "transcript" && (
        <TranscriptPanel transcript={transcript} onSeek={seekVideoTo} />
      )}

      {activeTab === "assistant" && (
        <AssistantPanel
          video={video}
          transcript={transcript}
          question={question}
          setQuestion={setQuestion}
          answer={answer}
          loading={loading}
          onAsk={handleAsk}
          onSeek={seekVideoTo}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />
      )}

      {/* Technical summary always visible */}
      <VideoSummary
        video={video}
        areaLabel={areaLabel}
        manualsCount={manuals.length}
        latestManual={latestManual}
        onReprocess={handleReprocess}
        onDeleteRequest={() => setVideoToDelete(video)}
        loading={loading}
      />

      {/* Modals */}
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

      <DeleteManualModal
        manual={manualToDelete}
        onConfirm={() => handleDeleteManual(manualToDelete)}
        onClose={() => setManualToDelete(null)}
        loading={loading}
      />
    </>
  );
}
