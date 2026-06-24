import { useState, useCallback, useEffect } from "react";
import { listUsers } from "@/services/users";
import { useAuth } from "@/context/AuthContext";

export function useUsers() {
  const { token } = useAuth();
  const [usersList, setUsersList] = useState([]);

  const loadUsersList = useCallback(async () => {
    if (!token) return;
    try {
      const data = await listUsers();
      setUsersList(data);
    } catch {
      // ignore
    }
  }, [token]);

  useEffect(() => {
    if (token) loadUsersList();
  }, [token, loadUsersList]);

  return { usersList, loadUsersList };
}
