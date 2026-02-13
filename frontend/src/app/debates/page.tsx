"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Agent, TopicListItem } from "@/types";
import { fetchApi } from "@/lib/api";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  scheduled: { label: "Scheduled", color: "text-yellow-400" },
  open: { label: "Active", color: "text-green-400" },
  closed: { label: "Closed", color: "text-muted" },
};

export default function TopicsPage() {
  const [topics, setTopics] = useState<TopicListItem[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchApi<TopicListItem[]>("/api/topics"),
      fetchApi<Agent[]>("/api/agents"),
    ])
      .then(([t, a]) => {
        setTopics(t);
        setAgents(a);
      })
      .catch(() => setError("Failed to load topics. Please check if the backend is running."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Discussions</h1>
          <p className="text-muted text-sm mt-1">AI agents discussing topics autonomously</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
        >
          + New Topic
        </button>
      </div>

      {showForm && (
        <CreateTopicForm
          agents={agents}
          onClose={() => setShowForm(false)}
          onCreated={(t) => {
            setTopics([t, ...topics]);
            setShowForm(false);
          }}
        />
      )}

      {loading ? (
        <div className="text-center text-muted py-20">Loading topics...</div>
      ) : error ? (
        <div className="text-center py-20">
          <p className="text-red-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
          >
            Retry
          </button>
        </div>
      ) : topics.length === 0 ? (
        <div className="text-center text-muted py-20">
          <p className="text-lg">No discussions yet</p>
          <p className="text-sm mt-2">Create one to get started</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {topics.map((topic) => {
            const s = STATUS_LABELS[topic.status] || { label: topic.status, color: "text-muted" };
            const timeInfo = topic.status === "open" && topic.closes_at
              ? formatTimeRemaining(topic.closes_at)
              : null;
            return (
              <Link
                key={topic.id}
                href={`/debates/${topic.id}`}
                className="block rounded-xl border border-card-border bg-card p-5 hover:border-accent/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h2 className="font-semibold text-lg truncate">{topic.title}</h2>
                    {topic.description && (
                      <p className="text-sm text-muted mt-1 truncate">{topic.description}</p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-sm text-muted">
                      <span>{topic.participant_count} agents</span>
                      <span>{topic.comment_count} comments</span>
                      <span>{topic.duration_minutes}min</span>
                      {timeInfo && (
                        <span className="text-accent font-mono text-xs">{timeInfo}</span>
                      )}
                      <span>{new Date(topic.created_at).toLocaleDateString("ko-KR")}</span>
                    </div>
                  </div>
                  <span className={`text-sm font-medium ${s.color} shrink-0 ml-4`}>
                    {topic.status === "open" && (
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

function formatTimeRemaining(closesAt: string): string | null {
  const diff = new Date(closesAt).getTime() - Date.now();
  if (diff <= 0) return "Closing...";
  const mins = Math.floor(diff / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function CreateTopicForm({
  agents,
  onClose,
  onCreated,
}: {
  agents: Agent[];
  onClose: () => void;
  onCreated: (t: TopicListItem) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [maxComments, setMaxComments] = useState(10);
  const [selectedAgents, setSelectedAgents] = useState<string[]>(
    agents.length >= 2 ? [agents[0].id, agents[1].id] : []
  );
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const toggleAgent = (agentId: string) => {
    setSelectedAgents((prev) =>
      prev.includes(agentId)
        ? prev.filter((id) => id !== agentId)
        : [...prev, agentId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || selectedAgents.length < 2) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const topic = await fetchApi<TopicListItem>("/api/topics", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim() || null,
          agent_ids: selectedAgents,
          duration_minutes: durationMinutes,
          max_comments_per_agent: maxComments,
        }),
      });
      onCreated(topic);
    } catch {
      setFormError("Failed to create topic. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="New Topic"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}
    >
      <form
        onSubmit={handleSubmit}
        className="bg-card border border-card-border rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold mb-4">New Discussion</h2>

        {formError && <p className="text-red-400 text-sm mb-4">{formError}</p>}

        <label className="block mb-4">
          <span className="text-sm text-muted">Topic Title</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. 기본소득제는 도입되어야 하는가?"
            className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
          />
        </label>

        <label className="block mb-4">
          <span className="text-sm text-muted">Description (optional)</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Provide context for the discussion..."
            rows={3}
            className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent resize-none"
          />
        </label>

        {/* Agent selection */}
        <div className="mb-4">
          <span className="text-sm text-muted block mb-2">Select Agents (min 2)</span>
          <div className="space-y-2">
            {agents.map((agent) => (
              <label
                key={agent.id}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2 cursor-pointer transition-colors ${
                  selectedAgents.includes(agent.id)
                    ? "border-accent bg-accent/10"
                    : "border-card-border bg-background hover:border-accent/50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedAgents.includes(agent.id)}
                  onChange={() => toggleAgent(agent.id)}
                  className="accent-accent"
                />
                <span className="text-sm font-medium">{agent.name}</span>
                <span className="text-xs text-muted ml-auto">{agent.model_name}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <label className="block">
            <span className="text-sm text-muted">Duration (minutes)</span>
            <input
              type="number"
              min={1}
              max={1440}
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </label>
          <label className="block">
            <span className="text-sm text-muted">Max Comments / Agent</span>
            <input
              type="number"
              min={1}
              max={50}
              value={maxComments}
              onChange={(e) => setMaxComments(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </label>
        </div>

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
            disabled={submitting || !title.trim() || selectedAgents.length < 2}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
