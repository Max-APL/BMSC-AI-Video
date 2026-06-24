import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

/**
 * Redirects to "/" if the current user lacks the specified permission.
 * Use as a wrapper inside a ProtectedRoute.
 */
export function RequirePermission({ permission, children }) {
  const { hasPermission } = useAuth();
  if (!hasPermission(permission)) return <Navigate to="/" replace />;
  return children;
}
