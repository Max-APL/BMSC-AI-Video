import React, { useState } from "react";
import { Topbar } from "@/components/layout/Topbar";
import { useVideos } from "@/context/VideosContext";
import { useAreas } from "@/context/AreasContext";
import { createArea, createSubarea } from "@/services/areas";
import "./OrganizationPage.css";

export function OrganizationPage() {
  const { loading, setLoading, setError } = useVideos();
  const { areas, loadAreas } = useAreas();

  const [newAreaName, setNewAreaName] = useState("");
  const [newSubareaNames, setNewSubareaNames] = useState({});

  async function handleCreateArea(e) {
    e.preventDefault();
    if (!newAreaName.trim()) return;
    setLoading(true);
    try {
      await createArea(newAreaName.trim());
      setNewAreaName("");
      await loadAreas();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateSubarea(e, areaId) {
    e.preventDefault();
    const name = newSubareaNames[areaId] || "";
    if (!name.trim()) return;
    setLoading(true);
    try {
      await createSubarea(areaId, name.trim());
      setNewSubareaNames((prev) => ({ ...prev, [areaId]: "" }));
      await loadAreas();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Topbar />
      <section className="library-surface">
        <div className="library-header">
          <div>
            <span className="eyebrow">Configuración</span>
            <h2>Estructura Organizacional</h2>
            <p>
              Gestiona áreas y subáreas para clasificar el contenido de la
              institución.
            </p>
          </div>
        </div>

        <div className="library-grid org-grid-mt">
          {/* New area card */}
          <div className="area-card area-card-new">
            <h3 className="area-card-new-title">Nueva Área</h3>
            <form className="add-form" onSubmit={handleCreateArea}>
              <input
                placeholder="Nombre del área..."
                value={newAreaName}
                onChange={(e) => setNewAreaName(e.target.value)}
                disabled={loading}
              />
              <button
                className="primary-button compact"
                type="submit"
                disabled={loading || !newAreaName.trim()}
              >
                Crear
              </button>
            </form>
          </div>

          {/* Existing areas */}
          {areas.map((area) => (
            <div className="area-card" key={area.id}>
              <h3>
                {area.name} <span>({area.subareas.length})</span>
              </h3>
              <div className="subarea-list">
                {area.subareas.map((sub) => (
                  <div key={sub.id} className="subarea-item">
                    {sub.name}
                  </div>
                ))}
              </div>
              <form
                className="add-form"
                onSubmit={(e) => handleCreateSubarea(e, area.id)}
              >
                <input
                  placeholder="Nueva subárea..."
                  value={newSubareaNames[area.id] || ""}
                  onChange={(e) =>
                    setNewSubareaNames((prev) => ({
                      ...prev,
                      [area.id]: e.target.value,
                    }))
                  }
                  disabled={loading}
                />
                <button
                  className="secondary-button compact"
                  type="submit"
                  disabled={loading || !newSubareaNames[area.id]?.trim()}
                >
                  Añadir
                </button>
              </form>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
