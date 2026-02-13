"use client";

import { useState } from "react";
import type { FactcheckResult } from "@/types";

const VERDICT_CONFIG: Record<
  FactcheckResult["verdict"],
  { label: string; color: string; bg: string; icon: string }
> = {
  verified: {
    label: "Citation Verified",
    color: "text-green-400",
    bg: "bg-green-400/10 border-green-400/30",
    icon: "\u2713",
  },
  source_mismatch: {
    label: "Source Mismatch",
    color: "text-orange-400",
    bg: "bg-orange-400/10 border-orange-400/30",
    icon: "\u26A0",
  },
  source_inaccessible: {
    label: "Source Inaccessible",
    color: "text-zinc-400",
    bg: "bg-zinc-400/10 border-zinc-400/30",
    icon: "\u2715",
  },
  inconclusive: {
    label: "Inconclusive",
    color: "text-zinc-400",
    bg: "bg-zinc-400/10 border-zinc-400/30",
    icon: "?",
  },
};

export function FactcheckBadge({ result }: { result: FactcheckResult }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const config = VERDICT_CONFIG[result.verdict];

  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border ${config.bg} ${config.color} cursor-default`}
      >
        <span>{config.icon}</span>
        <span>{config.label}</span>
      </button>

      {showTooltip && result.details && (
        <div className="absolute bottom-full left-0 mb-2 w-72 rounded-lg border border-card-border bg-card p-3 shadow-lg z-50 text-xs">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-muted">Accessible</span>
              <span className={result.citation_accessible ? "text-green-400" : "text-red-400"}>
                {result.citation_accessible ? "Yes" : "No"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Content Match</span>
              <span className={result.content_match ? "text-green-400" : "text-red-400"}>
                {result.content_match == null ? "N/A" : result.content_match ? "Yes" : "No"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Logic Valid</span>
              <span className={result.logic_valid ? "text-green-400" : "text-red-400"}>
                {result.logic_valid == null ? "N/A" : result.logic_valid ? "Yes" : "No"}
              </span>
            </div>
            {result.details.logic_explanation && (
              <div className="pt-1 border-t border-card-border">
                <p className="text-muted leading-relaxed">{result.details.logic_explanation}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
