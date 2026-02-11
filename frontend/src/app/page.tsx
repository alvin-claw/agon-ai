"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Agent, DebateListItem } from "@/types";
import { fetchApi } from "@/lib/api";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  scheduled: { label: "Scheduled", color: "text-yellow-400" },
  in_progress: { label: "Live", color: "text-green-400" },
  completed: { label: "Completed", color: "text-muted" },
  cancelled: { label: "Cancelled", color: "text-red-400" },
};

export default function HomePage() {
  const [debates, setDebates] = useState<DebateListItem[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchApi<DebateListItem[]>("/api/debates"),
      fetchApi<Agent[]>("/api/agents"),
    ]).then(([d, a]) => {
      setDebates(d);
      setAgents(a);
      setLoading(false);
    });
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Debates</h1>
          <p className="text-muted text-sm mt-1">AI agents debating topics autonomously</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
        >
          + New Debate
        </button>
      </div>

      {showForm && (
        <CreateDebateForm
          agents={agents}
          onClose={() => setShowForm(false)}
          onCreated={(d) => {
            setDebates([d, ...debates]);
            setShowForm(false);
          }}
        />
      )}

      {loading ? (
        <div className="text-center text-muted py-20">Loading debates...</div>
      ) : debates.length === 0 ? (
        <div className="text-center text-muted py-20">
          <p className="text-lg">No debates yet</p>
          <p className="text-sm mt-2">Create one to get started</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {debates.map((debate) => {
            const s = STATUS_LABELS[debate.status] || { label: debate.status, color: "text-muted" };
            return (
              <Link
                key={debate.id}
                href={`/debates/${debate.id}`}
                className="block rounded-xl border border-card-border bg-card p-5 hover:border-accent/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h2 className="font-semibold text-lg truncate">{debate.topic}</h2>
                    <div className="flex items-center gap-3 mt-2 text-sm text-muted">
                      <span className="uppercase text-xs font-mono">{debate.format}</span>
                      <span>Turn {debate.current_turn}/{debate.max_turns}</span>
                      <span>{new Date(debate.created_at).toLocaleDateString("ko-KR")}</span>
                    </div>
                  </div>
                  <span className={`text-sm font-medium ${s.color}`}>
                    {debate.status === "in_progress" && (
                      <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1.5 animate-pulse" />
                    )}
                    {s.label}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CreateDebateForm({
  agents,
  onClose,
  onCreated,
}: {
  agents: Agent[];
  onClose: () => void;
  onCreated: (d: DebateListItem) => void;
}) {
  const [topic, setTopic] = useState("");
  const [agentIds, setAgentIds] = useState<[string, string]>(
    agents.length >= 2 ? [agents[0].id, agents[1].id] : ["", ""]
  );
  const [maxTurns, setMaxTurns] = useState(6);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim() || !agentIds[0] || !agentIds[1]) return;
    setSubmitting(true);
    try {
      const debate = await fetchApi<DebateListItem>("/api/debates", {
        method: "POST",
        body: JSON.stringify({
          topic: topic.trim(),
          format: "1v1",
          max_turns: maxTurns,
          agent_ids: agentIds,
        }),
      });
      onCreated(debate);
    } catch {
      alert("Failed to create debate");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="bg-card border border-card-border rounded-2xl p-6 w-full max-w-lg"
      >
        <h2 className="text-lg font-bold mb-4">New Debate</h2>

        <label className="block mb-4">
          <span className="text-sm text-muted">Topic</span>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. AI 개발에 대한 규제가 필요한가?"
            className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
          />
        </label>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <label className="block">
            <span className="text-sm text-pro">Pro Agent</span>
            <select
              value={agentIds[0]}
              onChange={(e) => setAgentIds([e.target.value, agentIds[1]])}
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-con">Con Agent</span>
            <select
              value={agentIds[1]}
              onChange={(e) => setAgentIds([agentIds[0], e.target.value])}
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="block mb-6">
          <span className="text-sm text-muted">Max Turns</span>
          <input
            type="number"
            min={2}
            max={20}
            step={2}
            value={maxTurns}
            onChange={(e) => setMaxTurns(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
          />
        </label>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-muted hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !topic.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
