# -*- coding: utf-8 -*-
"""legal_engine — 법정 동역학 시뮬레이션 엔진 (v0.4.0)

ionia 철학 레이어 내 응용 계층.
Observer + KEMET + Pharaoh 시스템과 연동해
사법 정의 흐름의 정합성을 판단한다.

v0.4.0: 법규범 자체 정합성 분석 모듈 추가
    StatuteProfile, ConstitutionalAnalysis, analyze_norms()
    → 헌법·법률 품질을 6번째 Ω 레이어(Ω_norm)로 통합
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
from .legal_norm_analyzer import (
    StatuteProfile,
    ConstitutionalAnalysis,
    analyze_norms,
    diagnose_statute,
)

__version__ = "0.4.0"
__all__ = [
    # 엔진
    "LegalEngine",
    # 상태·컨텍스트
    "LegalMutable", "LegalParams", "LegalContext",
    "JudgeParams", "ProsecutorParams", "DefenseParams",
    "JuryParams", "DefendantParams", "LegalHierarchy",
    # 법규범 분석 (v0.4.0 신규)
    "StatuteProfile", "ConstitutionalAnalysis",
    "analyze_norms", "diagnose_statute",
    # 이벤트
    "JudicialEvent", "JudicialCourt", "recommend_event",
    # 관찰·진단
    "observe", "diagnose", "to_snapshot",
    # 사법 정의 단계
    "JUSTICE_FAIR", "JUSTICE_DISTORTED", "JUSTICE_COMPROMISED", "JUSTICE_CORRUPTED",
]
