import React, { useState } from "react";
import { Edit2, Plus, Shield, Trash2 } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { RoleModal } from "@/components/modals/RoleModal";
import "@/components/modals/RoleModal.css";
import { useAuth } from "@/context/AuthContext";
import { useRoles } from "@/hooks/useRoles";
import { useUsers } from "@/hooks/useUsers";
import { useAreas } from "@/context/AreasContext";
import { availablePermissions } from "@/constants/labels";
import { deleteRole } from "@/services/roles";
import "./RolesPage.css";

export function RolesPage() {
  const { hasPermission } = useAuth();
  const { roles, loadRoles } = useRoles();
  const { usersList } = useUsers();
  const { areas } = useAreas();
  const canManageRoles = hasPermission("manage_roles");

  const [modalOpen, setModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [deleteDialog, setDeleteDialog] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  function openCreate() {
    setEditingRole(null);
    setModalOpen(true);
  }

  function openEdit(role) {
    if (role.name === "Super Admin") return;
    setEditingRole(role);
    setModalOpen(true);
  }

  function openDelete(role) {
    const assignedUsers = role.assigned_users || [];
    const isBlocked =
      role.name === "Super Admin" || assignedUsers.length > 0 || (role.user_count || 0) > 0;
    setDeleteDialog({ role, isBlocked, error: "" });
  }

  function roleAssignedUsers(role) {
    const usersFromAccounts = usersList.filter(
      (user) =>
        user.role_id === role.id ||
        user.role?.id === role.id ||
        user.role?.name === role.name
    );
    if (usersFromAccounts.length > 0) return usersFromAccounts;
    return role.assigned_users || [];
  }

  function deleteRoleBlockedBody(dialog) {
    if (!dialog?.role) return "";

    if (dialog.role.name === "Super Admin") {
      return "El rol Super Admin es un rol base del sistema y no puede eliminarse.";
    }

    const assignedUsers = roleAssignedUsers(dialog.role);
    if (assignedUsers.length === 0) {
      return (
        <div>
          <p>
            {dialog.error ||
              `El rol ${dialog.role.name} no puede eliminarse porque está asignado a usuarios.`}
          </p>
          <p>Reasigna esos usuarios a otro rol antes de eliminarlo.</p>
        </div>
      );
    }

    return (
      <div>
        {dialog.error && <p>{dialog.error}</p>}
        <p>
          El rol {dialog.role.name} no puede eliminarse porque está asignado a los siguientes usuarios:
        </p>
        <ul>
          {assignedUsers.map((user) => (
            <li key={user.id}>
              {user.name || user.email} ({user.email})
            </li>
          ))}
        </ul>
        <p>Reasigna esos usuarios a otro rol antes de eliminarlo.</p>
      </div>
    );
  }

  function roleUserCount(role) {
    const assignedUsers = roleAssignedUsers(role);
    return assignedUsers.length || role.user_count || 0;
  }

  async function handleDeleteRole() {
    if (!deleteDialog?.role) return;
    setActionLoading(true);
    try {
      await deleteRole(deleteDialog.role.id);
      setDeleteDialog(null);
      await loadRoles();
    } catch (err) {
      setDeleteDialog((current) => ({
        ...current,
        isBlocked: true,
        error: err.message,
      }));
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <>
      <Topbar />
      <section className="organization-page">
        <div className="roles-top-bar">
          {canManageRoles && (
            <button className="primary-button" onClick={openCreate}>
              <Plus size={18} />
              Añadir Rol
            </button>
          )}
        </div>

        <div className="roles-grid">
          {roles.map((r) => {
            const isGlobal = r.allowed_areas?.includes("*");
            const isSystemRole = r.name === "Super Admin";
            const userCount = roleUserCount(r);
            return (
              <div className="role-card-premium" key={r.id}>
                <div className="role-card-header">
                  <div className="role-card-name">
                    <Shield size={20} color="var(--green-800)" />
                    <h3>{r.name}</h3>
                  </div>
                  <span
                    className={
                      isGlobal ? "role-access-badge global" : "role-access-badge area"
                    }
                  >
                    {isGlobal ? "Acceso Global" : "Por Áreas"}
                  </span>
                  {isSystemRole && (
                    <span className="role-access-badge system">Rol del sistema</span>
                  )}
                  {canManageRoles && !isSystemRole && (
                    <div className="role-card-actions">
                      <button
                        className="icon-button role-edit-btn"
                        onClick={() => openEdit(r)}
                        title="Editar Rol"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        className="icon-button role-delete-btn"
                        onClick={() => openDelete(r)}
                        title="Eliminar Rol"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </div>

                <div>
                  <span className="role-section-micro-label">Permisos Asignados</span>
                  <div className="role-chips">
                    {r.permissions.map((pId) => {
                      const pDef = availablePermissions.find((x) => x.id === pId);
                      return (
                        <span className="role-chip" key={pId}>
                          {pDef ? pDef.label : pId}
                        </span>
                      );
                    })}
                    {r.permissions.length === 0 && (
                      <span className="role-no-perms">Sin permisos</span>
                    )}
                  </div>
                </div>

                {!isGlobal && r.allowed_areas?.length > 0 && (
                  <div className="role-areas-section">
                    <span className="role-section-micro-label">Áreas Autorizadas</span>
                    <div className="role-chips">
                      {r.allowed_areas.map((aId) => {
                        const aDef = areas.find((x) => x.id === aId);
                        return (
                          <span className="role-chip role-chip-area" key={aId}>
                            {aDef ? aDef.name : "Desconocida"}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="role-users-footnote">
                  {userCount} usuario{userCount === 1 ? "" : "s"} asignado{userCount === 1 ? "" : "s"}
                </div>
              </div>
            );
          })}
        </div>

        {canManageRoles && (
          <RoleModal
            isOpen={modalOpen}
            onClose={() => setModalOpen(false)}
            editingRole={editingRole}
            onSaved={loadRoles}
          />
        )}

        <ConfirmDialog
          isOpen={Boolean(deleteDialog)}
          variant={deleteDialog?.isBlocked ? "info" : "danger"}
          title={
            deleteDialog?.isBlocked
              ? "No se puede eliminar el rol"
              : "Eliminar rol"
          }
          body={
            deleteDialog?.isBlocked
              ? deleteRoleBlockedBody(deleteDialog)
              : `Se eliminará definitivamente el rol ${deleteDialog?.role?.name}. Esta acción solo es posible porque no tiene usuarios asignados.`
          }
          confirmLabel="Eliminar rol"
          cancelLabel={deleteDialog?.isBlocked ? "Cerrar" : "Cancelar"}
          loading={actionLoading}
          onClose={() => {
            if (!actionLoading) setDeleteDialog(null);
          }}
          onConfirm={handleDeleteRole}
        />
      </section>
    </>
  );
}
