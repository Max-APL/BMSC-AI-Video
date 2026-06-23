import { useState, useCallback, useEffect } from "react";
import { listRoles } from "@/services/roles";
import { useAuth } from "@/context/AuthContext";

export function useRoles() {
  const { token } = useAuth();
  const [roles, setRoles] = useState([]);

  const loadRoles = useCallback(async () => {
    if (!token) return;
    try {
      const data = await listRoles();
      setRoles(data);
    } catch {
      // ignore
    }
  }, [token]);

  useEffect(() => {
    if (token) loadRoles();
  }, [token, loadRoles]);

  return { roles, loadRoles };
}
