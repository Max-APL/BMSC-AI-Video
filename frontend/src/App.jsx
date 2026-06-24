import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { VideosProvider } from "@/context/VideosContext";
import { AreasProvider } from "@/context/AreasContext";
import { AppLayout } from "@/components/layout/AppLayout";
import { ProtectedRoute } from "@/components/routing/ProtectedRoute";
import { RequirePermission } from "@/components/routing/RequirePermission";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { UploadPage } from "@/pages/UploadPage";
import { LibraryPage } from "@/pages/LibraryPage";
import { OrganizationPage } from "@/pages/OrganizationPage";
import { UsersPage } from "@/pages/UsersPage";
import { RolesPage } from "@/pages/RolesPage";
import { VideoDetailPage } from "@/pages/VideoDetailPage";

function ProtectedLayout() {
  return (
    <ProtectedRoute>
      <VideosProvider>
        <AreasProvider>
          <AppLayout />
        </AreasProvider>
      </VideosProvider>
    </ProtectedRoute>
  );
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedLayout />}>
          <Route
            path="/"
            element={
              <RequirePermission permission="view_dashboard">
                <DashboardPage />
              </RequirePermission>
            }
          />
          <Route
            path="/upload"
            element={
              <RequirePermission permission="view_videos">
                <UploadPage />
              </RequirePermission>
            }
          />
          <Route
            path="/library"
            element={
              <RequirePermission permission="view_library">
                <LibraryPage />
              </RequirePermission>
            }
          />
          <Route
            path="/organization"
            element={
              <RequirePermission permission="view_organization">
                <OrganizationPage />
              </RequirePermission>
            }
          />
          <Route
            path="/users"
            element={
              <RequirePermission permission="view_users">
                <UsersPage />
              </RequirePermission>
            }
          />
          <Route
            path="/roles"
            element={
              <RequirePermission permission="view_roles">
                <RolesPage />
              </RequirePermission>
            }
          />
          <Route path="/videos/:id" element={<VideoDetailPage />} />
        </Route>

        {/* Fallback: redirect unknown paths to root */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
