-- ============================================================================
-- AgonAI - Team Debates Schema Changes
-- ============================================================================
-- Migration: 004_team_debates.sql
-- Description: Remove 1v1-only constraints, add team_id columns
-- ============================================================================

-- Remove constraints that block multi-agent team debates
ALTER TABLE debate_participants DROP CONSTRAINT IF EXISTS debate_participants_debate_id_side_key;
ALTER TABLE debate_participants DROP CONSTRAINT IF EXISTS debate_participants_debate_id_agent_id_key;

-- Add team identifier to participants and turns
ALTER TABLE debate_participants ADD COLUMN team_id VARCHAR(10);
ALTER TABLE turns ADD COLUMN team_id VARCHAR(10);
ALTER TABLE turns ADD COLUMN support_target_id UUID REFERENCES turns(id);
