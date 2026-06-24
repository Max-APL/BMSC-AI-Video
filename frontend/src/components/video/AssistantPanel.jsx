import React from "react";
import {
  ArrowRight,
  Bot,
  Clock3,
  Loader2,
  PlayCircle,
  Search,
  Send,
} from "lucide-react";
import { cx } from "@/utils/cx";
import { EmptyState } from "@/components/common/EmptyState";
import { TranscriptPanel } from "./TranscriptPanel";
import "./AssistantPanel.css";

export function AssistantPanel({
  video,
  transcript,
  question,
  setQuestion,
  answer,
  loading,
  onAsk,
  onSeek,
  activeTab,
  setActiveTab,
}) {
  return (
    <section className="workspace">
      {/* Assistant panel */}
      <div className="assistant-panel">
        <div className="panel-tabs">
          <button
            type="button"
            className={cx(activeTab === "assistant" && "active")}
            onClick={() => setActiveTab("assistant")}
          >
            <Bot size={16} />
            Asistente
          </button>
          <button
            type="button"
            className={cx(activeTab === "transcript" && "active")}
            onClick={() => setActiveTab("transcript")}
          >
            <Search size={16} />
            Transcripción
          </button>
        </div>

        {activeTab === "assistant" ? (
          <div className="assistant-content">
            <form className="question-box" onSubmit={onAsk}>
              <Search size={18} />
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Pregunta algo del video o escribe un término para encontrarlo"
                disabled={video.status !== "ready"}
              />
              <button
                className="send-button"
                type="submit"
                disabled={video.status !== "ready" || loading || !question.trim()}
              >
                {loading ? (
                  <Loader2 className="spin" size={17} />
                ) : (
                  <Send size={17} />
                )}
              </button>
            </form>

            {video.status !== "ready" && (
              <div className="processing-note">
                <Clock3 size={18} />
                <span>
                  El video estará disponible para preguntas cuando termine la
                  indexación.
                </span>
              </div>
            )}

            {!answer && video.status === "ready" && (
              <EmptyState
                icon={Bot}
                title="Busca dentro del video"
                body="Escribe una pregunta o una palabra clave; el asistente responderá con el fragmento exacto donde encontró evidencia."
              />
            )}

            {answer && (
              <div className="answer-card">
                <div className="answer-header">
                  <div>
                    <span className="eyebrow">Respuesta</span>
                    <h3>{answer.question}</h3>
                    <small>
                      {answer.mode === "llm"
                        ? `Redactada con LLM${answer.model ? ` · ${answer.model}` : ""}`
                        : "Respuesta extractiva"}
                      {answer.fallback_reason ? " · fallback local" : ""}
                    </small>
                  </div>
                  <span className="confidence">
                    {Math.round((answer.confidence || 0) * 100)}%
                  </span>
                </div>
                {answer.fallback_reason && (
                  <p className="answer-fallback">
                    No se pudo usar el modelo local, se muestra la mejor respuesta
                    extractiva disponible.
                  </p>
                )}
                <p>{answer.answer}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="transcript-list">
            {transcript.length === 0 ? (
              <EmptyState
                icon={Search}
                title="Transcripción no disponible"
                body="Cuando el video esté listo, aquí verás los segmentos con timestamps."
              />
            ) : (
              transcript.map((segment) => (
                <article key={segment.id} className="transcript-row">
                  <button
                    type="button"
                    className="timestamp-button"
                    onClick={() => onSeek(segment.start_seconds)}
                    title={`Reproducir desde ${segment.start_timecode}`}
                  >
                    <PlayCircle size={15} />
                    {segment.start_timecode}
                  </button>
                  <p>{segment.text}</p>
                </article>
              ))
            )}
          </div>
        )}
      </div>

      {/* Sources panel */}
      <aside className="sources-panel">
        <div className="panel-heading">
          <h3>Fuentes</h3>
          <span>{answer?.sources?.length || 0}</span>
        </div>
        {!answer?.sources?.length ? (
          <EmptyState
            icon={ArrowRight}
            title="Sin fuentes"
            body="Las evidencias aparecerán después de preguntar."
          />
        ) : (
          <div className="source-list">
            {answer.sources.map((source) => (
              <article key={source.id} className="source-card">
                <div className="source-card-top">
                  <span>
                    {source.start_timecode} - {source.end_timecode}
                  </span>
                  <div className="source-actions">
                    <strong>{Math.round(source.score * 100)}%</strong>
                    <button
                      type="button"
                      className="source-play-button"
                      onClick={() => onSeek(source.start_seconds)}
                      title={`Reproducir desde ${source.start_timecode}`}
                      aria-label={`Reproducir fuente desde ${source.start_timecode}`}
                    >
                      <PlayCircle size={16} />
                    </button>
                  </div>
                </div>
                <p>{source.text}</p>
              </article>
            ))}
          </div>
        )}
      </aside>
    </section>
  );
}
