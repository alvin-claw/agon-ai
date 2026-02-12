-- ============================================================================
-- AgonAI - Agent Onboarding Schema Extension
-- ============================================================================
-- Migration: 002_agent_onboarding.sql
-- Description: Adds developers, sandbox_results tables and extends agents/debates
-- Created: 2026-02-12
-- ============================================================================

-- ============================================================================
-- TABLE: developers
-- ============================================================================
-- Stores GitHub OAuth authenticated developer accounts
CREATE TABLE developers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_id BIGINT UNIQUE NOT NULL,
    github_login VARCHAR(100) NOT NULL,
    github_avatar_url VARCHAR(500),
    email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- ALTER: agents
-- ============================================================================
-- Link agents to their developer owners
ALTER TABLE agents ADD COLUMN developer_id UUID REFERENCES developers(id) ON DELETE SET NULL;

-- ============================================================================
-- ALTER: debates
-- ============================================================================
-- Flag sandbox debates used for agent verification
ALTER TABLE debates ADD COLUMN is_sandbox BOOLEAN NOT NULL DEFAULT false;

-- ============================================================================
-- TABLE: sandbox_results
-- ============================================================================
-- Stores sandbox verification results for external agents
CREATE TABLE sandbox_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'passed', 'failed')),
    checks JSONB DEFAULT '[]'::jsonb,
    debate_id UUID REFERENCES debates(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- INDEXES
-- ============================================================================
CREATE INDEX idx_agents_developer ON agents(developer_id);
CREATE INDEX idx_sandbox_agent ON sandbox_results(agent_id);
CREATE INDEX idx_developers_github ON developers(github_id);

-- ============================================================================
-- TRIGGERS
-- ============================================================================
CREATE TRIGGER tr_developers_updated_at
    BEFORE UPDATE ON developers FOR EACH ROW EXECUTE FUNCTION update_updated_at();
