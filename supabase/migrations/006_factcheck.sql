-- ============================================================================
-- AgonAI - Fact-Check Schema
-- ============================================================================
-- Migration: 006_factcheck.sql
-- Description: Tables for crowd-sourced fact-check requests and results
-- ============================================================================

CREATE TABLE factcheck_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    turn_id UUID NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    debate_id UUID NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    claim_hash VARCHAR(64) NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(debate_id, claim_hash)
);

CREATE TABLE factcheck_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES factcheck_requests(id) ON DELETE CASCADE,
    turn_id UUID NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
    verdict VARCHAR(30) NOT NULL CHECK (verdict IN ('verified', 'source_mismatch', 'source_inaccessible', 'inconclusive')),
    citation_url TEXT,
    citation_accessible BOOLEAN,
    content_match BOOLEAN,
    logic_valid BOOLEAN,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(request_id)
);

-- Indexes for common query patterns
CREATE INDEX idx_factcheck_req_debate ON factcheck_requests(debate_id);
CREATE INDEX idx_factcheck_req_turn ON factcheck_requests(turn_id);
CREATE INDEX idx_factcheck_results_turn ON factcheck_results(turn_id);

-- Enable real-time subscriptions for live fact-check results
ALTER PUBLICATION supabase_realtime ADD TABLE factcheck_results;
