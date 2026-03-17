# -*- coding: utf-8 -*-
"""
legal_dynamics.py — 법정 동역학 ODE + RK4 + 이벤트 충격

5개 상태 변수 연립 ODE:
    dT/dt  truth_score      — 진실 발현·억압·수렴
    dE/dt  evidence_integrity — 증거 강화·감쇠·변호 도전
    dL/dt  legal_coherence  — 법리 판례 수렴·허점 왜곡
    dB/dt  bias_total       — 전관예우·정치 압력·개혁·감쇠
    dP/dt  procedural_score — 절차 회복·편향 훼손
"""
from __future__ import annotations

import copy
from typing import Tuple

from .legal_state import LegalMutable, LegalParams, LegalContext, _clamp


# ─── ODE 미분 ──────────────────────────────────────────────────────────────────
def _derivatives(
    s: LegalMutable,
    params: LegalParams,
    ctx: LegalContext,
) -> Tuple[float, float, float, float, float]:
    """
    (dT, dE, dL, dB, dP) 반환.
    모든 클램프는 ±0.40 이내로 수치 발산 방지.
    """
    T = s.truth_score
    E = s.evidence_integrity
    L = s.legal_coherence
    B = s.bias_total
    P = s.procedural_score

    j  = ctx.judge
    pr = ctx.prosecutor
    de = ctx.defense
    df = ctx.defendant

    # ── dT/dt — 진실 발현도 ──────────────────────────────────────────────────
    # 발현: 증거 × 공정성 × (1 − 편향 × 억압계수)
    truth_reveal = (
        params.alpha_reveal
        * E
        * j.impartiality
        * max(0.0, 1.0 - B * params.beta_suppress)
    )
    # 억압: 편향 × 검사 조작 경향 + 정치 개입
    truth_suppress = (
        B * params.beta_suppress * pr.manipulation_tendency
        + ctx.political_interference * 0.08
    )
    # 자연 수렴: 진실(actual_guilt)으로의 회귀 (절차 × 공정성 × 거리)
    truth_converge = (
        params.gamma_converge
        * (df.actual_guilt - T)
        * P
        * j.impartiality
    )
    dT = truth_reveal - truth_suppress + truth_converge
    dT = _clamp(dT, -0.40, 0.40)

    # ── dE/dt — 증거 신뢰성 ──────────────────────────────────────────────────
    # 증거 강화: 수사 품질 × (1 − 조작경향) × (1 + 협조도 보너스)
    evidence_build = (
        params.delta_investigate
        * pr.evidence_quality
        * (1.0 - pr.manipulation_tendency)
        * (1.0 + df.cooperation * 0.20)
    )
    # 자연 감쇠
    evidence_decay = params.epsilon_decay * E
    # 변호 도전: 스킬 × 허점활용 비례
    defense_challenge = (
        params.zeta_defense
        * de.skill_level
        * (de.loophole_exploitation * 0.5 + 0.5)
        * E  # 실제로 존재하는 증거에만 도전 가능
    )
    dE = evidence_build - evidence_decay - defense_challenge
    dE = _clamp(dE, -0.30, 0.30)

    # ── dL/dt — 법리 정합성 ──────────────────────────────────────────────────
    # 판례 수렴: 법률 계층 정합성으로 회귀
    hier = ctx.hierarchy.hierarchy_integrity()
    hierarchy_pull = params.eta_precedent * (hier - L)
    # 허점 왜곡: 변호사 허점활용 × 법리 모호성
    loophole_distort = (
        params.theta_loophole
        * de.loophole_exploitation
        * (1.0 - ctx.hierarchy.doctrine_score)
    )
    # 정치 압력 → 법리 왜곡
    political_distort = ctx.political_interference * 0.08
    dL = hierarchy_pull - loophole_distort - political_distort
    dL = _clamp(dL, -0.25, 0.25)

    # ── dB/dt — 편향 총합 ────────────────────────────────────────────────────
    # 편향 증가: 전관예우 + 정치압력 + 미디어 압박 (제도 저항에 비례 감쇠)
    revolving = j.corruption_risk * (1.0 - j.impartiality)
    bias_increase = (
        params.iota_corrupt
        * (revolving + pr.political_pressure * 0.30 + ctx.media_pressure * 0.20)
        * (1.0 - ctx.institutional_resistance)
    )
    # 편향 감소: 공개 감시 × 공정성
    bias_decrease = (
        params.kappa_reform
        * ctx.public_scrutiny
        * j.impartiality
    )
    # 자연 감쇠
    bias_natural = params.lambda_decay * B
    dB = bias_increase - bias_decrease - bias_natural
    dB = _clamp(dB, -0.30, 0.30)

    # ── dP/dt — 절차적 정당성 ────────────────────────────────────────────────
    # 자연 회복: 경험 × (1 − 현재 절차점수)
    proc_restore = params.mu_restore * (1.0 - P) * j.experience
    # 편향 훼손: 편향 × (1 − 제도 저항)
    proc_damage = params.nu_violation * B * (1.0 - ctx.institutional_resistance)
    dP = proc_restore - proc_damage
    dP = _clamp(dP, -0.30, 0.30)

    return dT, dE, dL, dB, dP


