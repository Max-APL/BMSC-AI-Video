import React from "react";
import { useLocation, useParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useVideos } from "@/context/VideosContext";
import "./Topbar.css";

const VIEW_META = {
  "/": {
    eyebrow: "Panel principal",
    title: "Centro de capacitación inteligente",
    description: "Vista general de videos cargados, procesamiento y contenido indexado.",
  },
  "/upload": {
    eyebrow: "Carga de video",
    title: "Ingreso de material audiovisual",
    description: "Carga nuevos videos y revisa el historial reciente de procesamiento.",
  },
  "/library": {
    eyebrow: "Biblioteca",
    title: "Repositorio audiovisual",
    description:
      "Explora todos los videos disponibles y abre la gestión individual de cada material.",
  },
  "/organization": {
    eyebrow: "Configuración",
    title: "Organización",
    description: "Gestiona la estructura de áreas y subáreas de la institución.",
  },
  "/users": {
    eyebrow: "Administración",
    title: "Usuarios",
    description: "Gestión de cuentas y accesos.",
  },
  "/roles": {
    eyebrow: "Seguridad",
    title: "Roles y Permisos",
    description: "Definición de permisos granulares.",
  },
};

export function Topbar({ actions }) {
  const location = useLocation();
  const { id: videoId } = useParams();
  const { videos } = useVideos();

  let meta = VIEW_META[location.pathname];

  if (!meta && videoId) {
    const video = videos.find((v) => v.id === videoId);
    meta = {
      eyebrow: "Expediente del video",
      title: video?.original_filename || "Video seleccionado",
      description:
        "Reproductor, consulta con fuentes, manuales y transcripción pertenecen a este video.",
    };
  }

  meta = meta || VIEW_META["/"];

  return (
    <header className="topbar">
      <div>
        <span className="eyebrow">{meta.eyebrow}</span>
        <h1>{meta.title}</h1>
        <p>{meta.description}</p>
      </div>
      <div className="topbar-actions">
        <div className="bank-chip">
          <ShieldCheck size={15} />
          Entorno institucional
        </div>
        {actions}
      </div>
    </header>
  );
}
