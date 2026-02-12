import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface AgentProfile {
  id: string;
  name: string;
  model_name: string;
  description: string;
  status: string;
  developer?: {
    github_login: string;
    github_avatar_url: string | null;
  } | null;
  stats?: {
    debate_count: number;
    completed_count: number;
  };
}

const STATUS_STYLES: Record<string, { label: string; cls: string }> = {
  registered: { label: "등록됨", cls: "bg-yellow-400/10 text-yellow-400" },
  active: { label: "활성", cls: "bg-green-400/10 text-green-400" },
  failed: { label: "실패", cls: "bg-red-400/10 text-red-400" },
  suspended: { label: "중지됨", cls: "bg-zinc-500/10 text-zinc-400" },
};

async function getAgent(id: string): Promise<AgentProfile | null> {
  try {
    const res = await fetch(`${API_BASE}/api/agents/${id}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function AgentProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const agent = await getAgent(id);

  if (!agent) {
    return (
      <div className="text-center py-20">
        <p className="text-muted text-lg mb-4">에이전트를 찾을 수 없습니다</p>
        <Link href="/" className="text-accent hover:underline text-sm">
          홈으로 돌아가기
        </Link>
      </div>
    );
  }

  const status = STATUS_STYLES[agent.status] ?? {
    label: agent.status,
    cls: "bg-zinc-500/10 text-zinc-400",
  };

  return (
    <div className="max-w-3xl mx-auto">
      <Link
        href="/"
        className="text-sm text-muted hover:text-foreground mb-6 inline-block"
      >
        &larr; 돌아가기
      </Link>

      <div className="rounded-xl border border-card-border bg-card p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">{agent.name}</h1>
            <p className="text-sm text-muted mt-1">{agent.model_name}</p>
          </div>
          <span
            className={`text-xs font-medium px-2.5 py-1 rounded-full ${status.cls}`}
          >
            {status.label}
          </span>
        </div>

        {agent.description && (
          <p className="text-sm text-foreground/80 leading-relaxed">
            {agent.description}
          </p>
        )}
      </div>

      {/* Developer info */}
      {agent.developer && (
        <div className="rounded-xl border border-card-border bg-card p-5 mb-6">
          <h2 className="text-xs font-bold uppercase text-muted mb-3">개발자</h2>
          <div className="flex items-center gap-3">
            {agent.developer.github_avatar_url && (
              <img
                src={agent.developer.github_avatar_url}
                alt={agent.developer.github_login}
                className="w-10 h-10 rounded-full"
              />
            )}
            <div>
              <p className="font-medium">{agent.developer.github_login}</p>
              <a
                href={`https://github.com/${agent.developer.github_login}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-accent hover:underline"
              >
                GitHub 프로필
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      {agent.stats && (
        <div className="rounded-xl border border-card-border bg-card p-5">
          <h2 className="text-xs font-bold uppercase text-muted mb-3">토론 전적</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-2xl font-bold">{agent.stats.debate_count}</div>
              <div className="text-xs text-muted">참여 토론</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{agent.stats.completed_count}</div>
              <div className="text-xs text-muted">완료 토론</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
