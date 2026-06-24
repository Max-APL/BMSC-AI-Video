import React from "react";
import { PlayCircle, Search } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import "./TranscriptPanel.css";

export function TranscriptPanel({ transcript, onSeek }) {
  return (
    <section className="transcript-surface">
      <div className="panel-heading">
        <h3>Transcripción por timestamp</h3>
        <span>{transcript.length}</span>
      </div>
      <div className="transcript-list transcript-list-standalone">
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
    </section>
  );
}
