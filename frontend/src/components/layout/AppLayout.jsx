import React from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { useVideos } from "@/context/VideosContext";

export function AppLayout() {
  const { error } = useVideos();

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-panel">
        <Outlet />
        {error && <ErrorAlert message={error} />}
      </main>
    </div>
  );
}
