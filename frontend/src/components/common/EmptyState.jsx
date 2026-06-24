import React from "react";

export function EmptyState({ icon: Icon, title, body }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={22} />
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}
