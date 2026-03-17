# -*- coding: utf-8 -*-
"""legal_engine — 법정 동역학 시뮬레이션 엔진 (v0.3.0)

ionia 철학 레이어 내 응용 계층.
Observer + KEMET + Pharaoh 시스템과 연동해
사법 정의 흐름의 정합성을 판단한다.
"""

from .legal_state import (
    LegalMutable,
    LegalParams,
    LegalContext,
    JudgeParams,
    ProsecutorParams,
    DefenseParams,
    JuryParams,
    DefendantParams,
    LegalHierarchy,
    to_snapshot,
    compute_derived,
    compute_flags,
    JUSTICE_FAIR, JUSTICE_DISTORTED, JUSTICE_COMPROMISED, JUSTICE_CORRUPTED,
)
from .legal_dynamics import step_rk4, apply_legal_event
from .legal_observer import observe, diagnose
from .legal_engine import LegalEngine
from .pharaoh_decree_legal import JudicialEvent, JudicialCourt, recommend_event

__version__ = "0.3.0"
__all__ = [
    "LegalEngine",
    "LegalMutable", "LegalParams", "LegalContext",
    "JudgeParams", "ProsecutorParams", "DefenseParams",
    "JuryParams", "DefendantParams", "LegalHierarchy",
    "JudicialEvent", "JudicialCourt", "recommend_event",
    "observe", "diagnose", "to_snapshot",
    "JUSTICE_FAIR", "JUSTICE_DISTORTED", "JUSTICE_COMPROMISED", "JUSTICE_CORRUPTED",
]
