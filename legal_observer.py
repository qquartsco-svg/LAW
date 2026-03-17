# -*- coding: utf-8 -*-
"""
legal_observer.py — Observer 5레이어 Ω + 법정 진단  (v0.2.0)

5개 차원:
    Ω_truth      진실 발현도 + 정의 괴리 (방향성 반영)
    Ω_evidence   증거 신뢰성 + 조작 부재
    Ω_legal      법리 정합성 + 법률 계층 온전성
    Ω_bias       편향 부재 + 유착·전관예우 억제
    Ω_procedural 절차적 정당성 + 공개 감시

전역 Ω = Ω_truth×0.30 + Ω_evidence×0.25 + Ω_legal×0.20 + Ω_bias×0.15 + Ω_procedural×0.10

강제 임계치 (사법 정의 단계별):
    CORRUPTED   (gap ≥ 0.60): Ω ≤ 0.25 → 시스템이 아무리 좋아도 CRITICAL 이하
    COMPROMISED (gap ≥ 0.40): Ω ≤ 0.45 → FRAGILE 이하
    DISTORTED   (gap ≥ 0.20): Ω ≤ 0.70 → STABLE 이하, JUST 불가

판정: JUST(≥0.80) / STABLE(0.60~) / FRAGILE(0.40~) / CRITICAL(<0.40)

v0.2.0 개선:
    - Ω_bias의 revolving 정규화 수정: 이론적 최댓값 1.0에 맞게 조정
      (기존 0.70으로 나누면 최악이어도 Ω_bias > 0 → 수정)
    - DISTORTED 단계 강제 임계치 추가 (Ω ≤ 0.70)
    - Ω_truth에 방향 패널티 추가: 억울한 유죄(over_convicted) 방향이면 추가 감점
    - diagnose(): 방향성 플래그(over_convicted / unjust_acquittal) 진단 추가
    - diagnose(): verdict_unjust를 방향성 플래그와 조합해 더 구체적인 처방 제시
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
    """
    Ω_truth — 진실 발현도 레이어.

    구성:
        T_ω   = T / 0.80          진실 발현도 정규화 (T=0.80 → 1.0)
        gap_ω = 1 − |gap| / 0.60  정의 괴리 정규화 (gap=0 → 1.0, gap=0.60 → 0.0)
        방향 패널티: 억울한 유죄(signed_gap > 0) 방향이면 signed_gap×0.20 감산
                    부당 방면(signed_gap < 0)도 절댓값 동일 패널티

    가중: T_ω×0.60 + gap_ω×0.40
    """
    T           = state.truth_score
    gap         = derived["justice_gap"]
    signed_gap  = derived["signed_justice_gap"]

    T_ω   = _clamp(T / 0.80)                    # T=0.80 → 1.0
    gap_ω = _clamp(1.0 - gap / 0.60)            # gap=0 → 1.0, gap≥0.60 → 0.0

    # 방향 패널티: 억울하거나(+) 부당 방면(-) 방향이 강할수록 gap_ω 추가 감산
    direction_penalty = abs(signed_gap) * 0.20
    gap_ω = _clamp(gap_ω - direction_penalty)

    return T_ω * 0.60 + gap_ω * 0.40


def _omega_evidence(state: LegalMutable, ctx: LegalContext) -> float:
    """
    Ω_evidence — 증거 신뢰성 레이어.

    구성:
        E_ω = (E − 0.20) / 0.70   E=0.20→0, E=0.90→1 (하한 0.20은 구조적 최저선)
        m_ω = 1 − manipulation    조작 경향 없음 → 1.0

    가중: E_ω×0.65 + m_ω×0.35
    """
    E   = state.evidence_integrity
    E_ω = _clamp((E - 0.20) / 0.70)               # 구조적 최저 E=0.20 기준
    m_ω = _clamp(1.0 - ctx.prosecutor.manipulation_tendency)
    return E_ω * 0.65 + m_ω * 0.35


def _omega_legal(state: LegalMutable, ctx: LegalContext) -> float:
    """
    Ω_legal — 법리 정합성 레이어.

    구성:
        L_ω    = (L − 0.20) / 0.70      법리 정합성 정규화
        hier_ω = (hier − 0.40) / 0.55   계층 온전성 정규화
                                          (hier 최솟값 ≈ 0.40, 최댓값 ≈ 0.95)

    가중: L_ω×0.60 + hier_ω×0.40
    """
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
    """
    Ω_bias — 편향 부재 레이어.

    구성:
        bias_ω     = 1 − B / 0.80           편향 수준 역산 (B=0.80 → 0.0)
        coll_ω     = 1 − collusion / 0.70   검-판 유착 역산 (최대 ≈ 1.0+0.3 → clamp)
        rev_ω      = 1 − revolving          전관예우 역산 (이론적 최댓값 1.0)

    v0.2.0: revolving 정규화 수정
        기존 `1 − revolving/0.70`: revolving 최댓값 1.0 → 최악이어도 rev_ω ≥ 0.0 → OK
        → 이론적 최댓값 1.0으로 정규화 = `1 − revolving` (clamp 적용)

    가중: bias_ω×0.50 + coll_ω×0.25 + rev_ω×0.25
    """
    B          = state.bias_total
    collusion  = derived["collusion_risk"]
    revolving  = derived["revolving_door_index"]

    bias_ω     = _clamp(1.0 - B         / 0.80)
    coll_ω     = _clamp(1.0 - collusion / 0.70)
    rev_ω      = _clamp(1.0 - revolving)          # max=1.0 → 최악시 0.0

    return bias_ω * 0.50 + coll_ω * 0.25 + rev_ω * 0.25


def _omega_procedural(state: LegalMutable, ctx: LegalContext) -> float:
    """
    Ω_procedural — 절차적 정당성 레이어.

    구성:
        P_ω      = (P − 0.20) / 0.70   절차 점수 정규화
        scrutiny = public_scrutiny      공개 감시 강도 (외부 견제력)

    가중: P_ω×0.70 + scrutiny×0.30
    """
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

    # ── 사법 단계별 강제 임계치 ──────────────────────────────────────────────
    # 정의 괴리가 클수록 시스템 건전성 상한을 낮춤 (단계 비례 하향)
    stage = derived["justice_stage"]
    if stage == JUSTICE_CORRUPTED:
        # gap ≥ 0.60: 아무리 나머지가 좋아도 CRITICAL 이하 강제
        Ω_global = min(Ω_global, 0.25)
    elif stage == JUSTICE_COMPROMISED:
        # gap ≥ 0.40: FRAGILE 이하 강제
        Ω_global = min(Ω_global, 0.45)
    elif stage == JUSTICE_DISTORTED:
        # gap ≥ 0.20: STABLE 이하 강제 (JUST 불가)
        Ω_global = min(Ω_global, 0.70)

    # ── 판정 ────────────────────────────────────────────────────────────────
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
        "signed_justice_gap": derived["signed_justice_gap"],
        "verdict_direction":  derived["verdict_direction"],
        "verdict_score":    derived["verdict_score"],
        "constitutional_integrity": derived["constitutional_integrity"],
        "revolving_door_index":     derived["revolving_door_index"],
        "collusion_risk":           derived["collusion_risk"],
        "flags":        flags,
        "active_flags": sum(flags.values()),
    }


# ─── 진단 조언 ─────────────────────────────────────────────────────────────────
def diagnose(observation: Dict[str, Any]) -> List[str]:
    """플래그 기반 파라오 진단 조언 (Pharaoh Advisory).

    v0.2.0: 방향성 진단 추가 (over_convicted / unjust_acquittal)
    """
    flags     = observation["flags"]
    direction = observation.get("verdict_direction", "BALANCED")
    stage     = observation.get("justice_stage", "FAIR")
    advice    = []

    # ── 방향성 진단 (최우선: 억울하거나 방면되는 방향 명시) ────────────────
    if flags.get("over_convicted"):
        advice.append(
            "🔴 억울한 유죄 판결 위험 — 판결이 실제 유죄보다 과도, "
            "피고인 재심·상소 강력 권고"
        )
    if flags.get("unjust_acquittal"):
        advice.append(
            "🔴 부당 방면 판결 위험 — 실제 유죄이나 낮은 판결 가능성, "
            "검찰 항소 및 증거 보완 필요"
        )

    # ── 판결 불공정 (방향 무관 절대 괴리) ───────────────────────────────────
    if flags.get("verdict_unjust") and not flags.get("over_convicted") and not flags.get("unjust_acquittal"):
        advice.append("⚠️  판결 정의 괴리 심각 — 상소 또는 재심 검토 필요")

    # ── 증거·진실 ────────────────────────────────────────────────────────────
    if flags.get("evidence_tampered"):
        advice.append("🔴 증거 신뢰성 붕괴 — 독립 수사 기구 투입 필요")
    if flags.get("truth_suppressed"):
        advice.append("🔴 진실 억압 — 내부 고발자 보호 및 독립 조사 필요")

    # ── 편향·유착 ────────────────────────────────────────────────────────────
    if flags.get("bias_critical"):
        advice.append("🔴 편향 임계 수준 — 판사 기피신청 또는 재배당 검토")
    if flags.get("collusion_suspected"):
        advice.append("🔴 검-판 유착 의심 — 특별검사 또는 외부 감사 필요")
    if flags.get("revolving_door_active"):
        advice.append("⚠️  전관예우 동작 — 법조 이해충돌 방지법 강화 필요")

    # ── 제도·헌법 ────────────────────────────────────────────────────────────
    if flags.get("constitutional_breach"):
        advice.append("🔴 헌법 적합성 위기 — 헌법재판소 위헌 심판 청구 필요")
    if flags.get("legal_incoherent"):
        advice.append("⚠️  법리 불일치 — 판례 재검토 및 법률 해석 통일 필요")
    if flags.get("procedural_violation"):
        advice.append("⚠️  절차 위반 — 공정한 재심리 절차 보장 필요")

    # ── 외부 압력 ────────────────────────────────────────────────────────────
    if flags.get("media_capture"):
        advice.append("⚠️  언론 포획 — 판결 전 보도 제한 및 미디어 분리 원칙 강화")
    if flags.get("jury_compromised"):
        advice.append("⚠️  배심원 오염 — 격리 강화 또는 배심원단 교체")

    # ── 단계별 총평 (복합 경고) ──────────────────────────────────────────────
    if stage == JUSTICE_CORRUPTED and not advice:
        advice.append("🔴 CORRUPTED — 사법 시스템 전면 붕괴, 즉각적 외부 개입 필요")
    elif stage == JUSTICE_COMPROMISED and not advice:
        advice.append("⚠️  COMPROMISED — 사법 정의 심각 훼손, 구조적 개혁 필요")

    if not advice:
        advice.append("✅ 사법 시스템 정상 작동 — 유의미한 위험 신호 없음")

    return advice
