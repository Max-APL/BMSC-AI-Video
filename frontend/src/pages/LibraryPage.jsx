import React, { useEffect, useMemo, useState } from "react";
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

const UNASSIGNED_NAV_ID = "__unassigned__";

export function LibraryPage() {
  const navigate = useNavigate();
  const { videos } = useVideos();
  const { areas } = useAreas();

  const [selectedAreaId, setSelectedAreaId] = useState(null);
  const [selectedSubareaId, setSelectedSubareaId] = useState(null);
  const [search, setSearch] = useState("");

  const libraryIndex = useMemo(() => {
    const subareaToArea = new Map();
    const areaVideoCounts = new Map(areas.map((area) => [area.id, 0]));
    const subareaVideoCounts = new Map();
    let unassignedCount = 0;

    areas.forEach((area) => {
      area.subareas.forEach((subarea) => {
        subareaToArea.set(subarea.id, area.id);
        subareaVideoCounts.set(subarea.id, 0);
      });
    });

    videos.forEach((video) => {
      if (!video.subarea_id) {
        unassignedCount += 1;
        return;
      }

      const areaId = subareaToArea.get(video.subarea_id);
      if (!areaId) return;

      areaVideoCounts.set(areaId, (areaVideoCounts.get(areaId) || 0) + 1);
      subareaVideoCounts.set(
        video.subarea_id,
        (subareaVideoCounts.get(video.subarea_id) || 0) + 1
      );
    });

    return {
      areaVideoCounts,
      subareaVideoCounts,
      unassignedCount,
    };
  }, [areas, videos]);

  const hasUnassignedVideos = libraryIndex.unassignedCount > 0;
  const selectedArea = areas.find((area) => area.id === selectedAreaId) || null;
  const selectedSubarea =
    selectedArea?.subareas.find((subarea) => subarea.id === selectedSubareaId) ||
    null;
  const isUnassignedSelected = selectedAreaId === UNASSIGNED_NAV_ID;

  useEffect(() => {
    if (selectedAreaId === UNASSIGNED_NAV_ID && hasUnassignedVideos) return;
    if (selectedAreaId && areas.some((area) => area.id === selectedAreaId)) return;

    if (areas.length > 0) {
      setSelectedAreaId(areas[0].id);
      setSelectedSubareaId(null);
      return;
    }

    if (hasUnassignedVideos) {
      setSelectedAreaId(UNASSIGNED_NAV_ID);
      setSelectedSubareaId(null);
      return;
    }

    setSelectedAreaId(null);
    setSelectedSubareaId(null);
  }, [areas, hasUnassignedVideos, selectedAreaId]);

  useEffect(() => {
    if (!selectedArea || !selectedSubareaId) return;
    const stillExists = selectedArea.subareas.some(
      (subarea) => subarea.id === selectedSubareaId
    );
    if (!stillExists) setSelectedSubareaId(null);
  }, [selectedArea, selectedSubareaId]);

  const scopedVideos = videos.filter((video) => {
    if (isUnassignedSelected) return !video.subarea_id;
    if (selectedSubarea) return video.subarea_id === selectedSubarea.id;
    if (selectedArea) {
      const subareaIds = selectedArea.subareas.map((subarea) => subarea.id);
      return subareaIds.includes(video.subarea_id);
    }
    return false;
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
        <aside className="library-area-nav" aria-label="Áreas disponibles">
          <div className="library-header library-area-header">
            <div>
              <span className="eyebrow">Navegación</span>
              <h2>Áreas disponibles</h2>
              <p>Selecciona un área para revisar sus capacitaciones.</p>
            </div>
          </div>

          <div className="library-area-list">
            {areas.map((area) => (
              <article
                key={area.id}
                className={cx(
                  "library-area-card",
                  selectedAreaId === area.id && "area-active"
                )}
              >
                <button
                  type="button"
                  className="library-area-button"
                  onClick={() => {
                    setSelectedAreaId(area.id);
                    setSelectedSubareaId(null);
                    setSearch("");
                  }}
                >
                  <h3>
                    {area.name}
                    <span>{libraryIndex.areaVideoCounts.get(area.id) || 0}</span>
                  </h3>
                </button>
                <div className="library-subarea-list">
                  {area.subareas.map((sub) => (
                    <button
                      type="button"
                      key={sub.id}
                      className={cx(
                        "library-subarea-item",
                        selectedSubareaId === sub.id && "subarea-active"
                      )}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedAreaId(area.id);
                        setSelectedSubareaId(sub.id);
                        setSearch("");
                      }}
                    >
                      <span>{sub.name}</span>
                      <strong>
                        {libraryIndex.subareaVideoCounts.get(sub.id) || 0}
                      </strong>
                    </button>
                  ))}
                </div>
              </article>
            ))}

            {hasUnassignedVideos && (
              <button
                type="button"
                className={cx(
                  "library-area-card",
                  isUnassignedSelected && "area-active"
                )}
                onClick={() => {
                  setSelectedAreaId(UNASSIGNED_NAV_ID);
                  setSelectedSubareaId(null);
                  setSearch("");
                }}
              >
                <h3>
                  Pendientes de asignación
                  <span>{libraryIndex.unassignedCount}</span>
                </h3>
              </button>
            )}
          </div>
        </aside>

        <div className="library-main-content">
          <div className="library-header">
            <div>
              <span className="eyebrow">
                {selectedArea?.name ||
                  (isUnassignedSelected
                    ? "Videos sin área"
                    : "Biblioteca institucional")}
              </span>
              <h2>
                {selectedSubarea?.name ||
                  selectedArea?.name ||
                  (isUnassignedSelected
                    ? "Pendientes de asignación"
                    : "Biblioteca de capacitaciones")}
              </h2>
              <p>
                Consulta los materiales disponibles del área seleccionada y abre el
                expediente correspondiente para revisar video, transcripción y
                documentación.
              </p>
            </div>
            <div className="library-mini-stats">
              <span>
                <strong>{scopedVideos.length}</strong> Videos
              </span>
              {selectedArea && (
                <span>
                  <strong>{selectedArea.subareas.length}</strong> Subáreas
                </span>
              )}
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
                selectedSubarea
                  ? "Buscar video dentro de esta subárea..."
                  : "Buscar video dentro del área seleccionada..."
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
                    : "No hay videos registrados para esta área."
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
