import React from "react";
import { Edit2, Loader2 } from "lucide-react";
import { useAreas } from "@/context/AreasContext";
import "./EditVideoModal.css";

export function EditVideoModal({ video, filename, subarea, onFilenameChange, onSubareaChange, onSave, onClose, loading }) {
  const { areas } = useAreas();
  if (!video) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="edit-modal-header">
          <Edit2 size={24} />
          <h2>Editar Video</h2>
        </div>

        <div className="edit-modal-body">
          <label className="edit-field">
            <span>Nombre del video</span>
            <input
              value={filename}
              onChange={(e) => onFilenameChange(e.target.value)}
              className="edit-input"
            />
          </label>

          <label className="edit-field">
            <span>Subárea asignada</span>
            <select
              value={subarea}
              onChange={(e) => onSubareaChange(e.target.value)}
              className="edit-select"
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
          </label>
        </div>

        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button
            className="primary-button"
            type="button"
            disabled={loading || !filename.trim()}
            onClick={onSave}
          >
            {loading ? <Loader2 className="spin" size={15} /> : "Guardar cambios"}
          </button>
        </div>
      </div>
    </div>
  );
}
