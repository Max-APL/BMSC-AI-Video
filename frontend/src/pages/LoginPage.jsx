import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import bmscLogo from "@/assets/bmsc-logo.png";
import { login } from "@/services/auth";
import { useAuth } from "@/context/AuthContext";
import "./LoginPage.css";

export function LoginPage() {
  const navigate = useNavigate();
  const { login: setToken } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email.endsWith("@bmsc.com.bo")) {
      setError("Solo se permiten correos corporativos @bmsc.com.bo");
      return;
    }
    setLoading(true);
    try {
      const token = await login(email, password);
      setToken(token);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <img className="brand-logo" src={bmscLogo} alt="Mercantil Santa Cruz" />
        <h2>Centro IA Video</h2>
        <p>
          Inicia sesión para gestionar el material audiovisual y los manuales
          operativos.
        </p>
        <form onSubmit={handleSubmit} className="login-form">
          <input
            type="email"
            placeholder="Correo electrónico (@bmsc.com.bo)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Contraseña"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <div className="alert">
              <AlertCircle size={15} />
              {error}
            </div>
          )}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Iniciando..." : "Ingresar"}
          </button>
        </form>
      </div>
    </div>
  );
}
