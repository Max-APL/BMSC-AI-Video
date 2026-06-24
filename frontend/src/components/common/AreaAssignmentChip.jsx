import React from "react";
import { FolderOpen } from "lucide-react";
import { cx } from "@/utils/cx";

export function AreaAssignmentChip({ label, unassigned = false }) {
  return (
    <span className={cx("area-assignment-chip", unassigned && "unassigned")}>
      <FolderOpen size={13} />
      {label}
    </span>
  );
}
