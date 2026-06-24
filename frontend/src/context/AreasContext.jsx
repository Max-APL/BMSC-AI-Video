import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from "react";
import { listAreas } from "@/services/areas";
import { useAuth } from "./AuthContext";

const AreasContext = createContext(null);

export function AreasProvider({ children }) {
  const { token } = useAuth();
  const [areas, setAreas] = useState([]);

  const loadAreas = useCallback(async () => {
    if (!token) return;
    try {
      const data = await listAreas();
      setAreas(data);
    } catch {
      // ignore silently
    }
  }, [token]);

  useEffect(() => {
    if (token) loadAreas();
  }, [token, loadAreas]);

  return (
    <AreasContext.Provider value={{ areas, loadAreas }}>
      {children}
    </AreasContext.Provider>
  );
}

export function useAreas() {
  const ctx = useContext(AreasContext);
  if (!ctx) throw new Error("useAreas must be used inside AreasProvider");
  return ctx;
}
