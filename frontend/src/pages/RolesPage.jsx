import React, { useState } from "react";
import { Edit2, Plus, Shield } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { RoleModal } from "@/components/modals/RoleModal";
import "@/components/modals/RoleModal.css";
import { useRoles } from "@/hooks/useRoles";
import { useAreas } from "@/context/AreasContext";
import { availablePermissions } from "@/constants/labels";
import "./RolesPage.css";

export function RolesPage() {
  const { roles, loadRoles } = useRoles();
  const { areas } = useAreas();

  const [modalOpen, setModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState(null);

  function openCreate() {
    setEditingRole(null);
    setModalOpen(true);
  }

  function openEdit(role) {
    setEditingRole(role);
    setModalOpen(true);
  }

  return (
    <>
      <Topbar />
      <section className="organization-page">
        <div className="roles-top-bar">
          <div>
            <h2 className="roles-title">Roles y Permisos</h2>
            <p className="roles-subtitle">
              Gestiona el nivel de acceso y las áreas permitidas para los usuarios
              de la plataforma.
            </p>
          </div>
          <button className="primary-button" onClick={openCreate}>
            <Plus size={18} />
            Añadir Rol
          </button>
        </div>

        <div className="roles-grid">
          {roles.map((r) => {
            const isGlobal = r.allowed_areas?.includes("*");
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
                  <button
                    className="icon-button role-edit-btn"
                    onClick={() => openEdit(r)}
                    title="Editar Rol"
                  >
                    <Edit2 size={14} />
                  </button>
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
              </div>
            );
          })}
        </div>

        <RoleModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          editingRole={editingRole}
          onSaved={loadRoles}
        />
      </section>
    </>
  );
}
