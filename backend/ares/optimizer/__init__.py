"""
ARES Prompt Optimizer & Hardening Engine.
"""

from ares.optimizer.models import (
    HardeningConfig,
    HardeningIteration,
    HardeningResult,
    HardeningStrategy,
)
from ares.optimizer.optimizer import PromptOptimizer
from ares.optimizer.strategies import (
    build_hardening_instructions,
    format_few_shot_inoculations,
    get_strategy_directive,
    programmatically_harden_prompt,
)

__all__ = [
    "HardeningConfig",
    "HardeningIteration",
    "HardeningResult",
    "HardeningStrategy",
    "PromptOptimizer",
    "build_hardening_instructions",
    "format_few_shot_inoculations",
    "get_strategy_directive",
    "programmatically_harden_prompt",
]
