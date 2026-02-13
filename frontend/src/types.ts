export interface Agent {
  id: string;
  name: string;
  model_name: string;
  description: string;
  status: string;
  is_builtin: boolean;
  endpoint_url: string | null;
  developer_id: string | null;
  created_at: string;
}

export interface Developer {
  id: string;
  github_login: string;
  github_avatar_url: string | null;
  email: string | null;
}

export interface SandboxCheck {
  check: string;
  passed: boolean;
  detail: string | null;
}

export interface SandboxResult {
  id: string;
  agent_id: string;
  status: "running" | "passed" | "failed";
  checks: SandboxCheck[];
  started_at: string;
  completed_at: string | null;
}

export interface Participant {
  agent_id: string;
  agent_name: string;
  side: "pro" | "con";
  turn_order: number;
  team_id: string | null;
}

export interface Debate {
  id: string;
  topic: string;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  format: string;
  mode: "async" | "live";
  max_turns: number;
  current_turn: number;
  viewer_count: number;
  participants: Participant[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface DebateListItem {
  id: string;
  topic: string;
  status: string;
  format: string;
  mode?: "async" | "live";
  max_turns: number;
  current_turn: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface Citation {
  url: string;
  title: string;
  quote: string;
}

export interface Turn {
  id: string;
  debate_id: string;
  agent_id: string;
  turn_number: number;
  status: "pending" | "validated" | "format_error" | "timeout";
  stance: string | null;
  claim: string | null;
  argument: string | null;
  citations: Citation[];
  rebuttal_target_id: string | null;
  support_target_id: string | null;
  team_id: string | null;
  token_count: number | null;
  submitted_at: string | null;
  created_at: string;
}

export interface Reaction {
  id: string;
  turn_id: string;
  reaction_type: string;
  count: number;
}

export interface FactcheckResult {
  id: string;
  request_id: string;
  turn_id: string;
  verdict: "verified" | "source_mismatch" | "source_inaccessible" | "inconclusive";
  citation_url: string | null;
  citation_accessible: boolean | null;
  content_match: boolean | null;
  logic_valid: boolean | null;
  details: {
    citation_results?: Array<{
      url: string;
      title: string;
      accessible: boolean;
      content_match: boolean | null;
      explanation: string;
    }>;
    logic_explanation?: string;
  } | null;
  created_at: string;
}

export interface AnalysisResult {
  id: string;
  debate_id: string;
  sentiment_data: Array<{
    turn_number: number;
    side: string;
    token_count: number | null;
    stance: string | null;
    aggression?: number;  // 0.0-1.0 sentiment score
    confidence?: number;  // 0.0-1.0 sentiment score
  }>;
  citation_stats: {
    pro: { total: number; unique_sources: number; source_types?: Record<string, number> };
    con: { total: number; unique_sources: number; source_types?: Record<string, number> };
  };
  created_at: string;
}
