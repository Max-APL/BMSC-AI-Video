import React, { useState } from "react";
import { AlertCircle } from "lucide-react";
import { cx } from "@/utils/cx";
import { formatSeconds } from "@/utils/format";
import "./VideoPlayer.css";

export function VideoPlayer({ video, mediaUrl, videoRef, className = "" }) {
  const [playerError, setPlayerError] = useState("");

  if (!video) return null;

  return (
    <section className={cx("player-surface", className)}>
      <div className="player-header">
        <div>
          <span className="eyebrow">Video seleccionado</span>
          <h3>{video.original_filename}</h3>
        </div>
        <span>{formatSeconds(video.duration_seconds)}</span>
      </div>

      <div className="video-frame">
        <video
          key={video.id}
          ref={videoRef}
          controls
          preload="metadata"
          src={mediaUrl}
          crossOrigin="anonymous"
          onLoadedMetadata={() => setPlayerError("")}
          onError={() =>
            setPlayerError(
              "El navegador no pudo reproducir este archivo. Si es MKV o usa un codec no soportado, prueba con MP4 H.264/AAC para reproducción embebida."
            )
          }
        />
      </div>

      {playerError ? (
        <div className="inline-warning">
          <AlertCircle size={17} />
          <span>{playerError}</span>
        </div>
      ) : (
        <p className="player-note">
          Los botones de reproducción en fuentes y transcripción saltan a este
          video en el momento exacto.
        </p>
      )}
    </section>
  );
}
