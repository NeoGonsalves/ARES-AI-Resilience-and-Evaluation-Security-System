"""ARES Red-Team Attack Engine — static payloads and self-evolving attacker loop."""

from ares.redteam.payloads import (
    AttackCategory,
    Payload,
    PAYLOAD_LIBRARY,
    get_payloads_by_category,
)
from ares.redteam.attacker import (
    AttackAttempt,
    AttackConfig,
    RedTeamAttacker,
)

from ares.redteam.operators import (
    OPERATOR_REGISTRY,
    apply_operator,
    encode_base64,
    encode_rot13,
    encode_hex,
    encode_leetspeak,
    wrap_xml_tags,
    wrap_markdown_fence,
    wrap_special_delimiters,
    wrap_in_fake_json,
    wrap_in_fake_log,
)

__all__ = [
    "AttackCategory",
    "Payload",
    "PAYLOAD_LIBRARY",
    "get_payloads_by_category",
    "AttackAttempt",
    "AttackConfig",
    "RedTeamAttacker",
    "OPERATOR_REGISTRY",
    "apply_operator",
    "encode_base64",
    "encode_rot13",
    "encode_hex",
    "encode_leetspeak",
    "wrap_xml_tags",
    "wrap_markdown_fence",
    "wrap_special_delimiters",
    "wrap_in_fake_json",
    "wrap_in_fake_log",
]
