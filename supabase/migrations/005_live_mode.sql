-- ============================================================================
-- AgonAI - Live Mode Schema Changes
-- ============================================================================
-- Migration: 005_live_mode.sql
-- Description: Add live/async mode and viewer count to debates
-- ============================================================================

ALTER TABLE debates ADD COLUMN mode VARCHAR(10) NOT NULL DEFAULT 'async' CHECK (mode IN ('async', 'live'));
ALTER TABLE debates ADD COLUMN viewer_count INTEGER NOT NULL DEFAULT 0;
