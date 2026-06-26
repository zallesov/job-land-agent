"use client";
import { useState } from "react";

interface JobIdChipProps {
  id: string;
  size?: "sm" | "md";
}

export function JobIdChip({ id, size = "sm" }: JobIdChipProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const fontSize = size === "md" ? 13 : 11;

  return (
    <span className="inline-flex items-center gap-1 shrink-0">
      <span className="font-data font-bold" style={{ color: "var(--text-2)", fontSize }}>
        #{id}
      </span>
      <button
        type="button"
        onClick={handleCopy}
        title="Copy ID"
        className="inline-flex items-center justify-center rounded opacity-40 hover:opacity-100 transition-opacity"
        style={{ color: copied ? "var(--green, #4ade80)" : "var(--text-3)", padding: "1px 2px" }}
      >
        {copied ? (
          <svg width={fontSize} height={fontSize} viewBox="0 0 16 16" fill="currentColor">
            <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/>
          </svg>
        ) : (
          <svg width={fontSize} height={fontSize} viewBox="0 0 16 16" fill="currentColor">
            <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
            <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
          </svg>
        )}
      </button>
    </span>
  );
}
