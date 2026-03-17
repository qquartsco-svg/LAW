# -*- coding: utf-8 -*-
"""
legal_state.py — 법정 동역학 상태 변수 정의

RK4 적분 대상 (LegalMutable):
    truth_score       T — 진실이 법정에서 드러난 정도
    evidence_integrity E — 증거 신뢰성
    legal_coherence   L — 법리 정합성 (판례·헌법 일치)
    bias_total        B — 편향 총합 (높을수록 위험: 전관예우+감정+정치)
    procedural_score  P — 절차적 정당성

핵심 통찰:
    숨겨진 진실 ctx.defendant.actual_guilt 와 판결 verdict_score 의 괴리
    = justice_gap = 사법 왜곡의 정도.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

# ─── 표기 규칙 ─────────────────────────────────────────────────────────────────
# 이 파일의 모든 clamp(x)는 clamp(x, 0.0, 1.0) = max(0, min(1, x)) 를 의미한다.

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ─── 사법 정의 단계 ────────────────────────────────────────────────────────────
JUSTICE_FAIR        = "FAIR"         # justice_gap < 0.20
JUSTICE_DISTORTED   = "DISTORTED"    # 0.20 ≤ gap < 0.40
JUSTICE_COMPROMISED = "COMPROMISED"  # 0.40 ≤ gap < 0.60
JUSTICE_CORRUPTED   = "CORRUPTED"    # gap ≥ 0.60


# ─── 참여자 파라미터 ────────────────────────────────────────────────────────────
@dataclass
class JudgeParams:
    """판사 파라미터."""
    impartiality:    float = 0.70  # 공정성 [0=완전 편향, 1=완전 공정]
    experience:      float = 0.70  # 법률 경험·역량
    corruption_risk: float = 0.20  # 부패/전관예우 위험도


@dataclass
class ProsecutorParams:
    """검사 파라미터."""
    evidence_quality:      float = 0.70  # 증거 수집 품질
    manipulation_tendency: float = 0.20  # 증거 조작 경향
    political_pressure:    float = 0.30  # 상부·정치 압력


@dataclass
class DefenseParams:
    """변호사(피고측) 파라미터."""
    skill_level:           float = 0.50  # 법률 기술·경험
    loophole_exploitation: float = 0.30  # 법의 허점 활용도
    unethical_tendency:    float = 0.10  # 비윤리적 전략 경향


@dataclass
class JuryParams:
    """배심원 파라미터 (배심제 미적용 시 weight=0)."""
    emotional_bias:      float = 0.30  # 감정적 편향
    media_influence:     float = 0.30  # 미디어/여론 영향도
    deliberation_quality: float = 0.60  # 숙의 품질
    weight:              float = 0.0   # 배심원 판결 반영 비중 (한국=0.15, 미국=1.0)


@dataclass
class DefendantParams:
    """피고인/피의자 파라미터."""
    actual_guilt:   float = 0.80  # 실제 유죄 [숨겨진 진실 — 시뮬레이션만 앎]
    cooperation:    float = 0.50  # 수사·재판 협조도
    resource_level: float = 0.50  # 재력 (변호인 품질에 영향)


# ─── 법률 계층 구조 ─────────────────────────────────────────────────────────────
@dataclass
class LegalHierarchy:
    """
    헌법 > 법률 > 시행령 > 판례 > 법리 계층.
    각 층이 상위 층과 정합할수록 legal_coherence 향상.
    위헌 상황 → constitution_score 하락 → 전체 legal_coherence 붕괴.
    """
    constitution_score: float = 0.90  # 헌법 적합성
    statute_score:      float = 0.80  # 법률 적합성
    regulation_score:   float = 0.75  # 시행령 적합성
    precedent_score:    float = 0.75  # 판례 정합성
    doctrine_score:     float = 0.70  # 법리 해석 적합성

    def hierarchy_integrity(self) -> float:
        """법률 계층 전체 정합성 — 상위일수록 가중치 높음."""
        return (
            self.constitution_score * 0.35
            + self.statute_score    * 0.25
            + self.regulation_score * 0.15
            + self.precedent_score  * 0.15
            + self.doctrine_score   * 0.10
        )


# ─── ODE 파라미터 ───────────────────────────────────────────────────────────────
@dataclass
class LegalParams:
    """동역학 ODE 파라미터."""
    # Truth dynamics
    alpha_reveal:   float = 0.30  # 증거 → 진실 발현 속도
    beta_suppress:  float = 0.40  # 편향 → 진실 억압 강도
    gamma_converge: float = 0.10  # 진실 자연 수렴 속도

    # Evidence dynamics
    delta_investigate: float = 0.25  # 수사 품질 → 증거 강화
    epsilon_decay:     float = 0.05  # 증거 자연 감쇠율
    zeta_defense:      float = 0.15  # 변호 → 증거 신뢰 도전

    # Legal coherence dynamics
    eta_precedent:  float = 0.20  # 판례 → 법리 수렴 속도
    theta_loophole: float = 0.25  # 허점 활용 → 법리 왜곡

    # Bias dynamics
    iota_corrupt:  float = 0.35  # 부패 압력 → 편향 증가
    kappa_reform:  float = 0.15  # 공개 감시 → 편향 감소
    lambda_decay:  float = 0.05  # 편향 자연 감쇠

    # Procedural dynamics
    mu_restore:    float = 0.20  # 절차 자연 회복 속도
    nu_violation:  float = 0.30  # 편향 → 절차 훼손 강도

    dt: float = 1.0  # 타임스텝 (1 심급 or 1개월 단위)


# ─── 동역학 상태 (RK4 대상) ────────────────────────────────────────────────────
@dataclass
class LegalMutable:
    """RK4 적분 대상 상태 변수 (5개)."""
    t: float = 0.0

    truth_score:        float = 0.50  # T: 진실 발현도   [0, 1]
    evidence_integrity: float = 0.70  # E: 증거 신뢰성   [0, 1]
    legal_coherence:    float = 0.70  # L: 법리 정합성   [0, 1]
    bias_total:         float = 0.30  # B: 편향 총합     [0, 1] ↑ 나쁨
    procedural_score:   float = 0.80  # P: 절차적 정당성 [0, 1]

    def copy(self) -> "LegalMutable":
        return LegalMutable(
            t=self.t,
            truth_score=self.truth_score,
            evidence_integrity=self.evidence_integrity,
            legal_coherence=self.legal_coherence,
            bias_total=self.bias_total,
            procedural_score=self.procedural_score,
        )

    def clamp_all(self) -> None:
        self.truth_score        = _clamp(self.truth_score)
        self.evidence_integrity = _clamp(self.evidence_integrity)
        self.legal_coherence    = _clamp(self.legal_coherence)
        self.bias_total         = _clamp(self.bias_total)
        self.procedural_score   = _clamp(self.procedural_score)


# ─── 컨텍스트 ───────────────────────────────────────────────────────────────────
@dataclass
class LegalContext:
    """사건 컨텍스트 — 참여자 파라미터 + 법률 계층 + 외부 환경."""
    judge:      JudgeParams      = field(default_factory=JudgeParams)
    prosecutor: ProsecutorParams = field(default_factory=ProsecutorParams)
    defense:    DefenseParams    = field(default_factory=DefenseParams)
    jury:       JuryParams       = field(default_factory=JuryParams)
    defendant:  DefendantParams  = field(default_factory=DefendantParams)
    hierarchy:  LegalHierarchy   = field(default_factory=LegalHierarchy)

    # 외부 환경
    media_pressure:           float = 0.30  # 언론 압박 강도
    political_interference:   float = 0.20  # 정치 개입 강도
    public_scrutiny:          float = 0.50  # 공개 감시 강도 (견제)
    institutional_resistance: float = 0.50  # 제도적 부패 저항력


# ─── 파생 지표 계산 ─────────────────────────────────────────────────────────────
def compute_derived(state: LegalMutable, ctx: LegalContext) -> Dict[str, Any]:
    """매 스텝 재계산되는 파생 지표."""
    T = state.truth_score
    E = state.evidence_integrity
    L = state.legal_coherence
    B = state.bias_total
    P = state.procedural_score
    actual_guilt = ctx.defendant.actual_guilt

    # 판결 점수: 진실·증거·법리·절차가 끌어올리고, 편향이 왜곡
    verdict_score = _clamp(
        T * 0.35 + E * 0.30 + L * 0.20 + P * 0.15 - B * 0.35
    )

    # 정의 괴리: 실제 유죄와 판결 점수의 거리
    justice_gap = abs(verdict_score - actual_guilt)

    # 헌법 계층 온전성
    constitutional_integrity = ctx.hierarchy.hierarchy_integrity()

    # 전관예우 지수: 판사 부패 × 변호사 스킬
    revolving_door_index = (
        ctx.judge.corruption_risk * ctx.defense.skill_level * 0.5
    )

    # 검-판 유착 위험
    collusion_risk = (
        ctx.judge.corruption_risk * (1.0 - ctx.judge.impartiality)
        + ctx.prosecutor.political_pressure * 0.3
    )

    # 배심원 편향 지수
    # raw: weight 미적용 — 배심원 자체의 편향 수준 (플래그 판단 기준)
    # weighted: weight 적용 — 판결에 미치는 실질 영향
    jury_bias_raw = ctx.jury.emotional_bias * 0.5 + ctx.jury.media_influence * 0.5
    jury_bias     = jury_bias_raw * ctx.jury.weight

    # 사법 정의 단계
    if justice_gap < 0.20:
        justice_stage = JUSTICE_FAIR
    elif justice_gap < 0.40:
        justice_stage = JUSTICE_DISTORTED
    elif justice_gap < 0.60:
        justice_stage = JUSTICE_COMPROMISED
    else:
        justice_stage = JUSTICE_CORRUPTED

    return {
        "verdict_score":          round(verdict_score, 4),
        "justice_gap":            round(justice_gap, 4),
        "justice_stage":          justice_stage,
        "constitutional_integrity": round(constitutional_integrity, 4),
        "revolving_door_index":   round(revolving_door_index, 4),
        "collusion_risk":         round(collusion_risk, 4),
        "jury_bias":              round(jury_bias, 4),
        "jury_bias_raw":          round(jury_bias_raw, 4),
    }


# ─── 플래그 계산 ────────────────────────────────────────────────────────────────
def compute_flags(
    state: LegalMutable,
    ctx: LegalContext,
    derived: Dict[str, Any],
) -> Dict[str, bool]:
    """11개 위험 플래그."""
    T, E, L, B, P = (
        state.truth_score,
        state.evidence_integrity,
        state.legal_coherence,
        state.bias_total,
        state.procedural_score,
    )
    return {
        "evidence_tampered":     E < 0.35,
        "bias_critical":         B > 0.65,
        "procedural_violation":  P < 0.35,
        "legal_incoherent":      L < 0.35,
        "truth_suppressed":      T < 0.30,
        "revolving_door_active": derived["revolving_door_index"] > 0.35,
        "media_capture":         ctx.media_pressure > 0.65,
        "constitutional_breach": derived["constitutional_integrity"] < 0.55,
        "verdict_unjust":        derived["justice_gap"] > 0.40,
        "collusion_suspected":   derived["collusion_risk"] > 0.45,
        "jury_compromised":      derived["jury_bias_raw"] > 0.40,  # weight 미적용 원시 편향
    }


# ─── 스냅샷 ─────────────────────────────────────────────────────────────────────
def to_snapshot(state: LegalMutable, ctx: LegalContext) -> Dict[str, Any]:
    """상태 → 불변 스냅샷 dict."""
    derived = compute_derived(state, ctx)
    flags   = compute_flags(state, ctx, derived)
    return {
        "t":                   state.t,
        "truth_score":         state.truth_score,
        "evidence_integrity":  state.evidence_integrity,
        "legal_coherence":     state.legal_coherence,
        "bias_total":          state.bias_total,
        "procedural_score":    state.procedural_score,
        **derived,
        "flags":               flags,
        "active_flags":        sum(flags.values()),
    }
