import React from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import "./DeleteVideoModal.css";

export function DeleteVideoModal({ video, onConfirm, onClose, loading }) {
  if (!video) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="delete-modal-header">
          <AlertCircle size={24} />
          <h2>Eliminar video</h2>
        </div>
        <div className="delete-modal-body">
          <p>
            ¿Estás seguro de que quieres eliminar permanentemente el video{" "}
            <strong>"{video.original_filename}"</strong>?
          </p>
          <p className="delete-modal-warning">
            Esta acción borrará también todas las transcripciones y manuales
            asociados. No se puede deshacer.
          </p>
        </div>
        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button className="danger-button" type="button" onClick={onConfirm} disabled={loading}>
            {loading ? <Loader2 className="spin" size={15} /> : "Sí, eliminar"}
          </button>
        </div>
      </div>
    </div>
  );
}
