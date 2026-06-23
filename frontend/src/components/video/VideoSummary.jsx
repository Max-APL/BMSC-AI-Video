import React from "react";
import { PlayCircle, RefreshCcw, Trash2 } from "lucide-react";
import { formatDate, formatSeconds } from "@/utils/format";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import "./VideoSummary.css";

export function VideoSummary({ video, manualsCount, latestManual, onReprocess, onDeleteRequest, loading }) {
  if (!video) return null;

  return (
    <section className="video-summary compact-video-summary">
      <div className="summary-main">
        <div className="summary-icon">
          <PlayCircle size={24} />
        </div>
        <div>
          <div className="summary-title-row">
            <h2>Resumen técnico</h2>
            <StatusPill status={video.status} stage={video.processing_stage} />
          </div>
          <p>
            {formatSeconds(video.duration_seconds)} · {video.segment_count} segmentos ·{" "}
            {video.chunk_count} fragmentos indexados
          </p>
        </div>
      </div>

      <div className="video-compact-meta">
        <div>
          <span>Progreso</span>
          <strong>{Math.round(video.processing_progress || 0)}%</strong>
          <ProgressBar value={video.processing_progress} />
        </div>
        <div>
          <span>Avance</span>
          <strong>{video.transcribed_timecode || "00:00:00.000"}</strong>
          <small>
            {video.progress_updated_at
              ? `Actualizado ${formatDate(video.progress_updated_at)}`
              : "Sin avance"}
          </small>
        </div>
        <div>
          <span>Audio</span>
          <strong>{video.audio_extraction_backend || "Pendiente"}</strong>
          <small>
            {video.language ? `Idioma ${video.language}` : "Idioma por detectar"}
          </small>
        </div>
        <div>
          <span>Manuales</span>
          <strong>{manualsCount}</strong>
          <small>
            {latestManual
              ? `Último ${formatDate(latestManual.created_at)}`
              : "Sin documentos"}
          </small>
        </div>
      </div>

      <div className="summary-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={onReprocess}
          disabled={loading}
        >
          <RefreshCcw size={16} />
          Reprocesar
        </button>
        <button
          className="danger-button"
          type="button"
          onClick={onDeleteRequest}
          disabled={loading}
        >
          <Trash2 size={16} />
          Eliminar
        </button>
      </div>
    </section>
  );
}
