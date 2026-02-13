"use client";

import { useState } from "react";
import type { Comment, FactcheckResult } from "@/types";
import { fetchApi } from "@/lib/api";
import { TypewriterText } from "@/components/TypewriterText";
import { FactcheckBadge } from "@/components/FactcheckBadge";

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = localStorage.getItem("agonai_session_id");
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem("agonai_session_id", sid);
  }
  return sid;
}

// Consistent color per agent based on agent_id hash
const AGENT_COLORS = [
  { border: "border-blue-500/40", bg: "bg-blue-500/5", text: "text-blue-400", dot: "bg-blue-400" },
  { border: "border-emerald-500/40", bg: "bg-emerald-500/5", text: "text-emerald-400", dot: "bg-emerald-400" },
  { border: "border-violet-500/40", bg: "bg-violet-500/5", text: "text-violet-400", dot: "bg-violet-400" },
  { border: "border-amber-500/40", bg: "bg-amber-500/5", text: "text-amber-400", dot: "bg-amber-400" },
  { border: "border-rose-500/40", bg: "bg-rose-500/5", text: "text-rose-400", dot: "bg-rose-400" },
  { border: "border-cyan-500/40", bg: "bg-cyan-500/5", text: "text-cyan-400", dot: "bg-cyan-400" },
];

function getAgentColor(agentId: string) {
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) {
    hash = ((hash << 5) - hash + agentId.charCodeAt(i)) | 0;
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

export function CommentCard({
  comment,
  topicId,
  reactions,
  onReacted,
  isNew = false,
  factcheckResult,
  allComments,
}: {
  comment: Comment;
  topicId: string;
  reactions: Record<string, number>;
  onReacted: () => void;
  isNew?: boolean;
  factcheckResult: FactcheckResult | null;
  allComments: Comment[];
}) {
  const [citationsCollapsed, setCitationsCollapsed] = useState(true);
  const colors = getAgentColor(comment.agent_id);

  const handleReaction = async (type: string) => {
    try {
      await fetchApi(`/api/topics/${topicId}/comments/${comment.id}/reactions`, {
        method: "POST",
        body: JSON.stringify({ type, session_id: getSessionId() }),
      });
      onReacted();
    } catch {
      // Ignore duplicate reaction errors
    }
  };

  const scrollToComment = (commentId: string) => {
    const el = document.getElementById(`comment-${commentId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-2", "ring-accent/50");
      setTimeout(() => el.classList.remove("ring-2", "ring-accent/50"), 2000);
    }
  };

  return (
    <div id={`comment-${comment.id}`} className={`rounded-xl border ${colors.border} ${colors.bg} p-5 animate-turn-in transition-all`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`inline-block w-2 h-2 rounded-full ${colors.dot}`} />
        <span className={`text-sm font-medium ${colors.text}`}>{comment.agent_name}</span>
        {comment.stance && (
          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-card-border/30 text-muted">
            {comment.stance}
          </span>
        )}
        {comment.token_count != null && (
          <span className="text-xs text-muted font-mono">{comment.token_count} tok</span>
        )}
        <span className="text-xs text-muted ml-auto">
          {new Date(comment.created_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </span>
      </div>

      {/* References (agree/rebut indicators) */}
      {comment.references.length > 0 && (
        <div className="space-y-1 mb-3">
          {comment.references.map((ref, i) => {
            const refComment = allComments.find((c) => c.id === ref.comment_id);
            const isAgree = ref.type === "agree";
            return (
              <button
                key={i}
                onClick={() => scrollToComment(ref.comment_id)}
                className={`flex items-center gap-1.5 text-xs ${isAgree ? "text-emerald-400/80" : "text-rose-400/80"} hover:underline`}
              >
                <span>{isAgree ? "+" : "-"}</span>
                <span>
                  {isAgree ? "Agrees with" : "Rebuts"} {refComment?.agent_name ?? "Unknown"}
                </span>
                {ref.quote && (
                  <span className="text-muted font-normal truncate max-w-[200px]">
                    &mdash; &ldquo;{ref.quote}&rdquo;
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Content */}
      <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
        {isNew ? <TypewriterText text={comment.content} /> : comment.content}
      </p>

      {/* Citations */}
      {comment.citations.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setCitationsCollapsed(!citationsCollapsed)}
            className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors"
          >
            <span className="transition-transform duration-200" style={{ transform: citationsCollapsed ? "rotate(0deg)" : "rotate(90deg)" }}>
              &#x25B8;
            </span>
            <span>{comment.citations.length} {comment.citations.length === 1 ? "citation" : "citations"}</span>
          </button>
          <div
            className="overflow-hidden transition-all duration-300 ease-in-out"
            style={{
              maxHeight: citationsCollapsed ? "0" : `${comment.citations.length * 60}px`,
              opacity: citationsCollapsed ? 0 : 1,
            }}
          >
            <div className="mt-2 space-y-1">
              {comment.citations.map((c, i) => (
                <div key={i} className="text-xs text-muted border-l-2 border-card-border pl-3">
                  <span className="font-medium">{c.title}</span>
                  {c.quote && <span className="italic"> &mdash; &ldquo;{c.quote}&rdquo;</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Reactions + Factcheck */}
      <div className="flex items-center gap-3 mt-4 pt-3 border-t border-card-border/50">
        <button
          onClick={() => handleReaction("like")}
          className="flex items-center gap-1.5 text-xs text-muted hover:text-green-400 transition-colors"
        >
          <span>&#x1F44D;</span>
          <span>{reactions.like ?? 0}</span>
        </button>
        <button
          onClick={() => handleReaction("logic_error")}
          className="flex items-center gap-1.5 text-xs text-muted hover:text-red-400 transition-colors"
        >
          <span>&#x26A0;</span>
          <span>{reactions.logic_error ?? 0}</span>
        </button>
        <div className="ml-auto">
          {factcheckResult && <FactcheckBadge result={factcheckResult} />}
        </div>
      </div>
    </div>
  );
}
