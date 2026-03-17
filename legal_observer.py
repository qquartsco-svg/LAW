# -*- coding: utf-8 -*-
"""
legal_observer.py — Observer 5레이어 Ω + 법정 진단

5개 차원:
    Ω_truth      진실 발현도 + 정의 괴리
    Ω_evidence   증거 신뢰성 + 조작 부재
    Ω_legal      법리 정합성 + 법률 계층 온전성
    Ω_bias       편향 부재 + 유착·전관예우 억제
    Ω_procedural 절차적 정당성 + 공개 감시

전역 Ω = Ω_truth×0.30 + Ω_evidence×0.25 + Ω_legal×0.20 + Ω_bias×0.15 + Ω_proc×0.10
판정: JUST(≥0.80) / STABLE(0.60~) / FRAGILE(0.40~) / CRITICAL(<0.40)
"""
from __future__ import annotations

from typing import Dict, Any, List

from .legal_state import (
    LegalMutable, LegalContext,
    compute_derived, compute_flags,
    JUSTICE_FAIR, JUSTICE_DISTORTED, JUSTICE_COMPROMISED, JUSTICE_CORRUPTED,
    _clamp,
)


# ─── Ω 레이어 계산 ─────────────────────────────────────────────────────────────
def _omega_truth(state: LegalMutable, derived: Dict[str, Any]) -> float:
    """L_truth: 진실 발현도 Ω."""
    T     = state.truth_score
    gap   = derived["justice_gap"]
    T_ω   = _clamp(T / 0.80)              # T=0.80 → Ω=1.0, T=0 → Ω=0
    gap_ω = _clamp(1.0 - gap / 0.60)      # gap=0 → Ω=1.0, gap=0.6 → Ω=0
    return T_ω * 0.60 + gap_ω * 0.40


def _omega_evidence(state: LegalMutable, ctx: LegalContext) -> float:
    """L_evidence: 증거 신뢰성 Ω."""
    E     = state.evidence_integrity
    E_ω   = _clamp((E - 0.20) / 0.70)     # E=0.20→0, E=0.90→1
    m_ω   = _clamp(1.0 - ctx.prosecutor.manipulation_tendency)
    return E_ω * 0.65 + m_ω * 0.35


def _omega_legal(state: LegalMutable, ctx: LegalContext) -> float:
    """L_legal: 법리 정합성 Ω."""
    L      = state.legal_coherence
    hier   = ctx.hierarchy.hierarchy_integrity()
    L_ω    = _clamp((L    - 0.20) / 0.70)
    hier_ω = _clamp((hier - 0.40) / 0.55)
    return L_ω * 0.60 + hier_ω * 0.40


def _omega_bias(
    state: LegalMutable,
    ctx: LegalContext,
    derived: Dict[str, Any],
) -> float:
    """L_bias: 편향 Ω (낮은 편향 = 높은 Ω)."""
    B          = state.bias_total
    collusion  = derived["collusion_risk"]
    revolving  = derived["revolving_door_index"]
    bias_ω     = _clamp(1.0 - B         / 0.80)
    coll_ω     = _clamp(1.0 - collusion / 0.70)
    rev_ω      = _clamp(1.0 - revolving / 0.70)
    return bias_ω * 0.50 + coll_ω * 0.25 + rev_ω * 0.25


def _omega_procedural(state: LegalMutable, ctx: LegalContext) -> float:
    """L_procedural: 절차적 정의 Ω."""
    P         = state.procedural_score
    scrutiny  = ctx.public_scrutiny
    P_ω       = _clamp((P - 0.20) / 0.70)
    return P_ω * 0.70 + scrutiny * 0.30


