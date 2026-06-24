import React from "react";
import { AlertCircle, Loader2, Trash2 } from "lucide-react";

export function DeleteManualModal({ manual, onConfirm, onClose, loading }) {
  if (!manual) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <AlertCircle size={24} />
          <h2>Eliminar manual</h2>
        </div>
        <div className="modal-body">
          <p>
            ¿Estás seguro de que quieres eliminar permanentemente el manual{" "}
            <strong>"{manual.title}"</strong>?
          </p>
          <p style={{ color: "var(--muted)", fontSize: "14px", marginTop: "8px" }}>
            Esta acción borrará el archivo de texto y sus imágenes adjuntas. No se
            puede deshacer.
          </p>
        </div>
        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button className="danger-button" type="button" onClick={onConfirm} disabled={loading}>
            {loading ? <Loader2 className="spin" size={17} /> : <Trash2 size={17} />}
            Eliminar
          </button>
        </div>
      </div>
    </div>
  );
}
