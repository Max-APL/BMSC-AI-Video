import React from "react";
import { AlertTriangle, X } from "lucide-react";
import "./ConfirmDialog.css";

export function ConfirmDialog({
  isOpen,
  title,
  body,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  variant = "danger",
  loading = false,
  confirmDisabled = false,
  onConfirm,
  onClose,
}) {
  if (!isOpen) return null;

  const isInfo = variant === "info";
  const renderedBody =
    typeof body === "string" ? <p>{body}</p> : <div className="confirm-dialog-body">{body}</div>;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content confirm-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="confirm-dialog-header">
          <div className={isInfo ? "confirm-icon info" : "confirm-icon danger"}>
            <AlertTriangle size={20} />
          </div>
          <div>
            <h2>{title}</h2>
            {renderedBody}
          </div>
          <button
            className="close-btn"
            type="button"
            onClick={onClose}
            disabled={loading}
          >
            <X size={20} />
          </button>
        </div>

        <div className="confirm-dialog-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={onClose}
            disabled={loading}
          >
            {cancelLabel}
          </button>
          {!isInfo && (
            <button
              type="button"
              className="danger-button"
              onClick={onConfirm}
              disabled={loading || confirmDisabled}
            >
              {confirmLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
