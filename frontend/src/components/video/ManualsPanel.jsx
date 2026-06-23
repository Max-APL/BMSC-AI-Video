import React from "react";
import {
  BookOpen,
  Bot,
  Download,
  FileText,
  Loader2,
  Trash2,
} from "lucide-react";
import { cx } from "@/utils/cx";
import { formatDateTime } from "@/utils/format";
import { StatusPill } from "@/components/common/StatusPill";
import { ProgressBar } from "@/components/common/ProgressBar";
import { EmptyState } from "@/components/common/EmptyState";
import { MarkdownDocument } from "@/components/markdown/MarkdownDocument";
import "./ManualsPanel.css";

export function ManualsPanel({
  video,
  manuals,
  manualMode,
  setManualMode,
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
  return (
    <section className="manual-surface">
      <div className="manual-header">
        <div>
          <span className="eyebrow">Documentación</span>
          <h3>Manuales y Guías</h3>
        </div>

        {hasGeneratePermission && (
          <div className="manual-controls">
            <div className="segmented-control">
              <button
                type="button"
                className={cx(manualMode === "extractive" && "active")}
                onClick={() => setManualMode("extractive")}
              >
                <FileText size={16} />
                Extractivo
              </button>
              <button
                type="button"
                className={cx(manualMode === "llm" && "active")}
                onClick={() => setManualMode("llm")}
              >
                <Bot size={16} />
                Redactado con LLM
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
        {manuals.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="Sin manuales"
            body="Genera una versión extractiva o una versión redactada con LLM."
          />
        ) : (
          manuals.map((manual) => (
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
                      : "Extractivo"}
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

              {(manual.status === "processing" || manual.status === "queued") && (
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

          {(manualPreview.metadata.status === "processing" ||
            manualPreview.metadata.status === "queued") && (
            <div className="manual-live-strip">
              <ProgressBar value={manualPreview.metadata.progress} />
              <p>
                {manualPreview.metadata.last_generated_text ||
                  "Esperando las primeras palabras del modelo..."}
              </p>
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
