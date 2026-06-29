import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import bmscLogo from "@/assets/bmsc-logo.png";
import {
  completeFirstLogin,
  confirmPasswordReset,
  login,
  requestPasswordReset,
} from "@/services/auth";
import { useAuth } from "@/context/AuthContext";
import "./LoginPage.css";

export function LoginPage() {
  const navigate = useNavigate();
  const { login: setToken } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [mode, setMode] = useState("login");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const validateEmail = () => {
    setError("");
    return true;
  };

  const finishLogin = (payload) => {
    setToken(payload.access_token);
    navigate("/", { replace: true });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setNotice("");
    if (!validateEmail()) return;
    setLoading(true);
    try {
      const payload = await login(email, password);
      if (payload.status === "password_change_required") {
        setMode("first-login");
        setCode("");
        setNewPassword("");
        setNotice(payload.detail || "Te enviamos un código de verificación.");
        return;
      }
      finishLogin(payload);
    } catch (err) {
      if (err.status === 423) {
        setError("Cuenta bloqueada temporalmente por intentos fallidos. Revisa tu correo o contacta a un administrador.");
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordResetRequest = async (e) => {
    e.preventDefault();
    setNotice("");
    if (!validateEmail()) return;
    setLoading(true);
    try {
      const response = await requestPasswordReset(email);
      setMode("reset-confirm");
      setCode("");
      setNewPassword("");
      setNotice(response.message || "Si el correo existe, enviaremos un código de recuperación.");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteFirstLogin = async (e) => {
    e.preventDefault();
    setError("");
    setNotice("");
    if (!validateEmail()) return;
    setLoading(true);
    try {
      const payload = await completeFirstLogin({
        email,
        code,
        new_password: newPassword,
      });
      finishLogin(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmReset = async (e) => {
    e.preventDefault();
    setError("");
    setNotice("");
    if (!validateEmail()) return;
    setLoading(true);
    try {
      const payload = await confirmPasswordReset({
        email,
        code,
        new_password: newPassword,
      });
      finishLogin(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const backToLogin = () => {
    setMode("login");
    setCode("");
    setNewPassword("");
    setError("");
    setNotice("");
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
        {mode === "login" && (
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
          {notice && <div className="login-notice">{notice}</div>}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Iniciando..." : "Ingresar"}
          </button>
          <button
            className="text-button"
            type="button"
            disabled={loading}
            onClick={() => {
              setMode("reset-request");
              setError("");
              setNotice("");
            }}
          >
            Olvidé mi contraseña
          </button>
        </form>
        )}

        {mode === "reset-request" && (
          <form onSubmit={handlePasswordResetRequest} className="login-form">
            <input
              type="email"
              placeholder="Correo electrónico (@bmsc.com.bo)"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            {error && (
              <div className="alert">
                <AlertCircle size={15} />
                {error}
              </div>
            )}
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Enviando..." : "Enviar código"}
            </button>
            <button className="text-button" type="button" onClick={backToLogin}>
              Volver al inicio de sesión
            </button>
          </form>
        )}

        {(mode === "first-login" || mode === "reset-confirm") && (
          <form
            onSubmit={mode === "first-login" ? handleCompleteFirstLogin : handleConfirmReset}
            className="login-form"
          >
            {notice && <div className="login-notice">{notice}</div>}
            <input
              type="email"
              placeholder="Correo electrónico (@bmsc.com.bo)"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <input
              type="text"
              inputMode="numeric"
              placeholder="Código de verificación"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder="Nueva contraseña"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
            />
            {error && (
              <div className="alert">
                <AlertCircle size={15} />
                {error}
              </div>
            )}
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Confirmando..." : "Guardar contraseña"}
            </button>
            <button className="text-button" type="button" onClick={backToLogin}>
              Volver al inicio de sesión
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
