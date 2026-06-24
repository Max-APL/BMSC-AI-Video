import React, { useState, useEffect } from "react";
import { X } from "lucide-react";
import { cx } from "@/utils/cx";
import { availablePermissions } from "@/constants/labels";
import { useAreas } from "@/context/AreasContext";
import { createRole, updateRole } from "@/services/roles";

export function RoleModal({ isOpen, onClose, editingRole, onSaved }) {
  const { areas } = useAreas();
  const [name, setName] = useState("");
  const [perms, setPerms] = useState([]);
  const [roleAreas, setRoleAreas] = useState(["*"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen) {
      setName(editingRole?.name ?? "");
      setPerms(editingRole?.permissions ?? []);
      setRoleAreas(editingRole?.allowed_areas ?? ["*"]);
      setError("");
    }
  }, [isOpen, editingRole]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError("");
    try {
      const payload = {
        name: name.trim(),
        permissions: perms,
        allowed_areas: roleAreas,
      };
      if (editingRole) {
        await updateRole(editingRole.id, payload);
      } else {
        await createRole(payload);
      }
      onSaved?.();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const togglePerm = (id) =>
    setPerms((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );

  const toggleArea = (id) => {
    if (id === "*") {
      setRoleAreas((prev) => (prev.includes("*") ? [] : ["*"]));
      return;
    }
    setRoleAreas((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const isGlobal = roleAreas.includes("*");

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content role-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editingRole ? "Editar Rol" : "Crear Nuevo Rol"}</h2>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {error && <p className="modal-error">{error}</p>}

        <form onSubmit={handleSubmit} className="role-modal-form">
          <label className="role-field">
            <span className="role-field-label">Nombre del Rol</span>
            <input
              placeholder="Ej. Administrador de RRHH..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={loading}
              required
              className="role-name-input"
            />
          </label>

          <div>
            <span className="role-section-label">Permisos del Sistema</span>
            <div className="toggle-grid">
              {availablePermissions.map((p) => (
                <label key={p.id} className={cx("toggle-label", perms.includes(p.id) && "active")}>
                  <div className="toggle-text-group">
                    <span className="toggle-title">{p.label}</span>
                  </div>
                  <input
                    type="checkbox"
                    className="hidden-input"
                    checked={perms.includes(p.id)}
                    onChange={() => togglePerm(p.id)}
                  />
                  <div className="toggle-switch" />
                </label>
              ))}
            </div>
          </div>

          <div>
            <span className="role-section-label">Acceso a Áreas Específicas</span>
            <div className="toggle-grid">
              <label className={cx("toggle-label", isGlobal && "active")}>
                <div className="toggle-text-group">
                  <span className="toggle-title">Todas las Áreas</span>
                  <span className="toggle-subtitle">Acceso Global</span>
                </div>
                <input
                  type="checkbox"
                  className="hidden-input"
                  checked={isGlobal}
                  onChange={() => toggleArea("*")}
                />
                <div className="toggle-switch" />
              </label>

              {areas.map((area) => {
                const isChecked = isGlobal || roleAreas.includes(area.id);
                return (
                  <label
                    key={area.id}
                    className={cx(
                      "toggle-label",
                      isChecked && "active",
                      isGlobal && "disabled"
                    )}
                  >
                    <div className="toggle-text-group">
                      <span className="toggle-title">{area.name}</span>
                      <span className="toggle-subtitle">Área Específica</span>
                    </div>
                    <input
                      type="checkbox"
                      className="hidden-input"
                      checked={isChecked}
                      disabled={isGlobal}
                      onChange={() => toggleArea(area.id)}
                    />
                    <div className="toggle-switch" />
                  </label>
                );
              })}
            </div>
          </div>

          <div className="role-modal-actions">
            <button type="button" className="secondary-button" onClick={onClose}>
              Cancelar
            </button>
            <button
              type="submit"
              className="primary-button"
              disabled={loading || !name.trim()}
            >
              {editingRole ? "Actualizar Rol" : "Guardar Rol"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
