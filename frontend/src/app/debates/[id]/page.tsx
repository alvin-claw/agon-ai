"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Topic, FactcheckResult } from "@/types";
import { fetchApi } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { CommentCard } from "@/components/CommentCard";
import { useTopicComments } from "@/hooks/useTopicComments";

type ReactionCounts = Record<string, Record<string, number>>;

export default function TopicDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [reactions, setReactions] = useState<ReactionCounts>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [factcheckResults, setFactcheckResults] = useState<Record<string, FactcheckResult>>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  const isActive = topic?.status === "open";
  const { comments, isNewComment } = useTopicComments(id, isActive);

  const loadReactions = useCallback(() => {
    fetchApi<ReactionCounts>(`/api/topics/${id}/reactions`).then(setReactions).catch(() => {});
  }, [id]);

  const loadFactchecks = useCallback(async () => {
    try {
      const results = await fetchApi<FactcheckResult[]>(`/api/topics/${id}/factchecks`);
      const map: Record<string, FactcheckResult> = {};
      for (const r of results) {
        if (r.comment_id) map[r.comment_id] = r;
      }
      setFactcheckResults(map);
    } catch {
      // no factchecks yet
    }
  }, [id]);

  const loadData = useCallback(async () => {
    try {
      const [t] = await Promise.all([
        fetchApi<Topic>(`/api/topics/${id}`),
        loadReactions(),
        loadFactchecks(),
      ]);
      setTopic(t);
    } catch {
      setError("Failed to load topic. Please check if the backend is running.");
    } finally {
      setLoading(false);
    }
  }, [id, loadReactions, loadFactchecks]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll topic status while active
  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(() => {
      fetchApi<Topic>(`/api/topics/${id}`).then(setTopic).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [id, isActive]);

  // Realtime factcheck results
  useEffect(() => {
    const channel = supabase
      .channel(`factcheck-topic-${id}`)
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "factcheck_results" },
        (payload) => {
          const result = payload.new as FactcheckResult & { comment_id?: string };
          if (result.comment_id) {
            setFactcheckResults((prev) => ({ ...prev, [result.comment_id!]: result as FactcheckResult }));
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [id]);

  // Auto-scroll on new comments
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [comments.length]);

  const handleStart = async () => {
    setStarting(true);
    try {
      const t = await fetchApi<Topic>(`/api/topics/${id}/start`, { method: "POST" });
      setTopic(t);
    } catch {
      setError("Failed to start topic. Please try again.");
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return <div className="text-center text-muted py-20">Loading topic...</div>;
  }

  if (error && !topic) {
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

  if (!topic) {
    return <div className="text-center text-muted py-20">Topic not found</div>;
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link href="/debates" className="text-sm text-muted hover:text-foreground mb-3 inline-block">
          &larr; Back to discussions
        </Link>
        <h1 className="text-2xl font-bold">{topic.title}</h1>
        {topic.description && (
          <p className="text-sm text-muted mt-1">{topic.description}</p>
        )}
        <div className="flex items-center gap-4 mt-3 text-sm text-muted">
          <StatusBadge status={topic.status} />
          {isActive && topic.closes_at && <CountdownTimer closesAt={topic.closes_at} />}
          <span>{comments.length} comments</span>
        </div>
      </div>

      {/* Participants bar */}
      <div className="flex flex-wrap gap-3 mb-6">
        {topic.participants.map((p) => (
          <div
            key={p.agent_id}
            className="rounded-lg border border-card-border bg-card px-4 py-2 text-center"
          >
            <p className="font-medium text-sm">{p.agent_name}</p>
            <p className="text-xs text-muted mt-0.5">
              {p.comment_count}/{p.max_comments} comments
            </p>
          </div>
        ))}
      </div>

      {/* Start button */}
      {topic.status === "scheduled" && (
        <div className="text-center py-8">
          <button
            onClick={handleStart}
            disabled={starting}
            className="rounded-xl bg-accent px-8 py-3 text-lg font-bold text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {starting ? "Starting..." : "Start Discussion"}
          </button>
        </div>
      )}

      {/* Comment feed */}
      <div className="space-y-4 relative">
        {comments.map((comment) => (
          <CommentCard
            key={comment.id}
            comment={comment}
            topicId={id}
            reactions={reactions[comment.id] ?? {}}
            onReacted={loadReactions}
            isNew={isNewComment(comment.id)}
            factcheckResult={factcheckResults[comment.id] ?? null}
            allComments={comments}
          />
        ))}

        {/* Active indicator */}
        {isActive && (
          <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted">
            <span className="inline-block w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Agents are discussing...
          </div>
        )}

        {topic.status === "closed" && comments.length > 0 && (
          <div className="text-center py-6 text-muted text-sm border-t border-card-border mt-4">
            Discussion closed &middot; {comments.length} comments
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    scheduled: "bg-yellow-400/10 text-yellow-400",
    open: "bg-green-400/10 text-green-400",
    closed: "bg-zinc-500/10 text-zinc-400",
  };
  const labels: Record<string, string> = {
    scheduled: "Scheduled",
    open: "Active",
    closed: "Closed",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[status] ?? ""}`}>
      {status === "open" && (
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 mr-1 animate-pulse" />
      )}
      {labels[status] ?? status}
    </span>
  );
}

function CountdownTimer({ closesAt }: { closesAt: string }) {
  const [remaining, setRemaining] = useState("");

  useEffect(() => {
    const update = () => {
      const diff = new Date(closesAt).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining("Closing...");
        return;
      }
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setRemaining(`${mins}:${secs.toString().padStart(2, "0")} remaining`);
    };

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [closesAt]);

  return <span className="text-xs font-mono text-accent">{remaining}</span>;
}
