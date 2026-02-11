export interface Agent {
  id: string;
  name: string;
  model_name: string;
  description: string;
  status: string;
  is_builtin: boolean;
  endpoint_url: string | null;
  created_at: string;
}

export interface Participant {
  agent_id: string;
  agent_name: string;
  side: "pro" | "con";
  turn_order: number;
}

export interface Debate {
  id: string;
  topic: string;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  format: string;
  max_turns: number;
  current_turn: number;
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

export interface AnalysisResult {
  id: string;
  debate_id: string;
  sentiment_data: Array<{
    turn_number: number;
    side: string;
    token_count: number | null;
    stance: string | null;
  }>;
  citation_stats: {
    pro: { total: number; unique_sources: number };
    con: { total: number; unique_sources: number };
  };
  created_at: string;
}
