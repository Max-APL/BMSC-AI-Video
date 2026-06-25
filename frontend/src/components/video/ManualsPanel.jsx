import React from "react";
import {
  BookOpen,
  Bot,
  Download,
  FileText,
  Loader2,
  Trash2,
} from "lucide-react";
import { formatDateTime } from "@/utils/format";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import { EmptyState } from "@/components/common/EmptyState";
import { MarkdownDocument } from "@/components/markdown/MarkdownDocument";
import "./ManualsPanel.css";

const GENERATING_STATUSES = new Set(["processing", "queued"]);

function mergePreviewManual(manuals, manualPreview) {
  const previewManual = manualPreview?.metadata;
  if (!previewManual) return manuals;

  const exists = manuals.some((manual) => manual.id === previewManual.id);
  const merged = exists
    ? manuals.map((manual) =>
        manual.id === previewManual.id ? { ...manual, ...previewManual } : manual
      )
    : [previewManual, ...manuals];

  return merged;
}

function manualLiveMessage(metadata) {
  if (metadata.last_generated_text) return metadata.last_generated_text;
  if (metadata.current_section) return metadata.current_section;
  if ((metadata.progress || 0) > 0) return "Preparando contenido del manual...";
  return "Esperando el inicio de la generación...";
}

export function ManualsPanel({
  video,
  manuals,
  manualQualityMode,
  setManualQualityMode,
  manualPreview,
  generatingManual,
  loading,
  hasGeneratePermission,
  onGenerate,
  onPreview,
  onDownload,
  onDeleteRequest,
  getAssetsUrl,
}) {
  const visibleManuals = mergePreviewManual(manuals, manualPreview);

  return (
    <section className="manual-surface">
      <div className="manual-header">
        <div>
          <span className="eyebrow">Documentación</span>
          <h3>Manuales y Guías</h3>
        </div>

        {hasGeneratePermission && (
          <div className="manual-controls">
            <div className="manual-mode-chip">
              <Bot size={16} />
              LLM local
            </div>

            <div className="segmented-control" aria-label="Calidad de generación">
              <button
                type="button"
                className={manualQualityMode === "fast" ? "active" : ""}
                onClick={() => setManualQualityMode("fast")}
                disabled={generatingManual}
              >
                Rápido
              </button>
              <button
                type="button"
                className={manualQualityMode === "quality" ? "active" : ""}
                onClick={() => setManualQualityMode("quality")}
                disabled={generatingManual}
              >
                Calidad
              </button>
            </div>

            <button
              className="primary-button"
              type="button"
              onClick={onGenerate}
              disabled={video.status !== "ready" || generatingManual}
            >
              {generatingManual ? (
                <Loader2 className="spin" size={17} />
              ) : (
                <BookOpen size={17} />
              )}
              Generar manual
            </button>
          </div>
        )}
      </div>

      {/* Manual list */}
      <div className="manual-list">
        {visibleManuals.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="Sin manuales"
            body="Genera un manual profesional redactado con LLM local."
          />
        ) : (
          visibleManuals.map((manual) => (
            <article key={manual.id} className="manual-card">
              <div className="manual-card-main">
                <div className="manual-card-icon">
                  <BookOpen size={18} />
                </div>
                <div>
                  <strong>{manual.title}</strong>
                  <span>
                    {manual.mode === "llm"
                      ? `LLM · ${manual.model || "modelo local"}`
                      : "Manual histórico"}
                    {manual.quality_mode === "quality" ? " · Calidad" : " · Rápido"}
                    {" · "}
                    {manual.section_count} secciones · {manual.word_count} palabras
                    {manual.screenshot_count
                      ? ` · ${manual.screenshot_count} capturas`
                      : ""}
                    {" · "}
                    Creado {formatDateTime(manual.created_at)}
                  </span>
                </div>
              </div>
              <div className="manual-card-actions">
                <StatusPill status={manual.status} />
                <button
                  className="secondary-button compact"
                  type="button"
                  onClick={() => onPreview(manual)}
                  disabled={manual.status === "failed" || loading}
                >
                  <FileText size={15} />
                  Ver
                </button>
                <button
                  className="secondary-button compact"
                  type="button"
                  onClick={() => onDownload(manual, "docx")}
                  disabled={manual.status !== "ready"}
                >
                  <Download size={15} />
                  DOCX
                </button>
                <button
                  className="secondary-button compact"
                  type="button"
                  onClick={() => onDownload(manual, "pdf")}
                  disabled={manual.status !== "ready"}
                >
                  <Download size={15} />
                  PDF
                </button>
                <button
                  className="secondary-button compact"
                  type="button"
                  onClick={() => onDeleteRequest(manual)}
                  disabled={loading}
                >
                  <Trash2 size={15} />
                  Eliminar
                </button>
              </div>

              {GENERATING_STATUSES.has(manual.status) && (
                <div className="manual-generation-status">
                  <div>
                    <span>{manual.current_section || "Preparando generación"}</span>
                    <strong>{Math.round(manual.progress || 0)}%</strong>
                  </div>
                  <ProgressBar value={manual.progress} />
                  {manual.last_generated_text && <p>{manual.last_generated_text}</p>}
                </div>
              )}

              {manual.error && <p className="manual-error">{manual.error}</p>}
            </article>
          ))
        )}
      </div>

      {/* Preview */}
      {manualPreview?.metadata && (
        <div className="manual-preview">
          <div className="manual-preview-header">
            <div>
              <strong>{manualPreview.metadata.filename}</strong>
              <span>
                {manualPreview.metadata.status === "ready"
                  ? `Vista previa renderizada · Creado ${formatDateTime(manualPreview.metadata.created_at)}`
                  : `${manualPreview.metadata.current_section || "Generando"} · ${Math.round(manualPreview.metadata.progress || 0)}% · Creado ${formatDateTime(manualPreview.metadata.created_at)}`}
              </span>
            </div>
            <div className="manual-download-group">
              <button
                className="secondary-button compact"
                type="button"
                onClick={() => onDownload(manualPreview.metadata, "markdown")}
                disabled={manualPreview.metadata.status !== "ready"}
              >
                <Download size={15} />
                MD
              </button>
              <button
                className="secondary-button compact"
                type="button"
                onClick={() => onDownload(manualPreview.metadata, "docx")}
                disabled={manualPreview.metadata.status !== "ready"}
              >
                <Download size={15} />
                DOCX
              </button>
              <button
                className="secondary-button compact"
                type="button"
                onClick={() => onDownload(manualPreview.metadata, "pdf")}
                disabled={manualPreview.metadata.status !== "ready"}
              >
                <Download size={15} />
                PDF
              </button>
            </div>
          </div>

          {GENERATING_STATUSES.has(manualPreview.metadata.status) && (
            <div className="manual-live-strip">
              <ProgressBar value={manualPreview.metadata.progress} />
              <p>{manualLiveMessage(manualPreview.metadata)}</p>
            </div>
          )}

          <MarkdownDocument
            content={manualPreview.content || ""}
            assetBaseUrl={getAssetsUrl(manualPreview.metadata.id)}
          />
        </div>
      )}
    </section>
  );
}
