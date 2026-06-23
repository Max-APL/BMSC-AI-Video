export const statusLabels = {
  uploaded: "Subido",
  processing: "Procesando",
  ready: "Listo",
  failed: "Falló",
};

export const stageLabels = {
  queued: "En cola",
  starting: "Iniciando",
  extracting_audio: "Extrayendo audio",
  transcribing: "Transcribiendo",
  indexing: "Indexando",
  ready: "Listo",
  failed: "Falló",
  interrupted: "Interrumpido",
};

export const manualStatusLabels = {
  queued: "En cola",
  processing: "Generando",
  ready: "Listo",
  failed: "Falló",
};

export const availablePermissions = [
  { id: "view_dashboard", label: "Ver Dashboard" },
  { id: "view_videos", label: "Ver Gestión de Videos" },
  { id: "view_library", label: "Ver Biblioteca" },
  { id: "view_organization", label: "Ver Organización" },
  { id: "view_users", label: "Ver Usuarios" },
  { id: "view_roles", label: "Ver Roles" },
  { id: "upload_video", label: "Subir Videos" },
  { id: "generate_manual", label: "Generar Manuales" },
  { id: "manage_organization", label: "Gestionar Áreas" },
  { id: "manage_users", label: "Gestionar Usuarios" },
  { id: "manage_roles", label: "Gestionar Roles" },
];
