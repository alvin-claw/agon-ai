import { useCallback, useEffect, useRef, useState } from "react";
import type { Comment } from "@/types";
import { fetchApi } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export function useTopicComments(topicId: string, isActive: boolean) {
  const [comments, setComments] = useState<Comment[]>([]);
  const seenIds = useRef<Set<string>>(new Set());

  const loadComments = useCallback(async () => {
    try {
      const data = await fetchApi<Comment[]>(`/api/topics/${topicId}/comments`);
      setComments(data);
    } catch {
      // ignore
    }
  }, [topicId]);

  // Initial load
  useEffect(() => {
    loadComments();
  }, [loadComments]);

  // Mark initial comments as seen
  useEffect(() => {
    if (comments.length > 0 && seenIds.current.size === 0) {
      comments.forEach((c) => seenIds.current.add(c.id));
    }
  }, [comments]);

  // Supabase Realtime subscription
  useEffect(() => {
    if (!isActive) return;

    const channel = supabase
      .channel(`topic-comments-${topicId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "comments",
          filter: `topic_id=eq.${topicId}`,
        },
        () => {
          loadComments();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [topicId, isActive, loadComments]);

  // Polling fallback (every 5s while active)
  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(loadComments, 5000);
    return () => clearInterval(interval);
  }, [isActive, loadComments]);

  const isNewComment = (commentId: string): boolean => {
    if (seenIds.current.has(commentId)) return false;
    seenIds.current.add(commentId);
    return true;
  };

  return { comments, isNewComment, reload: loadComments };
}
