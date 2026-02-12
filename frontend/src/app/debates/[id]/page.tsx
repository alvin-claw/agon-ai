"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Debate, Turn, AnalysisResult } from "@/types";
import { fetchApi } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

type ReactionCounts = Record<string, Record<string, number>>;

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = localStorage.getItem("agonai_session_id");
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem("agonai_session_id", sid);
  }
  return sid;
}

export default function DebateArenaPage() {
  const { id } = useParams<{ id: string }>();
  const [debate, setDebate] = useState<Debate | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [reactions, setReactions] = useState<ReactionCounts>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [generatingAnalysis, setGeneratingAnalysis] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadReactions = useCallback(() => {
    fetchApi<ReactionCounts>(`/api/debates/${id}/reactions`).then(setReactions);
  }, [id]);

  const loadAnalysis = useCallback(async () => {
    try {
      const a = await fetchApi<AnalysisResult>(`/api/debates/${id}/analysis`);
      setAnalysis(a);
    } catch {
      // Analysis not found (404), ignore
      setAnalysis(null);
    }
  }, [id]);

  const loadData = useCallback(async () => {
    try {
      const [d, t] = await Promise.all([
        fetchApi<Debate>(`/api/debates/${id}`),
        fetchApi<Turn[]>(`/api/debates/${id}/turns`),
        fetchApi<ReactionCounts>(`/api/debates/${id}/reactions`).then(setReactions),
      ]);
      setDebate(d);
      setTurns(t);

      if (d.status === "completed") {
        loadAnalysis();
      }
    } catch {
      setError("Failed to load debate. Please check if the backend is running.");
    } finally {
      setLoading(false);
    }
  }, [id, loadAnalysis]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Track debate status separately to avoid realtime subscription churn
  const [debateStatus, setDebateStatus] = useState<string | null>(null);

  // Update debateStatus when debate changes
  useEffect(() => {
    if (debate && debate.status !== debateStatus) {
      setDebateStatus(debate.status);
    }
  }, [debate, debateStatus]);

  // Supabase Realtime subscription for new turns
  useEffect(() => {
    if (!debateStatus || debateStatus === "completed") return;

    const channel = supabase
      .channel(`debate-${id}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "turns",
          filter: `debate_id=eq.${id}`,
        },
        () => {
          fetchApi<Turn[]>(`/api/debates/${id}/turns`).then(setTurns).catch(() => {});
          fetchApi<Debate>(`/api/debates/${id}`).then((d) => {
            setDebate(d);
            setDebateStatus(d.status);
          }).catch(() => {});
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [id, debateStatus]);

  // Poll as fallback (every 5s while in_progress)
  useEffect(() => {
    if (debateStatus !== "in_progress") return;
    const interval = setInterval(() => {
      fetchApi<Turn[]>(`/api/debates/${id}/turns`).then(setTurns).catch(() => {});
      fetchApi<Debate>(`/api/debates/${id}`).then((d) => {
        setDebate(d);
        setDebateStatus(d.status);
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [id, debateStatus]);

  // Auto-scroll to bottom when new turns arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length]);

  const handleStart = async () => {
    setStarting(true);
    try {
      const d = await fetchApi<Debate>(`/api/debates/${id}/start`, {
        method: "POST",
      });
      setDebate(d);
    } catch {
      setError("Failed to start debate. Please try again.");
    } finally {
      setStarting(false);
    }
  };

  const handleGenerateAnalysis = async () => {
    setGeneratingAnalysis(true);
    try {
      await fetchApi(`/api/debates/${id}/analysis/generate`, {
        method: "POST",
      });
      await loadAnalysis();
    } catch {
      setError("Failed to generate analysis. Please try again.");
    } finally {
      setGeneratingAnalysis(false);
    }
  };

  if (loading) {
    return <div className="text-center text-muted py-20">Loading debate...</div>;
  }

  if (error && !debate) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!debate) {
    return <div className="text-center text-muted py-20">Debate not found</div>;
  }

  const proParticipant = debate.participants.find((p) => p.side === "pro");
  const conParticipant = debate.participants.find((p) => p.side === "con");

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/"
          className="text-sm text-muted hover:text-foreground mb-3 inline-block"
        >
          &larr; Back to debates
        </Link>
        <h1 className="text-2xl font-bold">{debate.topic}</h1>
        <div className="flex items-center gap-4 mt-2 text-sm text-muted">
          <StatusBadge status={debate.status} />
          <span>Turn {debate.current_turn}/{debate.max_turns}</span>
          <span className="uppercase font-mono text-xs">{debate.format}</span>
        </div>
      </div>

      {/* Participants bar */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="rounded-lg border border-pro/30 bg-pro/5 p-3 text-center">
          <span className="text-pro text-xs font-bold uppercase">Pro</span>
          <p className="font-medium mt-1">{proParticipant?.agent_name ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-con/30 bg-con/5 p-3 text-center">
          <span className="text-con text-xs font-bold uppercase">Con</span>
          <p className="font-medium mt-1">{conParticipant?.agent_name ?? "—"}</p>
        </div>
      </div>

      {/* Start button */}
      {debate.status === "scheduled" && (
        <div className="text-center py-8">
          <button
            onClick={handleStart}
            disabled={starting}
            className="rounded-xl bg-accent px-8 py-3 text-lg font-bold text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {starting ? "Starting..." : "Start Debate"}
          </button>
        </div>
      )}

      {/* Turns timeline */}
      <div className="space-y-4">
        {turns.map((turn) => (
          <TurnCard
            key={turn.id}
            turn={turn}
            debateId={id}
            agentName={
              turn.agent_id === proParticipant?.agent_id
                ? proParticipant.agent_name
                : conParticipant?.agent_name ?? "Unknown"
            }
            side={
              turn.agent_id === proParticipant?.agent_id ? "pro" : "con"
            }
            reactions={reactions[turn.id] ?? {}}
            onReacted={loadReactions}
          />
        ))}

        {/* Pending indicator */}
        {debate.status === "in_progress" && (
          <div className="flex items-center gap-3 py-4 px-5 rounded-xl border border-card-border bg-card animate-pulse-border">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <span className="text-sm text-muted">
              Waiting for Turn {debate.current_turn + 1}...
            </span>
          </div>
        )}

        {debate.status === "completed" && turns.length > 0 && (
          <div className="text-center py-6 text-muted text-sm border-t border-card-border mt-4">
            Debate completed &middot; {turns.filter((t) => t.status === "validated").length} validated turns
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Analysis Section */}
      {debate.status === "completed" && (
        <div className="mt-8 pt-8 border-t border-card-border">
          <h2 className="text-xl font-bold mb-4">Post-Debate Analysis</h2>

          {!analysis ? (
            <div className="text-center py-8">
              <p className="text-muted mb-4">Generate analysis to view metrics and insights</p>
              <button
                onClick={handleGenerateAnalysis}
                disabled={generatingAnalysis}
                className="rounded-xl bg-accent px-6 py-2 font-medium text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
              >
                {generatingAnalysis ? "Generating..." : "Generate Analysis"}
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Token Chart */}
              <div className="rounded-xl border border-card-border bg-card p-6">
                <h3 className="text-sm font-bold uppercase text-muted mb-4">Token Count by Turn</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={analysis.sentiment_data}>
                    <XAxis
                      dataKey="turn_number"
                      stroke="#71717a"
                      tick={{ fill: "#71717a" }}
                    />
                    <YAxis
                      stroke="#71717a"
                      tick={{ fill: "#71717a" }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        border: "1px solid #27272a",
                        borderRadius: "8px",
                      }}
                      labelStyle={{ color: "#fafafa" }}
                    />
                    <Bar dataKey="token_count">
                      {analysis.sentiment_data.map((entry, idx) => (
                        <Cell key={idx} fill={entry.side === "pro" ? "#22c55e" : "#ef4444"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Citation Stats */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-pro/30 bg-pro/5 p-6">
                  <h3 className="text-xs font-bold uppercase text-pro mb-3">Pro Citations</h3>
                  <div className="space-y-2">
                    <div>
                      <div className="text-2xl font-bold text-foreground">{analysis.citation_stats.pro.total}</div>
                      <div className="text-xs text-muted">Total Citations</div>
                    </div>
                    <div>
                      <div className="text-xl font-semibold text-foreground">{analysis.citation_stats.pro.unique_sources}</div>
                      <div className="text-xs text-muted">Unique Sources</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-con/30 bg-con/5 p-6">
                  <h3 className="text-xs font-bold uppercase text-con mb-3">Con Citations</h3>
                  <div className="space-y-2">
                    <div>
                      <div className="text-2xl font-bold text-foreground">{analysis.citation_stats.con.total}</div>
                      <div className="text-xs text-muted">Total Citations</div>
                    </div>
                    <div>
                      <div className="text-xl font-semibold text-foreground">{analysis.citation_stats.con.unique_sources}</div>
                      <div className="text-xs text-muted">Unique Sources</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    scheduled: "bg-yellow-400/10 text-yellow-400",
    in_progress: "bg-green-400/10 text-green-400",
    completed: "bg-zinc-500/10 text-zinc-400",
    cancelled: "bg-red-400/10 text-red-400",
  };
  const labels: Record<string, string> = {
    scheduled: "Scheduled",
    in_progress: "Live",
    completed: "Completed",
    cancelled: "Cancelled",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[status] ?? ""}`}>
      {status === "in_progress" && (
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 mr-1 animate-pulse" />
      )}
      {labels[status] ?? status}
    </span>
  );
}

function TurnCard({
  turn,
  debateId,
  agentName,
  side,
  reactions,
  onReacted,
}: {
  turn: Turn;
  debateId: string;
  agentName: string;
  side: "pro" | "con";
  reactions: Record<string, number>;
  onReacted: () => void;
}) {
  const borderColor = side === "pro" ? "border-pro/40" : "border-con/40";
  const sideColor = side === "pro" ? "text-pro" : "text-con";
  const bgTint = side === "pro" ? "bg-pro/5" : "bg-con/5";

  const handleReaction = async (type: string) => {
    try {
      await fetchApi(`/api/debates/${debateId}/turns/${turn.id}/reactions`, {
        method: "POST",
        body: JSON.stringify({ type, session_id: getSessionId() }),
      });
      onReacted();
    } catch {
      // Ignore duplicate reaction errors
    }
  };

  if (turn.status === "pending") {
    return (
      <div className={`rounded-xl border ${borderColor} ${bgTint} p-5 animate-pulse`}>
        <div className="flex items-center gap-2 mb-2">
          <span className={`text-xs font-bold uppercase ${sideColor}`}>{side}</span>
          <span className="text-sm text-muted">{agentName}</span>
          <span className="text-xs text-muted ml-auto">Turn {turn.turn_number}</span>
        </div>
        <div className="h-4 bg-card-border/30 rounded w-3/4" />
      </div>
    );
  }

  const isError = turn.status === "format_error" || turn.status === "timeout";

  return (
    <div className={`rounded-xl border ${borderColor} ${bgTint} p-5 animate-turn-in`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={`text-xs font-bold uppercase ${sideColor}`}>{side}</span>
        <span className="text-sm text-muted">{agentName}</span>
        {turn.token_count != null && (
          <span className="text-xs text-muted font-mono">{turn.token_count} tok</span>
        )}
        <span className="text-xs text-muted ml-auto">Turn {turn.turn_number}</span>
      </div>

      {isError ? (
        <p className="text-sm text-red-400 italic">{turn.claim}</p>
      ) : (
        <>
          <p className="font-semibold text-sm mb-2">{turn.claim}</p>
          <p className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap">
            {turn.argument}
          </p>

          {turn.citations.length > 0 && (
            <div className="mt-3 space-y-1">
              {turn.citations.map((c, i) => (
                <div key={i} className="text-xs text-muted border-l-2 border-card-border pl-3">
                  <span className="font-medium">{c.title}</span>
                  {c.quote && <span className="italic"> &mdash; &ldquo;{c.quote}&rdquo;</span>}
                </div>
              ))}
            </div>
          )}

          {/* Reaction buttons */}
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
          </div>
        </>
      )}
    </div>
  );
}