# ─── RK4 ────────────────────────────────────────────────────────────────────────
def step_rk4(
    state: LegalMutable,
    params: LegalParams,
    ctx: LegalContext,
) -> LegalMutable:
    """RK4 4계 Runge-Kutta 1스텝 적분."""
    h = params.dt

    def deriv(s: LegalMutable) -> Tuple[float, float, float, float, float]:
        return _derivatives(s, params, ctx)

    def advance(
        s: LegalMutable,
        derivs: Tuple[float, float, float, float, float],
        factor: float,
    ) -> LegalMutable:
        ns = s.copy()
        dT, dE, dL, dB, dP = derivs
        ns.truth_score        = s.truth_score        + dT * factor * h
        ns.evidence_integrity = s.evidence_integrity + dE * factor * h
        ns.legal_coherence    = s.legal_coherence    + dL * factor * h
        ns.bias_total         = s.bias_total         + dB * factor * h
        ns.procedural_score   = s.procedural_score   + dP * factor * h
        ns.clamp_all()
        return ns

    k1 = deriv(state)
    s2 = advance(state, k1, 0.5)
    k2 = deriv(s2)
    s3 = advance(state, k2, 0.5)
    k3 = deriv(s3)
    s4 = advance(state, k3, 1.0)
    k4 = deriv(s4)

    next_state = state.copy()
    next_state.t += h

    attrs = [
        "truth_score", "evidence_integrity", "legal_coherence",
        "bias_total",  "procedural_score",
    ]
    for i, attr in enumerate(attrs):
        cur = getattr(state, attr)
        r1, r2, r3, r4 = k1[i], k2[i], k3[i], k4[i]
        setattr(next_state, attr, cur + (h / 6.0) * (r1 + 2 * r2 + 2 * r3 + r4))

    next_state.clamp_all()
    return next_state


# ─── 이벤트 충격 ────────────────────────────────────────────────────────────────
def apply_legal_event(
    state: LegalMutable,
    ctx: LegalContext,
    event_type: str,
    magnitude: float = 1.0,
) -> tuple:
    """
    법적 이벤트 충격 적용 → (새 상태, 새 컨텍스트) 반환.

    이벤트 목록 (12종):
        evidence_fabrication   증거 조작
        evidence_suppression   증거 은폐
        judicial_corruption    판사 부패/전관예우
        media_manipulation     여론 조작
        judicial_reform        사법 개혁
        transparency_law       수사 투명성 법제화
        jury_education         배심원 교육 강화
        precedent_establish    새 판례 확립
        constitutional_review  위헌 심사 청구
        plea_bargain           플리바게닝
        procedural_violation   절차 위반
        star_defense           스타 변호사 투입 (재력 비례)
    """
    ns  = state.copy()
    nc  = copy.deepcopy(ctx)
    m   = magnitude

    if event_type == "evidence_fabrication":
        ns.evidence_integrity -= 0.30 * m
        ns.truth_score        -= 0.15 * m
        nc.prosecutor.manipulation_tendency = min(
            1.0, nc.prosecutor.manipulation_tendency + 0.20 * m
        )

    elif event_type == "evidence_suppression":
        ns.truth_score        -= 0.20 * m
        ns.evidence_integrity -= 0.10 * m

    elif event_type == "judicial_corruption":
        ns.bias_total         += 0.25 * m
        nc.judge.corruption_risk  = min(1.0, nc.judge.corruption_risk  + 0.20 * m)
        nc.judge.impartiality     = max(0.0, nc.judge.impartiality     - 0.20 * m)

    elif event_type == "media_manipulation":
        nc.media_pressure             = min(1.0, nc.media_pressure             + 0.30 * m)
        nc.jury.media_influence       = min(1.0, nc.jury.media_influence       + 0.20 * m)
        ns.bias_total                += 0.10 * m

    elif event_type == "judicial_reform":
        ns.bias_total                   -= 0.20 * m
        nc.institutional_resistance      = min(1.0, nc.institutional_resistance + 0.15 * m)
        nc.judge.corruption_risk         = max(0.0, nc.judge.corruption_risk    - 0.15 * m)

    elif event_type == "transparency_law":
        nc.public_scrutiny               = min(1.0, nc.public_scrutiny              + 0.20 * m)
        nc.prosecutor.manipulation_tendency = max(
            0.0, nc.prosecutor.manipulation_tendency - 0.10 * m
        )
        ns.procedural_score             += 0.10 * m

    elif event_type == "jury_education":
        nc.jury.emotional_bias           = max(0.0, nc.jury.emotional_bias      - 0.15 * m)
        nc.jury.deliberation_quality     = min(1.0, nc.jury.deliberation_quality + 0.15 * m)

    elif event_type == "precedent_establish":
        nc.hierarchy.precedent_score     = min(1.0, nc.hierarchy.precedent_score + 0.15 * m)
        ns.legal_coherence              += 0.10 * m

    elif event_type == "constitutional_review":
        nc.hierarchy.constitution_score  = min(1.0, nc.hierarchy.constitution_score + 0.10 * m)
        ns.legal_coherence              += 0.15 * m
        ns.procedural_score             += 0.05 * m

    elif event_type == "plea_bargain":
        nc.defendant.cooperation         = min(1.0, nc.defendant.cooperation + 0.30 * m)
        ns.truth_score                  += 0.15 * m
        ns.evidence_integrity           += 0.10 * m

    elif event_type == "procedural_violation":
        ns.procedural_score             -= 0.25 * m
        ns.bias_total                   += 0.10 * m

    elif event_type == "star_defense":
        bonus = m * nc.defendant.resource_level
        nc.defense.skill_level           = min(1.0, nc.defense.skill_level          + 0.25 * bonus)
        nc.defense.loophole_exploitation = min(1.0, nc.defense.loophole_exploitation + 0.20 * m)

    ns.clamp_all()
    return ns, nc
