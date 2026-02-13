"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Debate, Turn, AnalysisResult, FactcheckResult } from "@/types";
import { fetchApi } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { TypewriterText } from "@/components/TypewriterText";
import { CooldownTimer } from "@/components/CooldownTimer";
import { FactcheckBadge } from "@/components/FactcheckBadge";
import { useLiveDebate } from "@/hooks/useLiveDebate";

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

function transformSentimentData(sentimentData: AnalysisResult["sentiment_data"]) {
  // Group by turn_number, merging pro and con data
  const turnMap = new Map<number, any>();

  sentimentData.forEach((item) => {
    if (!turnMap.has(item.turn_number)) {
      turnMap.set(item.turn_number, { turn_number: item.turn_number });
    }

    const turn = turnMap.get(item.turn_number)!;
    const prefix = item.side === "pro" ? "pro" : "con";

    // Use aggression/confidence if available, otherwise fallback to null
    turn[`${prefix}_aggression`] = item.aggression ?? null;
    turn[`${prefix}_confidence`] = item.confidence ?? null;
  });

  // Convert to array and sort by turn_number
  return Array.from(turnMap.values()).sort((a, b) => a.turn_number - b.turn_number);
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
  const [factcheckResults, setFactcheckResults] = useState<Record<string, FactcheckResult>>({});
  const [factcheckCooldown, setFactcheckCooldown] = useState<number>(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const seenTurnIdsRef = useRef<Set<string>>(new Set());

  const isLiveMode = debate?.mode === "live";
  const { isLive, viewerCount, cooldownSeconds: serverCooldown, latestTurn } = useLiveDebate(id, isLiveMode && debate?.status === "in_progress");

  // Process live turn events
  useEffect(() => {
    if (latestTurn && isLiveMode) {
      setTurns((prev) => {
        const exists = prev.some((t) => t.id === latestTurn.id);
        if (exists) {
          return prev.map((t) => (t.id === latestTurn.id ? latestTurn : t));
        }
        return [...prev, latestTurn];
      });
    }
  }, [latestTurn, isLiveMode]);

  const loadReactions = useCallback(() => {
    fetchApi<ReactionCounts>(`/api/debates/${id}/reactions`).then(setReactions);
  }, [id]);

  const loadFactchecks = useCallback(async () => {
    try {
      const results = await fetchApi<FactcheckResult[]>(`/api/debates/${id}/factchecks`);
      const map: Record<string, FactcheckResult> = {};
      for (const r of results) {
        map[r.turn_id] = r;
      }
      setFactcheckResults(map);
    } catch {
      // No factchecks yet
    }
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
        loadFactchecks(),
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
  }, [id, loadAnalysis, loadFactchecks]);

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

  // Supabase Realtime subscription for factcheck results
  useEffect(() => {
    const channel = supabase
      .channel(`factcheck-${id}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "factcheck_results",
        },
        (payload) => {
          const result = payload.new as FactcheckResult;
          setFactcheckResults((prev) => ({ ...prev, [result.turn_id]: result }));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [id]);

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

  // Track seen turn IDs for typewriter animation
  useEffect(() => {
    // On initial load, mark all turns as already seen
    if (turns.length > 0 && seenTurnIdsRef.current.size === 0) {
      turns.forEach((turn) => seenTurnIdsRef.current.add(turn.id));
    }
  }, [turns]);

  // Auto-scroll to bottom when new turns arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length]);

  const handleFactcheck = async (turnId: string) => {
    try {
      await fetchApi(`/api/debates/${id}/turns/${turnId}/factcheck`, {
        method: "POST",
        body: JSON.stringify({ session_id: getSessionId() }),
      });
      setFactcheckCooldown(Date.now() + 60000);
    } catch {
      // Rate limited or error
    }
  };

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

  const proParticipants = debate.participants.filter((p) => p.side === "pro");
  const conParticipants = debate.participants.filter((p) => p.side === "con");
  const isTeamDebate = debate.format !== "1v1";
  const agentMap = new Map(debate.participants.map((p) => [p.agent_id, p]));

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/debates"
          className="text-sm text-muted hover:text-foreground mb-3 inline-block"
        >
          &larr; Back to debates
        </Link>
        <h1 className="text-2xl font-bold">{debate.topic}</h1>
        <div className="flex items-center gap-4 mt-2 text-sm text-muted">
          <StatusBadge status={debate.status} />
          {isLiveMode && isLive && (
            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              LIVE
              {viewerCount > 0 && <span className="text-red-400/70 font-normal">{viewerCount}</span>}
            </span>
          )}
          <span>Turn {debate.current_turn}/{debate.max_turns}</span>
          <span className="uppercase font-mono text-xs">{debate.format}</span>
        </div>
      </div>

      {/* Participants bar */}
      {isTeamDebate ? (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="rounded-lg border border-pro/30 bg-pro/5 p-3">
            <div className="text-pro text-xs font-bold uppercase text-center mb-2">Team A (Pro)</div>
            <div className={`grid ${proParticipants.length >= 3 ? "grid-cols-3" : "grid-cols-2"} gap-2`}>
              {proParticipants.map((p) => (
                <div key={p.agent_id} className="text-center">
                  <p className="font-medium text-sm truncate">{p.agent_name}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-con/30 bg-con/5 p-3">
            <div className="text-con text-xs font-bold uppercase text-center mb-2">Team B (Con)</div>
            <div className={`grid ${conParticipants.length >= 3 ? "grid-cols-3" : "grid-cols-2"} gap-2`}>
              {conParticipants.map((p) => (
                <div key={p.agent_id} className="text-center">
                  <p className="font-medium text-sm truncate">{p.agent_name}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="rounded-lg border border-pro/30 bg-pro/5 p-3 text-center">
            <span className="text-pro text-xs font-bold uppercase">Pro</span>
            <p className="font-medium mt-1">{proParticipants[0]?.agent_name ?? "—"}</p>
          </div>
          <div className="rounded-lg border border-con/30 bg-con/5 p-3 text-center">
            <span className="text-con text-xs font-bold uppercase">Con</span>
            <p className="font-medium mt-1">{conParticipants[0]?.agent_name ?? "—"}</p>
          </div>
        </div>
      )}

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
      <div className="space-y-4 relative">
        {turns.map((turn) => {
          const isNew = !seenTurnIdsRef.current.has(turn.id);
          if (isNew) {
            seenTurnIdsRef.current.add(turn.id);
          }
          const participant = agentMap.get(turn.agent_id);
          const rebuttalTargetTurn = turn.rebuttal_target_id
            ? turns.find((t) => t.id === turn.rebuttal_target_id)
            : null;
          return (
            <div key={turn.id} id={`turn-${turn.id}`}>
              {/* Rebuttal connection indicator */}
              {rebuttalTargetTurn && (
                <div className="flex items-center gap-2 mb-1 ml-6">
                  <svg width="20" height="20" viewBox="0 0 20 20" className="text-accent/60 shrink-0">
                    <path d="M10 0 L10 12 L4 8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="text-xs text-accent/60 font-medium">
                    Replying to Turn {rebuttalTargetTurn.turn_number}
                    <span className="text-muted font-normal"> &mdash; {rebuttalTargetTurn.claim?.slice(0, 50)}{(rebuttalTargetTurn.claim?.length ?? 0) > 50 ? "..." : ""}</span>
                  </span>
                </div>
              )}
              <TurnCard
                turn={turn}
                debateId={id}
                agentName={participant?.agent_name ?? "Unknown"}
                side={participant?.side ?? "pro"}
                teamId={participant?.team_id ?? null}
                isTeamDebate={isTeamDebate}
                reactions={reactions[turn.id] ?? {}}
                onReacted={loadReactions}
                isNew={isNew}
                factcheckResult={factcheckResults[turn.id] ?? null}
                onFactcheck={handleFactcheck}
                factcheckCooldown={factcheckCooldown}
              />
            </div>
          );
        })}

        {/* Pending indicator */}
        {debate.status === "in_progress" && (
          <CooldownTimer
            cooldownSeconds={(debate as any).turn_cooldown_seconds ?? 10}
            nextTurnNumber={debate.current_turn + 1}
            serverCooldownSeconds={isLiveMode ? serverCooldown : undefined}
          />
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
              {/* Sentiment Trend Chart */}
              <div className="rounded-xl border border-card-border bg-card p-6">
                <h3 className="text-sm font-bold uppercase text-muted mb-4">Sentiment Trends</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={transformSentimentData(analysis.sentiment_data)}>
                    <XAxis
                      dataKey="turn_number"
                      stroke="#71717a"
                      tick={{ fill: "#71717a" }}
                      label={{ value: "Turn Number", position: "insideBottom", offset: -5, fill: "#71717a" }}
                    />
                    <YAxis
                      domain={[0, 1]}
                      stroke="#71717a"
                      tick={{ fill: "#71717a" }}
                      label={{ value: "Score", angle: -90, position: "insideLeft", fill: "#71717a" }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        border: "1px solid #27272a",
                        borderRadius: "8px",
                      }}
                      labelStyle={{ color: "#fafafa" }}
                      formatter={(value: number | undefined) => value?.toFixed(2) ?? "N/A"}
                    />
                    <Legend
                      wrapperStyle={{ paddingTop: "20px" }}
                      iconType="line"
                    />
                    <Line
                      type="monotone"
                      dataKey="pro_aggression"
                      stroke="#22c55e"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      name="Pro Aggression"
                    />
                    <Line
                      type="monotone"
                      dataKey="pro_confidence"
                      stroke="#22c55e"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={{ r: 4 }}
                      name="Pro Confidence"
                    />
                    <Line
                      type="monotone"
                      dataKey="con_aggression"
                      stroke="#ef4444"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      name="Con Aggression"
                    />
                    <Line
                      type="monotone"
                      dataKey="con_confidence"
                      stroke="#ef4444"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={{ r: 4 }}
                      name="Con Confidence"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Token Count Summary */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-pro/30 bg-pro/5 p-4">
                  <h3 className="text-xs font-bold uppercase text-pro mb-2">Pro Total Tokens</h3>
                  <div className="text-2xl font-bold text-foreground">
                    {analysis.sentiment_data
                      .filter(d => d.side === "pro")
                      .reduce((sum, d) => sum + (d.token_count || 0), 0)
                      .toLocaleString()}
                  </div>
                </div>
                <div className="rounded-xl border border-con/30 bg-con/5 p-4">
                  <h3 className="text-xs font-bold uppercase text-con mb-2">Con Total Tokens</h3>
                  <div className="text-2xl font-bold text-foreground">
                    {analysis.sentiment_data
                      .filter(d => d.side === "con")
                      .reduce((sum, d) => sum + (d.token_count || 0), 0)
                      .toLocaleString()}
                  </div>
                </div>
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
                    {analysis.citation_stats.pro.source_types && (
                      <div className="pt-2 border-t border-pro/20 space-y-1">
                        {Object.entries(analysis.citation_stats.pro.source_types).map(([type, count]) => (
                          <div key={type} className="flex justify-between text-xs">
                            <span className="text-muted capitalize">{type}</span>
                            <span className="text-foreground font-medium">{count}</span>
                          </div>
                        ))}
                      </div>
                    )}
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
                    {analysis.citation_stats.con.source_types && (
                      <div className="pt-2 border-t border-con/20 space-y-1">
                        {Object.entries(analysis.citation_stats.con.source_types).map(([type, count]) => (
                          <div key={type} className="flex justify-between text-xs">
                            <span className="text-muted capitalize">{type}</span>
                            <span className="text-foreground font-medium">{count}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Full Analysis Link */}
              <div className="text-center pt-2">
                <Link
                  href={`/debates/${id}/analysis`}
                  className="text-sm text-accent hover:text-accent/80 font-medium transition-colors"
                >
                  View Full Analysis &rarr;
                </Link>
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
  teamId,
  isTeamDebate,
  reactions,
  onReacted,
  isNew = false,
  factcheckResult,
  onFactcheck,
  factcheckCooldown,
}: {
  turn: Turn;
  debateId: string;
  agentName: string;
  side: "pro" | "con";
  teamId: string | null;
  isTeamDebate: boolean;
  reactions: Record<string, number>;
  onReacted: () => void;
  isNew?: boolean;
  factcheckResult: FactcheckResult | null;
  onFactcheck: (turnId: string) => void;
  factcheckCooldown: number;
}) {
  const [citationsCollapsed, setCitationsCollapsed] = useState(true);
  const [requesting, setRequesting] = useState(false);
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
          {isTeamDebate && teamId && (
            <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-card-border/30 text-muted">Team {teamId}</span>
          )}
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
        {isTeamDebate && teamId && (
          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-card-border/30 text-muted">Team {teamId}</span>
        )}
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
          <p className="font-semibold text-sm mb-2">
            {isNew ? <TypewriterText text={turn.claim ?? ""} /> : turn.claim}
          </p>
          <p className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap">
            {isNew ? <TypewriterText text={turn.argument ?? ""} /> : turn.argument}
          </p>

          {turn.citations.length > 0 && (
            <div className="mt-3">
              <button
                onClick={() => setCitationsCollapsed(!citationsCollapsed)}
                className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors"
              >
                <span className="transition-transform duration-200" style={{ transform: citationsCollapsed ? 'rotate(0deg)' : 'rotate(90deg)' }}>
                  ▸
                </span>
                <span>{turn.citations.length} {turn.citations.length === 1 ? 'citation' : 'citations'}</span>
              </button>
              <div
                className="overflow-hidden transition-all duration-300 ease-in-out"
                style={{
                  maxHeight: citationsCollapsed ? '0' : `${turn.citations.length * 60}px`,
                  opacity: citationsCollapsed ? 0 : 1,
                }}
              >
                <div className="mt-2 space-y-1">
                  {turn.citations.map((c, i) => (
                    <div key={i} className="text-xs text-muted border-l-2 border-card-border pl-3">
                      <span className="font-medium">{c.title}</span>
                      {c.quote && <span className="italic"> &mdash; &ldquo;{c.quote}&rdquo;</span>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Reaction buttons and factcheck */}
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

            <div className="ml-auto flex items-center gap-2">
              {factcheckResult ? (
                <FactcheckBadge result={factcheckResult} />
              ) : turn.status === "validated" && (
                <button
                  onClick={async () => {
                    setRequesting(true);
                    onFactcheck(turn.id);
                    setTimeout(() => setRequesting(false), 2000);
                  }}
                  disabled={requesting || Date.now() < factcheckCooldown}
                  className="text-xs text-muted hover:text-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {requesting ? "Requesting..." : Date.now() < factcheckCooldown ? "Cooldown..." : "Fact Check"}
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
