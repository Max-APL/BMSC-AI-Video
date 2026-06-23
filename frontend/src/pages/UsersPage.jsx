import React, { useState } from "react";
import { Users } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { useVideos } from "@/context/VideosContext";
import { useUsers } from "@/hooks/useUsers";
import { useRoles } from "@/hooks/useRoles";
import { createUser } from "@/services/users";
import "./UsersPage.css";

export function UsersPage() {
  const { loading, setLoading, setError } = useVideos();
  const { usersList, loadUsersList } = useUsers();
  const { roles } = useRoles();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleId, setRoleId] = useState("");

  async function handleCreateUser(e) {
    e.preventDefault();
    if (!email.trim() || !password || !roleId) return;
    setLoading(true);
    try {
      await createUser({
        email: email.trim(),
        password,
        role_id: roleId,
      });
      setEmail("");
      setPassword("");
      setRoleId("");
      await loadUsersList();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Topbar />
      <section className="organization-page">
        <div className="upload-hero">
          <div>
            <span className="eyebrow">Administración</span>
            <h2>Gestión de Usuarios</h2>
            <p>
              Administra los accesos de los colaboradores al centro de
              capacitación inteligente.
            </p>
          </div>
        </div>

        <div className="org-grid">
          {/* Create user form */}
          <div className="area-card user-create-card">
            <h3>Crear Nuevo Usuario</h3>
            <form
              className="add-form user-form"
              onSubmit={handleCreateUser}
            >
              <input
                type="email"
                placeholder="Correo corporativo (@bmsc.com.bo)"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                required
              />
              <input
                type="password"
                placeholder="Contraseña temporal"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required
              />
              <select
                value={roleId}
                onChange={(e) => setRoleId(e.target.value)}
                disabled={loading}
                className="user-role-select"
                required
              >
                <option value="">Seleccionar rol...</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <button
                className="primary-button compact"
                type="submit"
                disabled={loading || !email.trim() || !password || !roleId}
              >
                Crear Usuario
              </button>
            </form>
          </div>

          {/* User cards */}
          {usersList.map((u) => (
            <div className="area-card" key={u.id}>
              <div className="user-card-header">
                <Users size={20} color="var(--green-800)" />
                <h3 className="user-card-email">{u.email}</h3>
              </div>
              <div className="user-card-role">
                <span className="user-role-badge">
                  Rol: {u.role?.name || "Sin Rol"}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
