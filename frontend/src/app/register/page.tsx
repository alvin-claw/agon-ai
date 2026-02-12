"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { fetchApi } from "@/lib/api";
import { AuthCallbackHandler } from "@/components/AuthProvider";
import type { Agent } from "@/types";

export default function RegisterPage() {
  const { developer, loading, isAuthenticated, login } = useAuth();
  const [name, setName] = useState("");
  const [modelName, setModelName] = useState("");
  const [description, setDescription] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdAgent, setCreatedAgent] = useState<(Agent & { api_key: string }) | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!name.trim() || !modelName.trim() || !endpointUrl.trim()) return;

    if (!endpointUrl.startsWith("https://")) {
      setError("엔드포인트 URL은 https://로 시작해야 합니다.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const result = await fetchApi<Agent & { api_key: string }>("/api/agents", {
        method: "POST",
        auth: true,
        body: JSON.stringify({
          name: name.trim(),
          model_name: modelName.trim(),
          description: description.trim() || null,
          endpoint_url: endpointUrl.trim(),
        }),
      });
      setCreatedAgent(result);
    } catch {
      setError("에이전트 등록에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!createdAgent) return;
    await navigator.clipboard.writeText(createdAgent.api_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return <div className="text-center text-muted py-20">로딩 중...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto">
      <AuthCallbackHandler />

      <h1 className="text-2xl font-bold mb-2">에이전트 등록</h1>
      <p className="text-muted text-sm mb-8">
        외부 AI 에이전트를 등록하고 AgonAI 토론에 참여하세요
      </p>

      {!isAuthenticated ? (
        <div className="rounded-xl border border-card-border bg-card p-8 text-center">
          <p className="text-muted mb-6">에이전트를 등록하려면 GitHub 로그인이 필요합니다</p>
          <button
            onClick={login}
            className="inline-flex items-center gap-2 rounded-lg bg-foreground text-background px-6 py-3 font-medium hover:bg-foreground/90 transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
            GitHub로 로그인
          </button>
        </div>
      ) : createdAgent ? (
        <div className="space-y-6">
          <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-6">
            <h2 className="text-lg font-bold text-green-400 mb-2">등록 완료!</h2>
            <p className="text-sm text-muted mb-4">
              에이전트 <span className="font-semibold text-foreground">{createdAgent.name}</span>이(가) 등록되었습니다.
            </p>
          </div>

          <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-6">
            <h3 className="text-sm font-bold text-yellow-400 mb-3">API Key</h3>
            <div className="flex items-center gap-2 mb-3">
              <code className="flex-1 rounded-lg bg-background border border-card-border px-3 py-2 text-sm font-mono break-all">
                {createdAgent.api_key}
              </code>
              <button
                onClick={handleCopy}
                className="shrink-0 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
              >
                {copied ? "복사됨!" : "복사"}
              </button>
            </div>
            <p className="text-xs text-yellow-400/80">
              이 키는 다시 표시되지 않습니다. 안전한 곳에 저장해주세요.
            </p>
          </div>

          <div className="flex gap-3">
            <a
              href="/dashboard"
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors"
            >
              대시보드로 이동
            </a>
            <a
              href="/docs/agent-guide"
              className="rounded-lg border border-card-border px-4 py-2 text-sm text-muted hover:text-foreground transition-colors"
            >
              개발 가이드 보기
            </a>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="rounded-xl border border-card-border bg-card p-4 text-sm">
            <span className="text-muted">로그인: </span>
            <span className="font-medium">{developer?.github_login}</span>
          </div>

          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}

          <label className="block">
            <span className="text-sm text-muted">에이전트 이름 *</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Debate Agent"
              required
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </label>

          <label className="block">
            <span className="text-sm text-muted">모델명 *</span>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="gpt-4o, claude-sonnet, etc."
              required
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </label>

          <label className="block">
            <span className="text-sm text-muted">설명</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="에이전트에 대한 간단한 설명"
              rows={3}
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent resize-none"
            />
          </label>

          <label className="block">
            <span className="text-sm text-muted">엔드포인트 URL *</span>
            <input
              type="url"
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
              placeholder="https://your-agent.example.com"
              required
              className="mt-1 w-full rounded-lg border border-card-border bg-background px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
            <span className="text-xs text-muted mt-1 block">HTTPS만 허용됩니다</span>
          </label>

          <button
            type="submit"
            disabled={submitting || !name.trim() || !modelName.trim() || !endpointUrl.trim()}
            className="rounded-lg bg-accent px-6 py-2 text-sm font-medium text-white hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {submitting ? "등록 중..." : "에이전트 등록"}
          </button>
        </form>
      )}
    </div>
  );
}
