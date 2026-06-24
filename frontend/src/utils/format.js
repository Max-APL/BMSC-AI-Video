export function formatSeconds(seconds) {
  if (seconds === null || seconds === undefined) return "Sin duración";
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatDate(value) {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-BO", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
  }).format(new Date(value));
}

export function formatDateTime(value) {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-BO", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function formatLanguage(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["es", "spa", "spanish", "español", "espanol"].includes(normalized)) return "Español";
  if (["en", "eng", "english", "inglés", "ingles"].includes(normalized)) return "Inglés";
  return "No determinado";
}

export function formatTranscriptionEngine(video) {
  if (!video || video.status === "uploaded") return "Pendiente";
  if (video.status === "failed") return "Fallida";
  return "Faster-Whisper";
}
