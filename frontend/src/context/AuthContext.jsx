import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { getCurrentUser } from "@/services/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem("bmsc_token") || "");
  const [currentUser, setCurrentUser] = useState(null);

  const login = useCallback((accessToken) => {
    localStorage.setItem("bmsc_token", accessToken);
    setToken(accessToken);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("bmsc_token");
    setToken("");
    setCurrentUser(null);
  }, []);

  const hasPermission = useCallback(
    (perm) => {
      if (!currentUser?.permissions) return false;
      return currentUser.permissions.includes(perm);
    },
    [currentUser]
  );

  const loadCurrentUser = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getCurrentUser();
      setCurrentUser(data);
    } catch (err) {
      if (err.message?.includes("401")) logout();
      else console.error("loadCurrentUser:", err);
    }
  }, [token, logout]);

  useEffect(() => {
    if (token) loadCurrentUser();
  }, [token, loadCurrentUser]);

  return (
    <AuthContext.Provider
      value={{ token, currentUser, login, logout, hasPermission, loadCurrentUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
