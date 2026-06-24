import React from "react";
import { AlertCircle } from "lucide-react";

export function ErrorAlert({ message }) {
  if (!message) return null;
  return (
    <div className="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
    </div>
  );
}
