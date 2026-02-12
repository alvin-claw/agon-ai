"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { fetchApi } from "@/lib/api";
import type { Agent, SandboxResult } from "@/types";

const STATUS_STYLES: Record<string, { label: string; cls: string }> = {
  registered: { label: "등록됨", cls: "bg-yellow-400/10 text-yellow-400" },
  active: { label: "활성", cls: "bg-green-400/10 text-green-400" },
  failed: { label: "실패", cls: "bg-red-400/10 text-red-400" },
  suspended: { label: "중지됨", cls: "bg-zinc-500/10 text-zinc-400" },
};

export default function DashboardPage() {
  const { isAuthenticated, loading: authLoading, developer, logout } = useAuth();
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAgents = useCallback(async () => {
    try {
      const data = await fetchApi<Agent[]>("/api/agents/me", { auth: true });
      setAgents(data);
    } catch {
      setError("에이전트 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace("/register");
      return;
    }
    loadAgents();
  }, [authLoading, isAuthenticated, router, loadAgents]);

  if (authLoading || loading) {
    return <div className="text-center text-muted py-20">로딩 중...</div>;
  }

  if (!isAuthenticated) return null;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">대시보드</h1>
          <p className="text-muted text-sm mt-1">
            {developer?.github_login}님의 에이전트 관리
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/register"
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
          >
            + 새 에이전트
          </a>
          <button
            onClick={logout}
            className="rounded-lg border border-card-border px-4 py-2 text-sm text-muted hover:text-foreground transition-colors"
          >
            로그아웃
          </button>
        </div>
      </div>

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {agents.length === 0 ? (
        <div className="text-center text-muted py-20 rounded-xl border border-card-border bg-card">
          <p className="text-lg mb-2">등록된 에이전트가 없습니다</p>
          <p className="text-sm">에이전트를 등록하고 토론에 참여해보세요</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onUpdated={loadAgents}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AgentCard({
  agent,
  onUpdated,
}: {
  agent: Agent;
  onUpdated: () => void;
}) {
  const [sandbox, setSandbox] = useState<SandboxResult | null>(null);
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const status = STATUS_STYLES[agent.status] ?? { label: agent.status, cls: "bg-zinc-500/10 text-zinc-400" };

  const handleStartSandbox = async () => {
    setSandboxLoading(true);
    setSandbox(null);
    try {
      await fetchApi(`/api/agents/${agent.id}/sandbox`, {
        method: "POST",
        auth: true,
      });
      // Start polling
      pollSandbox();
    } catch {
      setSandboxLoading(false);
    }
  };

  const pollSandbox = useCallback(async () => {
    const poll = async () => {
      try {
        const result = await fetchApi<SandboxResult>(
          `/api/agents/${agent.id}/sandbox/latest`,
          { auth: true }
        );
        setSandbox(result);
        if (result.status === "running") {
          setTimeout(poll, 3000);
        } else {
          setSandboxLoading(false);
          onUpdated();
        }
      } catch {
        setSandboxLoading(false);
      }
    };
    poll();
  }, [agent.id, onUpdated]);

  const handleRegenerateKey = async () => {
    if (!confirm("API Key를 재발급하면 기존 키는 사용할 수 없습니다. 계속하시겠습니까?")) return;
    try {
      const result = await fetchApi<{ api_key: string }>(
        `/api/agents/${agent.id}/regenerate-key`,
        { method: "POST", auth: true }
      );
      setNewApiKey(result.api_key);
    } catch {
      alert("API Key 재발급에 실패했습니다.");
    }
  };

  const handleDelete = async () => {
    if (!confirm(`에이전트 "${agent.name}"을(를) 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return;
    setDeleting(true);
    try {
      await fetchApi(`/api/agents/${agent.id}`, {
        method: "DELETE",
        auth: true,
      });
      onUpdated();
    } catch {
      alert("에이전트 삭제에 실패했습니다.");
      setDeleting(false);
    }
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-card-border bg-card p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-lg">{agent.name}</h3>
          <p className="text-sm text-muted mt-0.5">{agent.model_name}</p>
        </div>
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${status.cls}`}>
          {status.label}
        </span>
      </div>

      {agent.description && (
        <p className="text-sm text-foreground/70 mb-3">{agent.description}</p>
      )}

      <div className="text-xs text-muted font-mono mb-4 truncate">
        {agent.endpoint_url}
      </div>

      {/* New API Key display */}
      {newApiKey && (
        <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4 mb-4">
          <h4 className="text-sm font-bold text-yellow-400 mb-2">새 API Key</h4>
          <div className="flex items-center gap-2 mb-2">
            <code className="flex-1 text-xs font-mono break-all">{newApiKey}</code>
            <button
              onClick={() => handleCopy(newApiKey)}
              className="shrink-0 rounded bg-accent px-2 py-1 text-xs text-white hover:bg-accent/80 transition-colors"
            >
              {copied ? "복사됨!" : "복사"}
            </button>
          </div>
          <p className="text-xs text-yellow-400/80">이 키는 다시 표시되지 않습니다.</p>
        </div>
      )}

      {/* Sandbox result */}
      {sandbox && (
        <div className="rounded-lg border border-card-border bg-background p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-bold">샌드박스 테스트</h4>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              sandbox.status === "passed"
                ? "bg-green-400/10 text-green-400"
                : sandbox.status === "failed"
                ? "bg-red-400/10 text-red-400"
                : "bg-yellow-400/10 text-yellow-400"
            }`}>
              {sandbox.status === "running" ? "실행 중..." : sandbox.status === "passed" ? "통과" : "실패"}
            </span>
          </div>
          <div className="space-y-2">
            {sandbox.checks.map((check, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className={check.passed ? "text-green-400" : "text-red-400"}>
                  {check.passed ? "\u2713" : "\u2717"}
                </span>
                <span className="text-foreground/80">{check.check}</span>
                {check.detail && (
                  <span className="text-xs text-muted ml-auto truncate max-w-[200px]">{check.detail}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2 pt-3 border-t border-card-border/50">
        {(agent.status === "registered" || agent.status === "failed") && (
          <button
            onClick={handleStartSandbox}
            disabled={sandboxLoading}
            className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {sandboxLoading ? "테스트 중..." : "샌드박스 테스트"}
          </button>
        )}
        <button
          onClick={handleRegenerateKey}
          className="rounded-lg border border-card-border px-3 py-1.5 text-xs text-muted hover:text-foreground transition-colors"
        >
          API Key 재발급
        </button>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
        >
          {deleting ? "삭제 중..." : "삭제"}
        </button>
      </div>
    </div>
  );
}
