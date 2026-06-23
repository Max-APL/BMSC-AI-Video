import React from "react";
import { cx } from "@/utils/cx";
import { stageLabels, manualStatusLabels, statusLabels } from "@/constants/labels";

export function StatusPill({ status, stage }) {
  const label =
    stageLabels[stage] ||
    manualStatusLabels[status] ||
    statusLabels[status] ||
    "Sin estado";
  return (
    <span className={cx("status-pill", status)}>
      <span className="status-dot" />
      {label}
    </span>
  );
}
