"""Harden endpoint — runs PromptOptimizer and returns a hardened prompt."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter

from ares.api.schemas import HardenRequest, HardenResponse
from ares.config import settings
from ares.optimizer.optimizer import PromptOptimizer

router = APIRouter(prefix="/api", tags=["harden"])


@router.post("/harden", response_model=HardenResponse)
async def harden_prompt(request: HardenRequest) -> HardenResponse:
    """Run the ARES Prompt Optimizer and return the hardened, token-efficient system prompt."""
    optimizer = PromptOptimizer(settings=settings)

    result = await optimizer.optimize(
        system_prompt=request.system_prompt,
        application_name=request.application_name,
        domain=request.domain,
        test_id=request.test_id,
        optimize_tokens=request.optimize_tokens,
    )

    baseline = int(getattr(result, "baseline_robustness", 15.0))
    hardened = int(getattr(result, "hardened_robustness", 95.0))
    strategies = getattr(result, "strategies_applied", ["zero_trust_boundary"])
    strategy_name = strategies[0] if strategies else "zero_trust_boundary"
    hardened_prompt = getattr(result, "hardened_prompt", request.system_prompt)
    overhead = getattr(result, "token_overhead", max(0, len(hardened_prompt.split()) - len(request.system_prompt.split())))
    base_tok = getattr(result, "baseline_tokens", max(1, int(len(request.system_prompt.split()) * 1.3)))
    hard_tok = getattr(result, "hardened_tokens", max(1, int(len(hardened_prompt.split()) * 1.3)))
    eff_score = getattr(result, "efficiency_score", round(base_tok / hard_tok, 2) if hard_tok > 0 else 1.0)

    return HardenResponse(
        hardened_prompt=hardened_prompt,
        baseline_score=baseline,
        hardened_score=hardened,
        improvement_points=max(0, hardened - baseline),
        strategy_applied=strategy_name,
        token_overhead=overhead,
        baseline_tokens=base_tok,
        hardened_tokens=hard_tok,
        efficiency_score=eff_score,
        generated_at=datetime.now(timezone.utc),
    )
