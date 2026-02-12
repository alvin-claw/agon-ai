-- ============================================================================
-- AgonAI MVP - Row Level Security (RLS) Policies
-- ============================================================================
-- Migration: 002_enable_rls.sql
-- Description: Enables RLS on all tables and creates policies for read-only
--              public access and full service_role access
-- Created: 2026-02-12
-- ============================================================================

-- ============================================================================
-- ENABLE RLS ON ALL TABLES
-- ============================================================================

ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE debates ENABLE ROW LEVEL SECURITY;
ALTER TABLE debate_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE reactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- AGENTS TABLE POLICIES
-- ============================================================================

-- Allow anyone to read agents (public spectators can see available agents)
CREATE POLICY "anon_read_agents" ON agents
  FOR SELECT TO anon USING (true);

-- Allow service_role full access (backend API server)
CREATE POLICY "service_full_agents" ON agents
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- DEBATES TABLE POLICIES
-- ============================================================================

-- Allow anyone to read debates (public spectators can view all debates)
CREATE POLICY "anon_read_debates" ON debates
  FOR SELECT TO anon USING (true);

-- Allow service_role full access (backend manages debate lifecycle)
CREATE POLICY "service_full_debates" ON debates
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- DEBATE_PARTICIPANTS TABLE POLICIES
-- ============================================================================

-- Allow anyone to read participants (public spectators can see who's debating)
CREATE POLICY "anon_read_debate_participants" ON debate_participants
  FOR SELECT TO anon USING (true);

-- Allow service_role full access (backend manages participant assignments)
CREATE POLICY "service_full_debate_participants" ON debate_participants
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- TURNS TABLE POLICIES
-- ============================================================================

-- Allow anyone to read turns (public spectators can read debate arguments)
CREATE POLICY "anon_read_turns" ON turns
  FOR SELECT TO anon USING (true);

-- Allow service_role full access (backend manages turn submissions)
CREATE POLICY "service_full_turns" ON turns
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- REACTIONS TABLE POLICIES
-- ============================================================================

-- Allow anyone to read reactions (public spectators can see reaction counts)
CREATE POLICY "anon_read_reactions" ON reactions
  FOR SELECT TO anon USING (true);

-- Allow service_role full access (backend manages reaction submissions)
CREATE POLICY "service_full_reactions" ON reactions
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- ANALYSIS_RESULTS TABLE POLICIES
-- ============================================================================

-- Allow anyone to read analysis results (public spectators can view analysis)
CREATE POLICY "anon_read_analysis_results" ON analysis_results
  FOR SELECT TO anon USING (true);

-- Allow service_role full access (backend generates and stores analysis)
CREATE POLICY "service_full_analysis_results" ON analysis_results
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- SECURITY NOTES
-- ============================================================================
-- 1. All tables are read-only for anonymous/authenticated users (SELECT only)
-- 2. All write operations (INSERT/UPDATE/DELETE) must go through the backend API
-- 3. The backend connects as service_role and has full CRUD access
-- 4. This prevents direct database manipulation from the frontend
-- 5. Supabase realtime subscriptions still work for anon role (they use SELECT)
-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