# ─── 전체 관찰 ─────────────────────────────────────────────────────────────────
def observe(state: LegalMutable, ctx: LegalContext) -> Dict[str, Any]:
    """5레이어 Ω 집계 + 전역 Ω + 판정."""
    derived = compute_derived(state, ctx)
    flags   = compute_flags(state, ctx, derived)

    Ω_truth  = _omega_truth(state, derived)
    Ω_evid   = _omega_evidence(state, ctx)
    Ω_legal  = _omega_legal(state, ctx)
    Ω_bias   = _omega_bias(state, ctx, derived)
    Ω_proc   = _omega_procedural(state, ctx)

    Ω_global = (
        Ω_truth  * 0.30
        + Ω_evid  * 0.25
        + Ω_legal * 0.20
        + Ω_bias  * 0.15
        + Ω_proc  * 0.10
    )

    # 사법 단계별 강제 임계치
    stage = derived["justice_stage"]
    if stage == JUSTICE_CORRUPTED:
        Ω_global = min(Ω_global, 0.25)
    elif stage == JUSTICE_COMPROMISED:
        Ω_global = min(Ω_global, 0.45)

    # 판정
    if Ω_global >= 0.80:
        verdict = "JUST"
    elif Ω_global >= 0.60:
        verdict = "STABLE"
    elif Ω_global >= 0.40:
        verdict = "FRAGILE"
    else:
        verdict = "CRITICAL"

    return {
        "Ω_truth":      round(Ω_truth,  4),
        "Ω_evidence":   round(Ω_evid,   4),
        "Ω_legal":      round(Ω_legal,  4),
        "Ω_bias":       round(Ω_bias,   4),
        "Ω_procedural": round(Ω_proc,   4),
        "Ω_global":     round(Ω_global, 4),
        "verdict":      verdict,
        "justice_stage":    stage,
        "justice_gap":      derived["justice_gap"],
        "verdict_score":    derived["verdict_score"],
        "constitutional_integrity": derived["constitutional_integrity"],
        "revolving_door_index":     derived["revolving_door_index"],
        "collusion_risk":           derived["collusion_risk"],
        "flags":        flags,
        "active_flags": sum(flags.values()),
    }


# ─── 진단 조언 ─────────────────────────────────────────────────────────────────
def diagnose(observation: Dict[str, Any]) -> List[str]:
    """플래그 기반 파라오 진단 조언 (Pharaoh Advisory)."""
    flags = observation["flags"]
    advice = []

    if flags.get("verdict_unjust"):
        advice.append("⚠️  판결 정의 괴리 심각 — 상소 또는 재심 검토 필요")
    if flags.get("evidence_tampered"):
        advice.append("🔴 증거 신뢰성 붕괴 — 독립 수사 기구 투입 필요")
    if flags.get("bias_critical"):
        advice.append("🔴 편향 임계 수준 — 판사 기피신청 또는 재배당 검토")
    if flags.get("collusion_suspected"):
        advice.append("🔴 검-판 유착 의심 — 특별검사 또는 외부 감사 필요")
    if flags.get("revolving_door_active"):
        advice.append("⚠️  전관예우 동작 — 법조 이해충돌 방지법 강화 필요")
    if flags.get("constitutional_breach"):
        advice.append("🔴 헌법 적합성 위기 — 헌법재판소 위헌 심판 청구 필요")
    if flags.get("media_capture"):
        advice.append("⚠️  언론 포획 — 판결 전 보도 제한 및 미디어 분리 원칙 강화")
    if flags.get("procedural_violation"):
        advice.append("⚠️  절차 위반 — 공정한 재심리 절차 보장 필요")
    if flags.get("jury_compromised"):
        advice.append("⚠️  배심원 오염 — 격리 강화 또는 배심원단 교체")
    if flags.get("legal_incoherent"):
        advice.append("⚠️  법리 불일치 — 판례 재검토 및 법률 해석 통일 필요")
    if flags.get("truth_suppressed"):
        advice.append("🔴 진실 억압 — 내부 고발자 보호 및 독립 조사 필요")

    if not advice:
        advice.append("✅ 사법 시스템 정상 작동 — 유의미한 위험 신호 없음")

    return advice
