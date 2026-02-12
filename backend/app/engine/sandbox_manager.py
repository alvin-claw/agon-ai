"""Sandbox validation engine for external agents."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
import tiktoken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant, Turn
from app.models.developer import SandboxResult

logger = logging.getLogger(__name__)

SANDBOX_TOPIC = "AI 규제가 필요한가?"
SANDBOX_MAX_TURNS = 6  # 3 per side (round-robin)

_TIKTOKEN_ENCODING = None


def _get_encoding():
    global _TIKTOKEN_ENCODING
    if _TIKTOKEN_ENCODING is None:
        _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")
    return _TIKTOKEN_ENCODING


class SandboxManager:
    """Runs a 3-turn sandbox debate to validate an external agent."""

    def __init__(self, agent_id: UUID, db_factory):
        self.agent_id = agent_id
        self.db_factory = db_factory
        self.sandbox_result_id: UUID | None = None

    async def run(self):
        checks = []
        agent = None
        try:
            async with self.db_factory() as db:
                result = await db.execute(select(Agent).where(Agent.id == self.agent_id))
                agent = result.scalar_one_or_none()
                if not agent or not agent.endpoint_url:
                    await self._save_result(
                        db,
                        "failed",
                        [{"check": "connectivity", "passed": False, "detail": "Agent not found or no endpoint"}],
                    )
                    return

                sandbox_result = SandboxResult(agent_id=self.agent_id, status="running")
                db.add(sandbox_result)
                await db.commit()
                await db.refresh(sandbox_result)
                self.sandbox_result_id = sandbox_result.id

            # Check 1: Connectivity
            connectivity_ok, connectivity_detail = await self._check_connectivity(agent.endpoint_url)
            checks.append({"check": "connectivity", "passed": connectivity_ok, "detail": connectivity_detail})

            if not connectivity_ok:
                await self._finalize(checks, agent)
                return

            # Run sandbox debate (3 turns per side)
            turn_results = await self._run_sandbox_debate(agent)

            # Evaluate turn results
            checks.extend(self._evaluate_turns(turn_results))

            await self._finalize(checks, agent)

        except Exception as e:
            logger.error(f"Sandbox for agent {self.agent_id} failed: {e}", exc_info=True)
            checks.append({"check": "connectivity", "passed": False, "detail": str(e)[:200]})
            try:
                if self.sandbox_result_id:
                    await self._finalize(checks, agent)
                else:
                    async with self.db_factory() as db:
                        await self._save_result(db, "failed", checks)
            except Exception:
                logger.error(f"Failed to save sandbox failure for {self.agent_id}", exc_info=True)

    async def _check_connectivity(self, endpoint_url: str) -> tuple[bool, str]:
        """Check if the agent endpoint is reachable via GET /health."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{endpoint_url}/health")
            if resp.status_code == 200:
                return True, "Endpoint reachable"
            return False, f"Health check returned status {resp.status_code}"
        except httpx.TimeoutException:
            return False, "Health check timed out (10s)"
        except httpx.ConnectError as e:
            return False, f"Connection failed: {str(e)[:150]}"
        except Exception as e:
            return False, f"Connectivity error: {str(e)[:150]}"

    async def _run_sandbox_debate(self, agent: Agent) -> list[dict]:
        """Run a sandbox debate: builtin Claude Pro vs external agent (con side)."""
        from app.agents.claude_agent import ClaudeDebateAgent
        from app.agents.external_agent import ExternalDebateAgent

        async with self.db_factory() as db:
            # Find the builtin pro agent
            result = await db.execute(
                select(Agent).where(Agent.is_builtin == True, Agent.name == "Claude Pro")
            )
            builtin_agent = result.scalar_one_or_none()
            if not builtin_agent:
                result = await db.execute(select(Agent).where(Agent.is_builtin == True).limit(1))
                builtin_agent = result.scalar_one_or_none()
            if not builtin_agent:
                raise ValueError("No builtin agent found for sandbox debate")

            # Create sandbox debate
            debate = Debate(
                topic=SANDBOX_TOPIC,
                format="1v1",
                max_turns=SANDBOX_MAX_TURNS,
                is_sandbox=True,
                status="in_progress",
                started_at=datetime.now(timezone.utc),
            )
            db.add(debate)
            await db.flush()

            db.add(DebateParticipant(debate_id=debate.id, agent_id=builtin_agent.id, side="pro", turn_order=0))
            db.add(DebateParticipant(debate_id=debate.id, agent_id=agent.id, side="con", turn_order=1))
            await db.commit()

            debate_id = debate.id
            builtin_agent_snapshot = builtin_agent

        # Link sandbox_result to debate
        async with self.db_factory() as db:
            result = await db.execute(select(SandboxResult).where(SandboxResult.id == self.sandbox_result_id))
            sr = result.scalar_one()
            sr.debate_id = debate_id
            await db.commit()

        # Create agent implementations
        pro_agent_impl = ClaudeDebateAgent(builtin_agent_snapshot, "pro")
        con_agent_impl = ExternalDebateAgent(agent, "con")

        previous_turns: list[Turn] = []
        external_turn_results: list[dict] = []

        for turn_number in range(1, SANDBOX_MAX_TURNS + 1):
            is_pro_turn = (turn_number % 2) == 1
            current_impl = pro_agent_impl if is_pro_turn else con_agent_impl
            current_side = "pro" if is_pro_turn else "con"
            current_agent_id = builtin_agent_snapshot.id if is_pro_turn else agent.id

            # Create pending turn record
            async with self.db_factory() as db:
                turn = Turn(
                    debate_id=debate_id,
                    agent_id=current_agent_id,
                    turn_number=turn_number,
                    status="pending",
                )
                db.add(turn)
                await db.commit()
                await db.refresh(turn)
                turn_id = turn.id

            try:
                turn_data = await asyncio.wait_for(
                    current_impl.generate_turn(
                        topic=SANDBOX_TOPIC,
                        side=current_side,
                        previous_turns=previous_turns,
                        turn_number=turn_number,
                    ),
                    timeout=120.0,
                )

                # Save validated turn
                async with self.db_factory() as db:
                    result = await db.execute(select(Turn).where(Turn.id == turn_id))
                    db_turn = result.scalar_one()
                    db_turn.stance = turn_data.get("stance")
                    db_turn.claim = turn_data.get("claim")
                    db_turn.argument = turn_data.get("argument", "")
                    db_turn.citations = turn_data.get("citations", [])
                    db_turn.token_count = turn_data.get("token_count", 0)
                    db_turn.status = "validated"
                    db_turn.submitted_at = datetime.now(timezone.utc)
                    db_turn.validated_at = datetime.now(timezone.utc)
                    await db.commit()
                    await db.refresh(db_turn)
                    previous_turns.append(db_turn)

                if not is_pro_turn:
                    external_turn_results.append({"turn_data": turn_data, "timed_out": False, "error": None})

                logger.info(f"Sandbox turn {turn_number} ({current_side}) completed")

            except asyncio.TimeoutError:
                async with self.db_factory() as db:
                    result = await db.execute(select(Turn).where(Turn.id == turn_id))
                    db_turn = result.scalar_one()
                    db_turn.status = "timeout"
                    db_turn.claim = "[Agent timed out]"
                    db_turn.argument = "[No response within time limit]"
                    db_turn.citations = []
                    await db.commit()
                    await db.refresh(db_turn)
                    previous_turns.append(db_turn)

                if not is_pro_turn:
                    external_turn_results.append({"turn_data": None, "timed_out": True, "error": None})
                logger.warning(f"Sandbox turn {turn_number} ({current_side}) timed out")

            except Exception as e:
                logger.error(f"Sandbox turn {turn_number} error: {e}", exc_info=True)
                async with self.db_factory() as db:
                    result = await db.execute(select(Turn).where(Turn.id == turn_id))
                    db_turn = result.scalar_one()
                    db_turn.status = "format_error"
                    db_turn.claim = "[Error]"
                    db_turn.argument = f"[Error: {str(e)[:200]}]"
                    db_turn.citations = []
                    await db.commit()
                    await db.refresh(db_turn)
                    previous_turns.append(db_turn)

                if not is_pro_turn:
                    external_turn_results.append({"turn_data": None, "timed_out": False, "error": str(e)[:200]})

        # Complete sandbox debate
        async with self.db_factory() as db:
            result = await db.execute(select(Debate).where(Debate.id == debate_id))
            debate = result.scalar_one()
            debate.status = "completed"
            debate.completed_at = datetime.now(timezone.utc)
            await db.commit()

        return external_turn_results

    def _evaluate_turns(self, turn_results: list[dict]) -> list[dict]:
        """Evaluate external agent turn results against sandbox checks."""
        checks = []

        # json_format: all turns returned valid JSON with required fields
        json_ok = bool(turn_results) and all(
            r["turn_data"] is not None and r["error"] is None for r in turn_results
        )
        checks.append({
            "check": "json_format",
            "passed": json_ok,
            "detail": "All turns returned valid JSON" if json_ok else "One or more turns failed to return valid JSON",
        })

        # timeout: no turns timed out
        timeout_ok = not any(r["timed_out"] for r in turn_results)
        checks.append({
            "check": "timeout",
            "passed": timeout_ok,
            "detail": "All turns responded within timeout" if timeout_ok else "One or more turns timed out",
        })

        # token_limit: all turns under 500 tokens
        token_ok = True
        for r in turn_results:
            if r["turn_data"] and r["turn_data"].get("token_count", 0) > 500:
                token_ok = False
                break
        checks.append({
            "check": "token_limit",
            "passed": token_ok,
            "detail": "All turns within 500 token limit" if token_ok else "One or more turns exceeded 500 token limit",
        })

        # citation: all turns include at least one citation
        has_valid = any(r["turn_data"] for r in turn_results)
        citation_ok = has_valid and all(
            len(r["turn_data"].get("citations", [])) >= 1
            for r in turn_results if r["turn_data"]
        )
        checks.append({
            "check": "citation",
            "passed": citation_ok,
            "detail": "All turns include citations" if citation_ok else "One or more turns missing citations",
        })

        # stance_consistency: all turns maintain correct stance (con)
        stance_ok = has_valid and all(
            r["turn_data"].get("stance") == "con"
            for r in turn_results if r["turn_data"]
        )
        checks.append({
            "check": "stance_consistency",
            "passed": stance_ok,
            "detail": "Consistent con stance maintained" if stance_ok else "Stance inconsistency detected",
        })

        return checks

    async def _finalize(self, checks: list[dict], agent: Agent | None):
        """Update sandbox result and agent status based on checks."""
        all_passed = all(c["passed"] for c in checks)
        final_status = "passed" if all_passed else "failed"

        async with self.db_factory() as db:
            result = await db.execute(select(SandboxResult).where(SandboxResult.id == self.sandbox_result_id))
            sr = result.scalar_one()
            sr.status = final_status
            sr.checks = checks
            sr.completed_at = datetime.now(timezone.utc)
            await db.commit()

        if agent:
            async with self.db_factory() as db:
                result = await db.execute(select(Agent).where(Agent.id == self.agent_id))
                db_agent = result.scalar_one_or_none()
                if db_agent:
                    db_agent.status = "active" if all_passed else "failed"
                    await db.commit()

        logger.info(f"Sandbox for agent {self.agent_id} completed: {final_status}")

    async def _save_result(self, db: AsyncSession, status: str, checks: list[dict]):
        """Quick save for early failures when no sandbox_result_id exists yet."""
        sr = SandboxResult(
            agent_id=self.agent_id,
            status=status,
            checks=checks,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(sr)
        await db.commit()
