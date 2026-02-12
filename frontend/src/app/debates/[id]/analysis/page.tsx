"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { Debate, AnalysisResult } from "@/types";
import { fetchApi } from "@/lib/api";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

function transformSentimentData(sentimentData: AnalysisResult["sentiment_data"]) {
  const turnMap = new Map<number, Record<string, unknown>>();

  sentimentData.forEach((item) => {
    if (!turnMap.has(item.turn_number)) {
      turnMap.set(item.turn_number, { turn_number: item.turn_number });
    }
    const turn = turnMap.get(item.turn_number)!;
    const prefix = item.side === "pro" ? "pro" : "con";
    turn[`${prefix}_aggression`] = item.aggression ?? null;
    turn[`${prefix}_confidence`] = item.confidence ?? null;
    turn[`${prefix}_tokens`] = item.token_count ?? 0;
  });

  return Array.from(turnMap.values()).sort(
    (a, b) => (a.turn_number as number) - (b.turn_number as number),
  );
}

function buildSourceTypeData(citationStats: AnalysisResult["citation_stats"]) {
  const types = ["academic", "news", "wiki", "government", "other"];
  return types.map((type) => ({
    type: type.charAt(0).toUpperCase() + type.slice(1),
    pro: citationStats.pro.source_types?.[type] ?? 0,
    con: citationStats.con.source_types?.[type] ?? 0,
  }));
}

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [debate, setDebate] = useState<Debate | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatingAnalysis, setGeneratingAnalysis] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const d = await fetchApi<Debate>(`/api/debates/${id}`);
      setDebate(d);
      try {
        const a = await fetchApi<AnalysisResult>(`/api/debates/${id}/analysis`);
        setAnalysis(a);
      } catch {
        setAnalysis(null);
      }
    } catch {
      setError("Failed to load debate data.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleGenerateAnalysis = async () => {
    setGeneratingAnalysis(true);
    try {
      await fetchApi(`/api/debates/${id}/analysis/generate`, { method: "POST" });
      const a = await fetchApi<AnalysisResult>(`/api/debates/${id}/analysis`);
      setAnalysis(a);
    } catch {
      setError("Failed to generate analysis.");
    } finally {
      setGeneratingAnalysis(false);
    }
  };

  if (loading) {
    return <div className="text-center text-muted py-20">Loading analysis...</div>;
  }

  if (error && !debate) {
    return <div className="text-center py-20 text-red-400">{error}</div>;
  }

  if (!debate) {
    return <div className="text-center text-muted py-20">Debate not found</div>;
  }

  const proTokens = analysis?.sentiment_data
    .filter((d) => d.side === "pro")
    .reduce((sum, d) => sum + (d.token_count || 0), 0) ?? 0;
  const conTokens = analysis?.sentiment_data
    .filter((d) => d.side === "con")
    .reduce((sum, d) => sum + (d.token_count || 0), 0) ?? 0;

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link
          href={`/debates/${id}`}
          className="text-sm text-muted hover:text-foreground mb-3 inline-block"
        >
          &larr; Back to arena
        </Link>
        <h1 className="text-2xl font-bold">{debate.topic}</h1>
        <p className="text-sm text-muted mt-1">Full Analysis Report</p>
      </div>

      {!analysis ? (
        <div className="text-center py-16">
          <p className="text-muted mb-4">
            {debate.status === "completed"
              ? "Generate analysis to view detailed metrics and insights."
              : "Analysis is available after the debate completes."}
          </p>
          {debate.status === "completed" && (
            <button
              onClick={handleGenerateAnalysis}
              disabled={generatingAnalysis}
              className="rounded-xl bg-accent px-6 py-2 font-medium text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
            >
              {generatingAnalysis ? "Generating..." : "Generate Analysis"}
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-8">
          {/* Sentiment Trend Chart */}
          <div className="rounded-xl border border-card-border bg-card p-6">
            <h2 className="text-sm font-bold uppercase text-muted mb-6">Sentiment Trends</h2>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={transformSentimentData(analysis.sentiment_data)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
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
                <Legend wrapperStyle={{ paddingTop: "20px" }} iconType="line" />
                <Line type="monotone" dataKey="pro_aggression" stroke="#22c55e" strokeWidth={2} dot={{ r: 4 }} name="Pro Aggression" />
                <Line type="monotone" dataKey="pro_confidence" stroke="#22c55e" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 4 }} name="Pro Confidence" />
                <Line type="monotone" dataKey="con_aggression" stroke="#ef4444" strokeWidth={2} dot={{ r: 4 }} name="Con Aggression" />
                <Line type="monotone" dataKey="con_confidence" stroke="#ef4444" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 4 }} name="Con Confidence" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Source Type Breakdown */}
          <div className="rounded-xl border border-card-border bg-card p-6">
            <h2 className="text-sm font-bold uppercase text-muted mb-6">Source Type Breakdown</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={buildSourceTypeData(analysis.citation_stats)} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="type" stroke="#71717a" tick={{ fill: "#71717a" }} />
                <YAxis stroke="#71717a" tick={{ fill: "#71717a" }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #27272a",
                    borderRadius: "8px",
                  }}
                  labelStyle={{ color: "#fafafa" }}
                />
                <Legend wrapperStyle={{ paddingTop: "20px" }} />
                <Bar dataKey="pro" fill="#22c55e" name="Pro" radius={[4, 4, 0, 0]} />
                <Bar dataKey="con" fill="#ef4444" name="Con" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Token Usage Comparison */}
          <div className="rounded-xl border border-card-border bg-card p-6">
            <h2 className="text-sm font-bold uppercase text-muted mb-4">Token Usage</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-xl border border-pro/30 bg-pro/5 p-4">
                <h3 className="text-xs font-bold uppercase text-pro mb-2">Pro Total Tokens</h3>
                <div className="text-3xl font-bold text-foreground">{proTokens.toLocaleString()}</div>
              </div>
              <div className="rounded-xl border border-con/30 bg-con/5 p-4">
                <h3 className="text-xs font-bold uppercase text-con mb-2">Con Total Tokens</h3>
                <div className="text-3xl font-bold text-foreground">{conTokens.toLocaleString()}</div>
              </div>
            </div>
            {/* Per-turn token chart */}
            <div className="mt-6">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={transformSentimentData(analysis.sentiment_data)} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="turn_number" stroke="#71717a" tick={{ fill: "#71717a" }} />
                  <YAxis stroke="#71717a" tick={{ fill: "#71717a" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #27272a",
                      borderRadius: "8px",
                    }}
                    labelStyle={{ color: "#fafafa" }}
                  />
                  <Legend />
                  <Bar dataKey="pro_tokens" fill="#22c55e" name="Pro Tokens" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="con_tokens" fill="#ef4444" name="Con Tokens" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Citation Stats */}
          <div className="rounded-xl border border-card-border bg-card p-6">
            <h2 className="text-sm font-bold uppercase text-muted mb-4">Citation Statistics</h2>
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
          </div>
        </div>
      )}
    </div>
  );
}
