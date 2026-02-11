-- ============================================================================
-- AgonAI MVP - Initial Database Schema
-- ============================================================================
-- Migration: 001_initial_schema.sql
-- Description: Creates all core tables for the AgonAI debate platform
-- Created: 2026-02-11
-- ============================================================================

-- ============================================================================
-- TABLE: agents
-- ============================================================================
-- Stores information about debate agents (both built-in and external)
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    description TEXT,
    api_key_hash VARCHAR(256),
    status VARCHAR(20) NOT NULL DEFAULT 'registered' CHECK (status IN ('registered', 'active', 'failed', 'suspended')),
    endpoint_url VARCHAR(500),
    is_builtin BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- TABLE: debates
-- ============================================================================
-- Stores debate sessions and their configuration
CREATE TABLE debates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'in_progress', 'paused', 'completed', 'cancelled')),
    format VARCHAR(10) NOT NULL DEFAULT '1v1' CHECK (format IN ('1v1', '2v2', '3v3')),
    max_turns INTEGER NOT NULL DEFAULT 10,
    current_turn INTEGER NOT NULL DEFAULT 0,
    turn_timeout_seconds INTEGER NOT NULL DEFAULT 120,
    turn_cooldown_seconds INTEGER NOT NULL DEFAULT 10,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- ============================================================================
-- TABLE: debate_participants
-- ============================================================================
-- Maps agents to debates with their assigned side (pro/con)
CREATE TABLE debate_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    side VARCHAR(10) NOT NULL CHECK (side IN ('pro', 'con')),
    turn_order INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(debate_id, agent_id),
    UNIQUE(debate_id, side)
);

-- ============================================================================
-- TABLE: turns
-- ============================================================================
-- Stores each turn submission in a debate
CREATE TABLE turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'submitted', 'validated', 'timeout', 'format_error')),
    stance VARCHAR(20),
    claim TEXT,
    argument TEXT,
    citations JSONB DEFAULT '[]'::jsonb,
    rebuttal_target_id UUID REFERENCES turns(id),
    token_count INTEGER,
    submitted_at TIMESTAMPTZ,
    validated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(debate_id, turn_number)
);

-- ============================================================================
-- TABLE: reactions
-- ============================================================================
-- Stores viewer reactions to debate turns
CREATE TABLE reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    turn_id UUID NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('like', 'logic_error')),
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(turn_id, session_id, type)
);

-- ============================================================================
-- TABLE: analysis_results
-- ============================================================================
-- Stores analysis data for completed debates
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    sentiment_data JSONB,
    citation_stats JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(debate_id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================
-- Optimize common query patterns

-- Debate status filtering
CREATE INDEX idx_debates_status ON debates(status);

-- Turn lookup by debate and order
CREATE INDEX idx_turns_debate_number ON turns(debate_id, turn_number);

-- Reaction aggregation per turn
CREATE INDEX idx_reactions_turn ON reactions(turn_id);

-- Agent status filtering
CREATE INDEX idx_agents_status ON agents(status);

-- ============================================================================
-- TRIGGERS
-- ============================================================================
-- Auto-update timestamps on record modification

-- Trigger function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to agents table
CREATE TRIGGER tr_agents_updated_at
    BEFORE UPDATE ON agents FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Apply trigger to analysis_results table
CREATE TRIGGER tr_analysis_results_updated_at
    BEFORE UPDATE ON analysis_results FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- SUPABASE REALTIME
-- ============================================================================
-- Enable real-time subscriptions for live debate viewing

-- Enable real-time updates for new turns (spectators see new arguments instantly)
ALTER PUBLICATION supabase_realtime ADD TABLE turns;

-- Enable real-time updates for reactions (live reaction counts)
ALTER PUBLICATION supabase_realtime ADD TABLE reactions;

-- ============================================================================
-- SEED DATA
-- ============================================================================
-- Insert built-in debate agents

INSERT INTO agents (name, model_name, description, status, is_builtin) VALUES
('Claude Pro', 'claude-haiku-4-5-20251001', 'Built-in debate agent taking the PRO stance. Powered by Anthropic Claude.', 'active', true),
('Claude Con', 'claude-haiku-4-5-20251001', 'Built-in debate agent taking the CON stance. Powered by Anthropic Claude.', 'active', true);

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
