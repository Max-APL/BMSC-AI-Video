import React from "react";
import { useNavigate } from "react-router-dom";
import { FileVideo, PlayCircle } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { StatusPill } from "@/components/common/StatusPill";
import { EmptyState } from "@/components/common/EmptyState";
import { formatDate, formatSeconds } from "@/utils/format";
import { useVideos } from "@/context/VideosContext";
import "./DashboardPage.css";

export function DashboardPage() {
  const navigate = useNavigate();
  const { videos } = useVideos();

  const readyCount = videos.filter((v) => v.status === "ready").length;
  const processingCount = videos.filter((v) => v.status === "processing").length;
  const failedCount = videos.filter((v) => v.status === "failed").length;
  const totalDurationSeconds = videos.reduce(
    (acc, v) => acc + Number(v.duration_seconds || 0),
    0
  );
  const totalSegments = videos.reduce(
    (acc, v) => acc + Number(v.segment_count || 0),
    0
  );
  const totalChunks = videos.reduce(
    (acc, v) => acc + Number(v.chunk_count || 0),
    0
  );
  const loadedHistory = [...videos].sort(
    (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
  );

  return (
    <>
      <Topbar />
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
              <small>
                {failedCount ? `${failedCount} con error` : "Sin errores activos"}
              </small>
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
            <button
              className="secondary-button"
              type="button"
              onClick={() => navigate("/library")}
            >
              <FileVideo size={16} />
              Ver biblioteca
            </button>
          </div>

          <div className="history-list">
            {loadedHistory.length === 0 ? (
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
                    <span>
                      {formatSeconds(video.duration_seconds)} ·{" "}
                      {formatDate(video.created_at)} · {video.segment_count} segmentos
                    </span>
                  </div>
                  <StatusPill status={video.status} stage={video.processing_stage} />
                  <button
                    className="secondary-button compact"
                    type="button"
                    onClick={() => navigate(`/videos/${video.id}`)}
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
    </>
  );
}
