-- Migration: Comment-based discussion system
-- Replaces turn-based debates with free-form agent comments

-- topics (replaces debates for new comment system)
CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'scheduled')),
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    max_comments_per_agent INTEGER NOT NULL DEFAULT 10,
    polling_interval_seconds INTEGER NOT NULL DEFAULT 30,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ
);

-- topic_participants
CREATE TABLE topic_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    max_comments INTEGER NOT NULL DEFAULT 10,
    comment_count INTEGER NOT NULL DEFAULT 0,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(topic_id, agent_id)
);

-- comments
CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    references_ JSONB DEFAULT '[]'::jsonb,
    citations JSONB DEFAULT '[]'::jsonb,
    stance VARCHAR(20),
    token_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_topic_participants_topic ON topic_participants(topic_id);
CREATE INDEX idx_topic_participants_agent ON topic_participants(agent_id);
CREATE INDEX idx_comments_topic ON comments(topic_id);
CREATE INDEX idx_comments_agent ON comments(agent_id);
CREATE INDEX idx_comments_created ON comments(topic_id, created_at);
CREATE INDEX idx_topics_status ON topics(status);

-- Add optional comment_id to existing factcheck/reaction tables
ALTER TABLE factcheck_requests ADD COLUMN comment_id UUID REFERENCES comments(id) ON DELETE CASCADE;
ALTER TABLE factcheck_requests ADD COLUMN topic_id UUID REFERENCES topics(id) ON DELETE CASCADE;
ALTER TABLE factcheck_results ADD COLUMN comment_id UUID REFERENCES comments(id) ON DELETE CASCADE;
ALTER TABLE reactions ADD COLUMN comment_id UUID REFERENCES comments(id) ON DELETE CASCADE;

-- Make turn_id nullable on factcheck_requests (comments don't have turns)
ALTER TABLE factcheck_requests ALTER COLUMN turn_id DROP NOT NULL;
ALTER TABLE factcheck_requests ALTER COLUMN debate_id DROP NOT NULL;

-- Make turn_id nullable on factcheck_results
ALTER TABLE factcheck_results ALTER COLUMN turn_id DROP NOT NULL;

-- Make turn_id nullable on reactions
ALTER TABLE reactions ALTER COLUMN turn_id DROP NOT NULL;

-- Enable Supabase Realtime on comments table
ALTER PUBLICATION supabase_realtime ADD TABLE comments;
