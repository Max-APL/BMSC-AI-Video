import React from "react";

export function ProgressBar({ value = 0 }) {
  const progress = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div className="progress-shell" aria-label={`Progreso ${progress}%`}>
      <div className="progress-fill" style={{ width: `${progress}%` }} />
    </div>
  );
}
