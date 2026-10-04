"""
ARES Canonical Category Mapping Layer.

Bridges the 8 frontend/API attack categories (AresModels.cs, OpenAPI schema)
with the 5 backend exploit categories (payloads.py, Qdrant vectors, benchmarks).
"""

from __future__ import annotations

from typing import Dict, List, Optional
from ares.api.schemas import AttackCategoryEnum
from ares.redteam.payloads import AttackCategory

# 8 Frontend/OpenAPI categories -> 5 Backend exploit categories
FRONTEND_TO_BACKEND: Dict[AttackCategoryEnum, AttackCategory] = {
    AttackCategoryEnum.direct_prompt_injection:   AttackCategory.INSTRUCTION_OVERRIDE,
    AttackCategoryEnum.system_prompt_extraction:  AttackCategory.INSTRUCTION_OVERRIDE,
    AttackCategoryEnum.policy_bypass:             AttackCategory.INSTRUCTION_OVERRIDE,
    AttackCategoryEnum.role_manipulation:         AttackCategory.ROLE_PLAY_HIJACK,
    AttackCategoryEnum.tool_misuse:               AttackCategory.DELIMITER_CONFUSION,
    AttackCategoryEnum.encoding_or_obfuscation:   AttackCategory.ENCODING_TRICKS,
    AttackCategoryEnum.indirect_prompt_injection: AttackCategory.CONTEXT_SMUGGLING,
    AttackCategoryEnum.data_exfiltration:         AttackCategory.CONTEXT_SMUGGLING,
}

# String-based lookup dictionary for flexible resolution
STRING_TO_BACKEND: Dict[str, AttackCategory] = {
    # Frontend keys (kebab, snake, camel)
    "direct_prompt_injection":    AttackCategory.INSTRUCTION_OVERRIDE,
    "directpromptinjection":      AttackCategory.INSTRUCTION_OVERRIDE,
    "system_prompt_extraction":   AttackCategory.INSTRUCTION_OVERRIDE,
    "systempromptextraction":     AttackCategory.INSTRUCTION_OVERRIDE,
    "policy_bypass":              AttackCategory.INSTRUCTION_OVERRIDE,
    "policybypass":               AttackCategory.INSTRUCTION_OVERRIDE,
    "instruction_override":       AttackCategory.INSTRUCTION_OVERRIDE,
    "instructionoverride":        AttackCategory.INSTRUCTION_OVERRIDE,

    "role_manipulation":          AttackCategory.ROLE_PLAY_HIJACK,
    "rolemanipulation":           AttackCategory.ROLE_PLAY_HIJACK,
    "role_play_hijack":           AttackCategory.ROLE_PLAY_HIJACK,
    "roleplayhijack":             AttackCategory.ROLE_PLAY_HIJACK,

    "tool_misuse":                AttackCategory.DELIMITER_CONFUSION,
    "toolmisuse":                 AttackCategory.DELIMITER_CONFUSION,
    "delimiter_confusion":        AttackCategory.DELIMITER_CONFUSION,
    "delimiterconfusion":         AttackCategory.DELIMITER_CONFUSION,

    "encoding_or_obfuscation":    AttackCategory.ENCODING_TRICKS,
    "encodingorobfuscation":      AttackCategory.ENCODING_TRICKS,
    "encoding_tricks":            AttackCategory.ENCODING_TRICKS,
    "encodingtricks":             AttackCategory.ENCODING_TRICKS,

    "indirect_prompt_injection":  AttackCategory.CONTEXT_SMUGGLING,
    "indirectpromptinjection":    AttackCategory.CONTEXT_SMUGGLING,
    "data_exfiltration":          AttackCategory.CONTEXT_SMUGGLING,
    "dataexfiltration":           AttackCategory.CONTEXT_SMUGGLING,
    "context_smuggling":          AttackCategory.CONTEXT_SMUGGLING,
    "contextsmuggling":           AttackCategory.CONTEXT_SMUGGLING,
}

# 5 Backend exploit categories -> Canonical frontend counterpart
BACKEND_TO_FRONTEND: Dict[AttackCategory, AttackCategoryEnum] = {
    AttackCategory.INSTRUCTION_OVERRIDE: AttackCategoryEnum.direct_prompt_injection,
    AttackCategory.ROLE_PLAY_HIJACK:     AttackCategoryEnum.role_manipulation,
    AttackCategory.DELIMITER_CONFUSION:   AttackCategoryEnum.tool_misuse,
    AttackCategory.ENCODING_TRICKS:       AttackCategoryEnum.encoding_or_obfuscation,
    AttackCategory.CONTEXT_SMUGGLING:     AttackCategoryEnum.indirect_prompt_injection,
}

# Backend string -> C# PascalCase identifier
BACKEND_TO_CSHARP: Dict[str, str] = {
    "instruction_override": "DirectPromptInjection",
    "role_play_hijack":     "RoleManipulation",
    "delimiter_confusion":  "ToolMisuse",
    "encoding_tricks":      "EncodingOrObfuscation",
    "context_smuggling":    "IndirectPromptInjection",
}


def to_backend_category(category: AttackCategory | AttackCategoryEnum | str) -> AttackCategory:
    """Resolve any frontend or string category to the canonical backend AttackCategory."""
    if isinstance(category, AttackCategory):
        return category
    if isinstance(category, AttackCategoryEnum):
        return FRONTEND_TO_BACKEND.get(category, AttackCategory.INSTRUCTION_OVERRIDE)
    
    clean = str(category).lower().strip()
    if clean.startswith("attackcategory."):
        clean = clean.split(".", 1)[1].strip()

    if clean in STRING_TO_BACKEND:
        return STRING_TO_BACKEND[clean]
    
    # Try normalized alphanumeric
    alphanumeric = "".join(c for c in clean if c.isalnum())
    if alphanumeric in STRING_TO_BACKEND:
        return STRING_TO_BACKEND[alphanumeric]
        
    return AttackCategory.INSTRUCTION_OVERRIDE


def to_frontend_category(category: AttackCategory | str) -> AttackCategoryEnum:
    """Map a backend category to its primary frontend AttackCategoryEnum representation."""
    if isinstance(category, AttackCategory):
        return BACKEND_TO_FRONTEND.get(category, AttackCategoryEnum.direct_prompt_injection)
    
    backend_cat = to_backend_category(category)
    return BACKEND_TO_FRONTEND.get(backend_cat, AttackCategoryEnum.direct_prompt_injection)


def to_csharp_name(category: AttackCategory | AttackCategoryEnum | str) -> str:
    """Map a category string or enum to C# PascalCase enum name."""
    backend_cat = to_backend_category(category).value
    return BACKEND_TO_CSHARP.get(backend_cat, "DirectPromptInjection")
