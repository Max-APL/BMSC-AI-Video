import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock3, FileText, FolderOpen, PlayCircle, Search } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import { EmptyState } from "@/components/common/EmptyState";
import { AreaAssignmentChip } from "@/components/common/AreaAssignmentChip";
import { formatDate, formatSeconds } from "@/utils/format";
import { useVideos } from "@/context/VideosContext";
import { useAreas } from "@/context/AreasContext";
import { thumbnailUrl } from "@/services/videos";
import { cx } from "@/utils/cx";
import "./LibraryPage.css";

export function LibraryPage() {
  const navigate = useNavigate();
  const { videos } = useVideos();
  const { areas } = useAreas();

  const [filterArea, setFilterArea] = useState(null);
  const [filterSubarea, setFilterSubarea] = useState(null);
  const [search, setSearch] = useState("");

  const scopedVideos = videos.filter((v) => {
    if (filterSubarea) return v.subarea_id === filterSubarea.id;
    if (filterArea) {
      const subIds = filterArea.subareas.map((s) => s.id);
      return subIds.includes(v.subarea_id);
    }
    return true;
  });
  const searchTerm = search.trim().toLowerCase();
  const filteredVideos = scopedVideos.filter(
    (video) =>
      !searchTerm || video.original_filename.toLowerCase().includes(searchTerm)
  );

  function getSubareaLabel(subareaId) {
    if (!subareaId) return "Sin área asignada";
    let label = "";
    areas.forEach((a) =>
      a.subareas.forEach((s) => {
        if (s.id === subareaId) label = `${a.name} > ${s.name}`;
      })
    );
    return label || "Sin área asignada";
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
                <strong>{scopedVideos.length}</strong> Total
              </span>
              {searchTerm && (
                <span>
                  <strong>{filteredVideos.length}</strong> Resultados
                </span>
              )}
            </div>
          </div>

          <label className="library-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={
                filterArea
                  ? "Buscar video dentro del área..."
                  : "Buscar video en la biblioteca..."
              }
            />
          </label>

          <div className="library-grid">
            {filteredVideos.length === 0 && (
              <EmptyState
                icon={Search}
                title="Sin videos encontrados"
                body={
                  searchTerm
                    ? "Prueba con otro nombre o limpia la búsqueda."
                    : "No hay videos registrados en esta selección."
                }
              />
            )}
            {filteredVideos.map((video) => (
              <article key={video.id} className="library-card library-card-media">
                <div className="library-card-thumb">
                  <div className="library-card-icon-wrap">
                    <PlayCircle size={34} color="var(--green-700)" />
                  </div>
                  <img
                    className="library-card-thumb-image"
                    src={thumbnailUrl(video.id)}
                    alt=""
                    loading="lazy"
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                    }}
                  />
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
                      <AreaAssignmentChip
                        label={getSubareaLabel(video.subarea_id)}
                        unassigned={!video.subarea_id}
                      />
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
