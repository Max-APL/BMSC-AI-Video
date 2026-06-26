import React, { useState } from "react";
import { Edit2, Plus, Trash2, UserCheck, UserX, Users } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { UserModal } from "@/components/modals/UserModal";
import { useVideos } from "@/context/VideosContext";
import { useAuth } from "@/context/AuthContext";
import { useUsers } from "@/hooks/useUsers";
import { useRoles } from "@/hooks/useRoles";
import { createUser, deleteUser, updateUser } from "@/services/users";
import "./UsersPage.css";

export function UsersPage() {
  const { setError } = useVideos();
  const { currentUser, hasPermission } = useAuth();
  const { usersList, loadUsersList } = useUsers();
  const { roles } = useRoles();
  const canManageUsers = hasPermission("manage_users");

  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState("");

  function openCreate() {
    setEditingUser(null);
    setModalError("");
    setModalOpen(true);
  }

  function openEdit(user) {
    setEditingUser(user);
    setModalError("");
    setModalOpen(true);
  }

  async function handleSaveUser(payload) {
    setActionLoading(true);
    setModalError("");
    try {
      if (editingUser) {
        await updateUser(editingUser.id, payload);
      } else {
        await createUser(payload);
      }
      setModalOpen(false);
      setEditingUser(null);
      await loadUsersList();
    } catch (err) {
      setModalError(err.message);
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteUser() {
    if (!deleteTarget) return;
    setActionLoading(true);
    try {
      await deleteUser(deleteTarget.id);
      setDeleteTarget(null);
      await loadUsersList();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
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
          {canManageUsers && (
            <button type="button" className="primary-button" onClick={openCreate}>
              <Plus size={18} />
              Nuevo usuario
            </button>
          )}
        </div>

        <div className="org-grid">
          {!canManageUsers && (
            <div className="area-card user-readonly-card">
              <h3>Modo consulta</h3>
              <p>
                Tu rol permite revisar usuarios, pero no crear ni modificar accesos.
              </p>
            </div>
          )}

          {usersList.map((u) => (
            <div className="area-card user-management-card" key={u.id}>
              <div className="user-card-header">
                <div className={u.is_disabled ? "user-avatar-card disabled" : "user-avatar-card"}>
                  {u.is_disabled ? <UserX size={18} /> : <UserCheck size={18} />}
                </div>
                <div>
                  <h3 className="user-card-name">{u.name || u.email}</h3>
                  <p className="user-card-email">{u.email}</p>
                </div>
              </div>

              <div className="user-card-badges">
                <span className="user-role-badge">
                  Rol: {u.role?.name || "Sin Rol"}
                </span>
                <span className={u.is_disabled ? "user-status-badge disabled" : "user-status-badge enabled"}>
                  {u.is_disabled ? "Deshabilitado" : "Habilitado"}
                </span>
              </div>

              {(u.role?.name !== "Super Admin" || u.disabled_reason) && (
                <div className="user-card-meta">
                  {u.role?.name !== "Super Admin" && (
                    <span>Intentos fallidos: {u.failed_login_attempts || 0}</span>
                  )}
                  {u.disabled_reason && <span>{u.disabled_reason}</span>}
                </div>
              )}

              {canManageUsers && (
                <div className="user-card-actions">
                  <button
                    type="button"
                    className="secondary-button compact"
                    onClick={() => openEdit(u)}
                  >
                    <Edit2 size={14} />
                    Editar
                  </button>
                  <button
                    type="button"
                    className="danger-button compact"
                    onClick={() => setDeleteTarget(u)}
                    disabled={u.id === currentUser?.id}
                    title={u.id === currentUser?.id ? "No puedes eliminar tu propio usuario" : "Eliminar usuario"}
                  >
                    <Trash2 size={14} />
                    Eliminar
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <UserModal
          isOpen={modalOpen}
          editingUser={editingUser}
          roles={roles}
          currentUser={currentUser}
          loading={actionLoading}
          error={modalError}
          onClose={() => {
            if (!actionLoading) setModalOpen(false);
          }}
          onSave={handleSaveUser}
        />

        <ConfirmDialog
          isOpen={Boolean(deleteTarget)}
          title="Eliminar usuario"
          body={
            deleteTarget
              ? `Se eliminará definitivamente el usuario ${deleteTarget.email}. Esta acción libera el correo para una futura creación.`
              : ""
          }
          confirmLabel="Eliminar usuario"
          loading={actionLoading}
          onClose={() => {
            if (!actionLoading) setDeleteTarget(null);
          }}
          onConfirm={handleDeleteUser}
        />
      </section>
    </>
  );
}
