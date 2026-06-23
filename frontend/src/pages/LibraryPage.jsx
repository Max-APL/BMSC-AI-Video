import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock3, Database, FileText, FolderOpen, PlayCircle } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import { formatDate, formatSeconds } from "@/utils/format";
import { useVideos } from "@/context/VideosContext";
import { useAreas } from "@/context/AreasContext";
import { cx } from "@/utils/cx";
import "./LibraryPage.css";

export function LibraryPage() {
  const navigate = useNavigate();
  const { videos } = useVideos();
  const { areas } = useAreas();

  const [filterArea, setFilterArea] = useState(null);
  const [filterSubarea, setFilterSubarea] = useState(null);

  const filteredVideos = videos.filter((v) => {
    if (filterSubarea) return v.subarea_id === filterSubarea.id;
    if (filterArea) {
      const subIds = filterArea.subareas.map((s) => s.id);
      return subIds.includes(v.subarea_id);
    }
    return true;
  });

  function getSubareaLabel(subareaId) {
    let label = "Sin área asignada";
    areas.forEach((a) =>
      a.subareas.forEach((s) => {
        if (s.id === subareaId) label = `${a.name} > ${s.name}`;
      })
    );
    return label;
  }

  return (
    <>
      <Topbar />
      <section className="library-surface library-layout">
        {/* Sidebar filters */}
        <div className="library-filter-nav">
          <div className="library-header library-filter-header">
            <div>
              <span className="eyebrow">Navegación</span>
              <h2>Filtros</h2>
            </div>
          </div>

          <div className="library-filter-list">
            <div
              className={cx("area-card library-filter-card", !filterArea && "filter-active")}
              onClick={() => {
                setFilterArea(null);
                setFilterSubarea(null);
              }}
            >
              <h3>Todos los videos</h3>
            </div>

            {areas.map((area) => (
              <div
                key={area.id}
                className={cx(
                  "area-card library-filter-card",
                  filterArea?.id === area.id && "filter-active"
                )}
                onClick={() => {
                  setFilterArea(area);
                  setFilterSubarea(null);
                }}
              >
                <h3>
                  {area.name} <span>({area.subareas.length})</span>
                </h3>
                <div className="subarea-list">
                  {area.subareas.map((sub) => (
                    <div
                      key={sub.id}
                      className={cx(
                        "subarea-item",
                        filterSubarea?.id === sub.id && "subarea-active"
                      )}
                      onClick={(e) => {
                        e.stopPropagation();
                        setFilterArea(area);
                        setFilterSubarea(sub);
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

        {/* Main content */}
        <div className="library-main-content">
          <div className="library-header">
            <div>
              <span className="eyebrow">
                {filterArea ? filterArea.name : "Gestión de archivos"}
              </span>
              <h2>
                {filterSubarea
                  ? filterSubarea.name
                  : filterArea
                  ? "Todos los videos del área"
                  : "Biblioteca de capacitaciones"}
              </h2>
              <p>
                Administra los materiales disponibles para consulta, documentación y
                revisión operativa.
              </p>
            </div>
            <div className="library-mini-stats">
              <span>
                <strong>{filteredVideos.length}</strong> Total
              </span>
            </div>
          </div>

          <div className="library-grid">
            {filteredVideos.map((video) => (
              <article key={video.id} className="library-card library-card-media">
                <div className="library-card-thumb">
                  <div className="library-card-icon-wrap">
                    <PlayCircle size={32} color="var(--green-700)" />
                  </div>
                  <div className="library-card-status-badge">
                    <StatusPill status={video.status} stage={video.processing_stage} />
                  </div>
                  <div className="library-card-duration">
                    {formatSeconds(video.duration_seconds)}
                  </div>
                </div>

                <div className="library-card-body">
                  <h3
                    className="library-card-title"
                    title={video.original_filename}
                  >
                    {video.original_filename}
                  </h3>

                  <div className="library-card-meta-list">
                    <div className="library-card-meta-item">
                      <Clock3 size={14} />
                      {formatDate(video.created_at)}
                    </div>
                    <div className="library-card-meta-item">
                      <Database size={14} />
                      {video.subarea_id
                        ? getSubareaLabel(video.subarea_id)
                        : "Sin área asignada"}
                    </div>
                    <div className="library-card-meta-item">
                      <FileText size={14} />
                      {video.segment_count} segmentos indexados
                    </div>
                  </div>

                  {video.status === "processing" && (
                    <ProgressBar value={video.processing_progress} />
                  )}

                  <button
                    className="secondary-button library-card-open"
                    type="button"
                    onClick={() => navigate(`/videos/${video.id}`)}
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
    </>
  );
}
