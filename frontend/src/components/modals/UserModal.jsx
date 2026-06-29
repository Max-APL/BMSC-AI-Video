import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import { cx } from "@/utils/cx";
import "./UserModal.css";

export function UserModal({
  isOpen,
  editingUser,
  roles,
  currentUser,
  loading = false,
  error = "",
  onClose,
  onSave,
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleId, setRoleId] = useState("");
  const [isDisabled, setIsDisabled] = useState(false);

  const isEditing = Boolean(editingUser);
  const isSuperAdmin = currentUser?.role === "Super Admin";
  const isSelf = editingUser?.id === currentUser?.id;
  const disableStatusToggle = Boolean(
    isEditing && (isSelf || (editingUser?.is_disabled && !isSuperAdmin))
  );

  useEffect(() => {
    if (!isOpen) return;
    setName(editingUser?.name ?? "");
    setEmail(editingUser?.email ?? "");
    setPassword("");
    setRoleId(editingUser?.role_id ?? "");
    setIsDisabled(Boolean(editingUser?.is_disabled));
  }, [isOpen, editingUser]);

  if (!isOpen) return null;

  function handleSubmit(event) {
    event.preventDefault();
    const payload = {
      name: name.trim(),
      email: email.trim(),
      role_id: roleId,
    };

    if (password.trim()) {
      payload.password = password;
    }

    if (!isEditing) {
      payload.password = password;
    } else {
      payload.is_disabled = isDisabled;
    }

    onSave(payload);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content user-modal-content"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2>{isEditing ? "Editar usuario" : "Crear nuevo usuario"}</h2>
          <button className="close-btn" type="button" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {error && <p className="modal-error">{error}</p>}

        <form className="user-modal-form" onSubmit={handleSubmit}>
          <label className="user-modal-field">
            <span>Nombre completo</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ej. María Fernanda Rojas"
              disabled={loading}
              required
            />
          </label>

          <label className="user-modal-field">
            <span>Correo corporativo</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="usuario@bmsc.com.bo"
              disabled={loading}
              required
            />
          </label>

          <label className="user-modal-field">
            <span>Rol asignado</span>
            <select
              value={roleId}
              onChange={(event) => setRoleId(event.target.value)}
              disabled={loading}
              required
            >
              <option value="">Seleccionar rol...</option>
              {roles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name}
                </option>
              ))}
            </select>
          </label>

          <label className="user-modal-field">
            <span>{isEditing ? "Nueva contraseña" : "Contraseña temporal"}</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={isEditing ? "Dejar vacío para mantenerla" : "Se genera automáticamente si queda vacío"}
              disabled={loading}
            />
          </label>

          {isEditing && (
            <label
              className={cx(
                "toggle-label user-status-toggle",
                isDisabled && "active",
                disableStatusToggle && "disabled"
              )}
            >
              <div className="toggle-text-group">
                <span className="toggle-title">
                  {isDisabled ? "Usuario deshabilitado" : "Usuario habilitado"}
                </span>
                <span className="toggle-subtitle">
                  {editingUser?.is_disabled && !isSuperAdmin
                    ? "Solo un Super Admin puede volver a habilitarlo"
                    : "Controla si puede iniciar sesión en la plataforma"}
                </span>
              </div>
              <input
                type="checkbox"
                className="hidden-input"
                checked={isDisabled}
                disabled={disableStatusToggle || loading}
                onChange={(event) => setIsDisabled(event.target.checked)}
              />
              <div className="toggle-switch" />
            </label>
          )}

          {isEditing && (
            <div className="user-security-note">
              Intentos fallidos: <strong>{editingUser.failed_login_attempts || 0}</strong>
            </div>
          )}

          <div className="user-modal-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={onClose}
              disabled={loading}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="primary-button"
              disabled={loading || !name.trim() || !email.trim() || !roleId}
            >
              {isEditing ? "Guardar cambios" : "Crear usuario"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
