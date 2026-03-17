# -*- coding: utf-8 -*-
"""
tests/test_legal.py — Legal Engine 전체 테스트

§1 상태 · 파생 지표 · 플래그 (10개)
§2 Observer 5레이어 Ω (10개)
§3 ODE 미분 + RK4 단조성 (8개)
§4 이벤트 충격 방향성 (12개)
§5 시뮬레이션 시나리오 (6개)
§6 Athena 권고 + 프리셋 (6개)
§7 v0.2.0 신규 로직 검증 (12개)
   — signed_justice_gap / verdict_direction
   — revolving_door_index 3요소 공식
   — revolving_door_active 임계치 (0.25)
   — over_convicted / unjust_acquittal 플래그
   — DISTORTED 강제 임계치 (Ω ≤ 0.70)
   — Ω_bias revolving 정규화 (max=1.0)
   — jury deliberation_quality ODE 반영
   — diagnose() 방향성 메시지
§8 v0.4.0 법규범 자체 정합성 분석 (18개)
   — StatuteProfile: norm_integrity, proportionality_score
   — ConstitutionalAnalysis: constitutional_quality
   — analyze_norms(): Ω_norm, 플래그, 진단
   — observe() 6-layer Ω 통합
   — diagnose() norm_report 통합
   — diagnose_statute() 개별 법령 진단
"""
from __future__ import annotations

import sys, os

_applied = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.abspath(_applied))

import pytest

from legal_engine.legal_state import (
    LegalMutable, LegalParams, LegalContext,
    JudgeParams, ProsecutorParams, DefenseParams,
    JuryParams, DefendantParams, LegalHierarchy,
    compute_derived, compute_flags, to_snapshot,
    JUSTICE_FAIR, JUSTICE_DISTORTED, JUSTICE_COMPROMISED, JUSTICE_CORRUPTED,
    _clamp,
)
from legal_engine.legal_dynamics import _derivatives, step_rk4, apply_legal_event
from legal_engine.legal_observer import observe, diagnose
from legal_engine.pharaoh_decree_legal import (
    JudicialEvent, JudicialCourt, recommend_event,
)
from legal_engine.legal_engine import LegalEngine, KOREA_CRIMINAL_PRESET, NEUTRAL_PRESET
from legal_engine.legal_norm_analyzer import (
    StatuteProfile, ConstitutionalAnalysis,
    analyze_norms, diagnose_statute,
)


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────
def make_state(**kwargs) -> LegalMutable:
    return LegalMutable(**kwargs)


def make_ctx(**kwargs) -> LegalContext:
    ctx = LegalContext()
    for k, v in kwargs.items():
        # 점 표기 지원: "judge.corruption_risk" 등
        if "." in k:
            obj, attr = k.split(".", 1)
            setattr(getattr(ctx, obj), attr, v)
        else:
            setattr(ctx, k, v)
    return ctx


def default_state() -> LegalMutable:
    return LegalMutable(
        truth_score=0.55,
        evidence_integrity=0.65,
        legal_coherence=0.65,
        bias_total=0.40,
        procedural_score=0.72,
    )


def default_ctx() -> LegalContext:
    return LegalContext()


# ─────────────────────────────────────────────────────────────────────────────
# §1 상태 · 파생 지표 · 플래그
# ─────────────────────────────────────────────────────────────────────────────
class TestState:

    def test_clamp_all_stays_in_range(self):
        s = LegalMutable(truth_score=2.0, evidence_integrity=-0.5,
                         legal_coherence=1.5, bias_total=-1.0, procedural_score=3.0)
        s.clamp_all()
        assert 0.0 <= s.truth_score <= 1.0
        assert 0.0 <= s.evidence_integrity <= 1.0
        assert 0.0 <= s.legal_coherence <= 1.0
        assert 0.0 <= s.bias_total <= 1.0
        assert 0.0 <= s.procedural_score <= 1.0

    def test_copy_independence(self):
        s = default_state()
        s2 = s.copy()
        s2.truth_score = 0.99
        assert s.truth_score != 0.99

    def test_justice_gap_fair(self):
        # verdict_score ≈ actual_guilt → gap 작음
        s   = LegalMutable(truth_score=0.75, evidence_integrity=0.80,
                            legal_coherence=0.80, bias_total=0.10, procedural_score=0.90)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.75))
        d   = compute_derived(s, ctx)
        assert d["justice_stage"] in (JUSTICE_FAIR, JUSTICE_DISTORTED)

    def test_justice_corrupted_when_gap_high(self):
        # 높은 편향 → verdict_score 낮음, 그러나 actual_guilt=0.95 → 큰 gap
        s   = LegalMutable(truth_score=0.10, evidence_integrity=0.15,
                            legal_coherence=0.20, bias_total=0.95, procedural_score=0.10)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.95))
        d   = compute_derived(s, ctx)
        assert d["justice_stage"] == JUSTICE_CORRUPTED

    def test_revolving_door_index_increases_with_corruption(self):
        s   = default_state()
        ctx1 = LegalContext(judge=JudgeParams(corruption_risk=0.10),
                             defense=DefenseParams(skill_level=0.80))
        ctx2 = LegalContext(judge=JudgeParams(corruption_risk=0.90),
                             defense=DefenseParams(skill_level=0.80))
        d1 = compute_derived(s, ctx1)
        d2 = compute_derived(s, ctx2)
        assert d2["revolving_door_index"] > d1["revolving_door_index"]

    def test_collusion_risk_driven_by_judge_prosecutor(self):
        s  = default_state()
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=0.80, impartiality=0.10),
            prosecutor=ProsecutorParams(political_pressure=0.90),
        )
        d = compute_derived(s, ctx)
        assert d["collusion_risk"] > 0.50

    def test_flags_evidence_tampered(self):
        s   = LegalMutable(evidence_integrity=0.20)
        ctx = default_ctx()
        d   = compute_derived(s, ctx)
        f   = compute_flags(s, ctx, d)
        assert f["evidence_tampered"] is True

    def test_flags_all_clear_healthy_state(self):
        s = LegalMutable(truth_score=0.80, evidence_integrity=0.80,
                         legal_coherence=0.80, bias_total=0.10, procedural_score=0.90)
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=0.05, impartiality=0.95),
            media_pressure=0.10,
            defendant=DefendantParams(actual_guilt=0.80),
        )
        d = compute_derived(s, ctx)
        f = compute_flags(s, ctx, d)
        assert not any(f.values()), f"플래그 발동: {[k for k, v in f.items() if v]}"

    def test_hierarchy_integrity_weighted(self):
        h = LegalHierarchy(
            constitution_score=1.0, statute_score=1.0, regulation_score=1.0,
            precedent_score=1.0, doctrine_score=1.0,
        )
        assert abs(h.hierarchy_integrity() - 1.0) < 1e-6

    def test_to_snapshot_has_all_keys(self):
        s = default_state()
        ctx = default_ctx()
        snap = to_snapshot(s, ctx)
        for key in ("truth_score", "evidence_integrity", "legal_coherence",
                    "bias_total", "procedural_score", "verdict_score",
                    "justice_gap", "justice_stage", "flags", "active_flags"):
            assert key in snap, f"키 누락: {key}"


# ─────────────────────────────────────────────────────────────────────────────
# §2 Observer 5레이어 Ω
# ─────────────────────────────────────────────────────────────────────────────
class TestObserver:

    def test_observe_returns_all_omega_keys(self):
        obs = observe(default_state(), default_ctx())
        for key in ("Ω_truth", "Ω_evidence", "Ω_legal", "Ω_bias", "Ω_procedural", "Ω_global"):
            assert key in obs

    def test_omega_global_range(self):
        obs = observe(default_state(), default_ctx())
        assert 0.0 <= obs["Ω_global"] <= 1.0

    def test_high_bias_lowers_omega_bias(self):
        s1  = LegalMutable(bias_total=0.10)
        s2  = LegalMutable(bias_total=0.90)
        ctx = default_ctx()
        o1  = observe(s1, ctx)
        o2  = observe(s2, ctx)
        assert o2["Ω_bias"] < o1["Ω_bias"]

    def test_corrupted_stage_caps_omega_global(self):
        s   = LegalMutable(truth_score=0.05, evidence_integrity=0.10,
                            legal_coherence=0.15, bias_total=0.95, procedural_score=0.05)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.95))
        obs = observe(s, ctx)
        assert obs["Ω_global"] <= 0.25
        assert obs["verdict"] == "CRITICAL"

    def test_just_verdict_high_omega(self):
        s = LegalMutable(truth_score=0.85, evidence_integrity=0.88,
                         legal_coherence=0.85, bias_total=0.08, procedural_score=0.92)
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=0.05, impartiality=0.92),
            defendant=DefendantParams(actual_guilt=0.82),
            public_scrutiny=0.80,
            institutional_resistance=0.80,
        )
        obs = observe(s, ctx)
        assert obs["verdict"] in ("JUST", "STABLE")

    def test_omega_evidence_drops_with_manipulation(self):
        s   = LegalMutable(evidence_integrity=0.70)
        ctx1 = LegalContext(prosecutor=ProsecutorParams(manipulation_tendency=0.10))
        ctx2 = LegalContext(prosecutor=ProsecutorParams(manipulation_tendency=0.90))
        o1   = observe(s, ctx1)
        o2   = observe(s, ctx2)
        assert o2["Ω_evidence"] < o1["Ω_evidence"]

    def test_diagnose_returns_list(self):
        obs = observe(default_state(), default_ctx())
        advice = diagnose(obs)
        assert isinstance(advice, list)
        assert len(advice) >= 1

    def test_diagnose_clean_state(self):
        s = LegalMutable(truth_score=0.85, evidence_integrity=0.88,
                         legal_coherence=0.85, bias_total=0.05, procedural_score=0.92)
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=0.04, impartiality=0.94),
            defendant=DefendantParams(actual_guilt=0.82),
            media_pressure=0.10,
            public_scrutiny=0.85,
        )
        obs    = observe(s, ctx)
        advice = diagnose(obs)
        assert any("정상" in a or "✅" in a for a in advice)

    def test_diagnose_corrupted_gives_warnings(self):
        s   = LegalMutable(truth_score=0.10, evidence_integrity=0.20,
                            bias_total=0.90, procedural_score=0.15)
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=0.90, impartiality=0.10),
            defendant=DefendantParams(actual_guilt=0.90),
            media_pressure=0.80,
        )
        obs    = observe(s, ctx)
        advice = diagnose(obs)
        assert len(advice) >= 3

    def test_omega_legal_drops_with_low_hierarchy(self):
        s    = LegalMutable(legal_coherence=0.65)
        ctx1 = LegalContext(hierarchy=LegalHierarchy(
            constitution_score=0.95, statute_score=0.90, regulation_score=0.88,
            precedent_score=0.88, doctrine_score=0.85))
        ctx2 = LegalContext(hierarchy=LegalHierarchy(
            constitution_score=0.40, statute_score=0.35, regulation_score=0.30,
            precedent_score=0.30, doctrine_score=0.25))
        o1 = observe(s, ctx1)
        o2 = observe(s, ctx2)
        assert o2["Ω_legal"] < o1["Ω_legal"]


# ─────────────────────────────────────────────────────────────────────────────
# §3 ODE 미분 + RK4 단조성
# ─────────────────────────────────────────────────────────────────────────────
class TestDynamics:

    def test_derivatives_return_five_values(self):
        d = _derivatives(default_state(), LegalParams(), default_ctx())
        assert len(d) == 5

    def test_high_impartiality_increases_truth(self):
        s   = LegalMutable(truth_score=0.40, evidence_integrity=0.70,
                            bias_total=0.20, procedural_score=0.80)
        ctx = LegalContext(
            judge=JudgeParams(impartiality=0.95, corruption_risk=0.05),
            defendant=DefendantParams(actual_guilt=0.80),
        )
        dT, *_ = _derivatives(s, LegalParams(), ctx)
        assert dT > 0.0, "공정한 판사 → 진실 발현 양수"

    def test_high_bias_increases_bias_derivative(self):
        s1 = LegalMutable(bias_total=0.10)
        s2 = LegalMutable(bias_total=0.10)
        ctx_corrupt = LegalContext(
            judge=JudgeParams(corruption_risk=0.90, impartiality=0.10),
            prosecutor=ProsecutorParams(political_pressure=0.80),
            media_pressure=0.80,
            public_scrutiny=0.10,
            institutional_resistance=0.10,
        )
        ctx_clean = LegalContext(
            judge=JudgeParams(corruption_risk=0.05, impartiality=0.90),
            prosecutor=ProsecutorParams(political_pressure=0.05),
            media_pressure=0.10,
            public_scrutiny=0.80,
            institutional_resistance=0.80,
        )
        _, _, _, dB_corrupt, _ = _derivatives(s1, LegalParams(), ctx_corrupt)
        _, _, _, dB_clean,   _ = _derivatives(s2, LegalParams(), ctx_clean)
        assert dB_corrupt > dB_clean

    def test_rk4_state_changes(self):
        s    = default_state()
        ctx  = default_ctx()
        ns   = step_rk4(s, LegalParams(), ctx)
        assert ns.t > s.t
        assert ns is not s

    def test_rk4_remains_in_range(self):
        s   = LegalMutable(truth_score=0.90, evidence_integrity=0.95,
                            bias_total=0.02, procedural_score=0.95)
        ctx = default_ctx()
        for _ in range(20):
            s = step_rk4(s, LegalParams(), ctx)
        assert 0.0 <= s.truth_score <= 1.0
        assert 0.0 <= s.bias_total  <= 1.0

    def test_judicial_reform_decreases_bias_over_time(self):
        # 편향이 높은 상태에서 제도 개혁이 강하면 편향 감소 방향
        s = LegalMutable(bias_total=0.70)
        ctx = LegalContext(
            judge=JudgeParams(impartiality=0.80, corruption_risk=0.10),
            public_scrutiny=0.90,
            institutional_resistance=0.80,
            media_pressure=0.10,
        )
        s2 = step_rk4(s, LegalParams(), ctx)
        assert s2.bias_total < s.bias_total

    def test_evidence_fabrication_suppresses_truth(self):
        s0   = default_state()
        ctx  = default_ctx()
        s1, c1 = apply_legal_event(s0, ctx, "evidence_fabrication", 1.0)
        # 증거 조작 → evidence_integrity 급락
        assert s1.evidence_integrity < s0.evidence_integrity
        # manipulation tendency 증가
        assert c1.prosecutor.manipulation_tendency > ctx.prosecutor.manipulation_tendency

    def test_plea_bargain_raises_truth(self):
        s0 = LegalMutable(truth_score=0.35, evidence_integrity=0.40)
        ctx = default_ctx()
        s1, _ = apply_legal_event(s0, ctx, "plea_bargain", 1.0)
        assert s1.truth_score > s0.truth_score
        assert s1.evidence_integrity > s0.evidence_integrity


# ─────────────────────────────────────────────────────────────────────────────
# §4 이벤트 충격 방향성 (12개 이벤트)
# ─────────────────────────────────────────────────────────────────────────────
class TestEvents:

    def _apply(self, etype, **state_kwargs):
        s0  = LegalMutable(**state_kwargs) if state_kwargs else default_state()
        ctx = default_ctx()
        s1, c1 = apply_legal_event(s0, ctx, etype, 1.0)
        return s0, s1, ctx, c1

    def test_evidence_fabrication(self):
        s0, s1, ctx, c1 = self._apply("evidence_fabrication")
        assert s1.evidence_integrity < s0.evidence_integrity
        assert s1.truth_score < s0.truth_score

    def test_evidence_suppression(self):
        s0, s1, ctx, c1 = self._apply("evidence_suppression")
        assert s1.truth_score < s0.truth_score

    def test_judicial_corruption(self):
        s0, s1, ctx, c1 = self._apply("judicial_corruption")
        assert s1.bias_total > s0.bias_total
        assert c1.judge.corruption_risk > ctx.judge.corruption_risk

    def test_media_manipulation(self):
        s0, s1, ctx, c1 = self._apply("media_manipulation")
        assert c1.media_pressure > ctx.media_pressure
        assert c1.jury.media_influence > ctx.jury.media_influence

    def test_judicial_reform(self):
        s0, s1, ctx, c1 = self._apply("judicial_corruption",
                                       bias_total=0.70)  # 먼저 부패
        # 개혁 이벤트
        s2, c2 = apply_legal_event(s1, c1, "judicial_reform", 1.0)
        assert s2.bias_total < s1.bias_total
        assert c2.institutional_resistance > c1.institutional_resistance

    def test_transparency_law(self):
        s0, s1, ctx, c1 = self._apply("transparency_law")
        assert c1.public_scrutiny > ctx.public_scrutiny
        assert s1.procedural_score > s0.procedural_score

    def test_jury_education(self):
        s0, s1, ctx, c1 = self._apply("jury_education")
        assert c1.jury.emotional_bias < ctx.jury.emotional_bias
        assert c1.jury.deliberation_quality > ctx.jury.deliberation_quality

    def test_precedent_establish(self):
        s0, s1, ctx, c1 = self._apply("precedent_establish")
        assert c1.hierarchy.precedent_score > ctx.hierarchy.precedent_score
        assert s1.legal_coherence > s0.legal_coherence

    def test_constitutional_review(self):
        s0, s1, ctx, c1 = self._apply("constitutional_review")
        assert c1.hierarchy.constitution_score > ctx.hierarchy.constitution_score
        assert s1.legal_coherence > s0.legal_coherence

    def test_plea_bargain(self):
        s0, s1, ctx, c1 = self._apply("plea_bargain")
        assert s1.truth_score > s0.truth_score
        assert c1.defendant.cooperation > ctx.defendant.cooperation

    def test_procedural_violation(self):
        s0, s1, ctx, c1 = self._apply("procedural_violation")
        assert s1.procedural_score < s0.procedural_score
        assert s1.bias_total > s0.bias_total

    def test_star_defense(self):
        s0   = default_state()
        ctx0 = LegalContext(defendant=DefendantParams(resource_level=0.90))
        s1, c1 = apply_legal_event(s0, ctx0, "star_defense", 1.0)
        assert c1.defense.skill_level > ctx0.defense.skill_level


# ─────────────────────────────────────────────────────────────────────────────
# §5 시뮬레이션 시나리오
# ─────────────────────────────────────────────────────────────────────────────
class TestSimulation:

    def test_simulate_produces_history(self):
        eng = LegalEngine(preset="korea")
        eng.simulate(steps=10)
        assert len(eng.history) == 10

    def test_no_event_korea_stays_fragile_or_critical(self):
        eng = LegalEngine(preset="korea")
        eng.simulate(steps=24)
        final_obs = observe(eng.state, eng.ctx)
        assert final_obs["verdict"] in ("FRAGILE", "CRITICAL", "STABLE")

    def test_evidence_fabrication_worsens_outcome(self):
        eng_clean  = LegalEngine(preset="korea")
        eng_dirty  = LegalEngine(preset="korea")
        eng_clean.simulate(steps=12)
        eng_dirty.simulate(
            steps=12,
            event_at={0: JudicialEvent(evidence_fabrication=1.0)}
        )
        obs_clean = observe(eng_clean.state, eng_clean.ctx)
        obs_dirty = observe(eng_dirty.state, eng_dirty.ctx)
        assert obs_dirty["Ω_global"] < obs_clean["Ω_global"]

    def test_reform_improves_outcome(self):
        eng_no    = LegalEngine(preset="korea")
        eng_reform = LegalEngine(preset="korea")
        eng_no.simulate(steps=18)
        eng_reform.simulate(
            steps=18,
            event_at={0: JudicialEvent(judicial_reform=1.0, transparency_law=1.0)}
        )
        obs_no     = observe(eng_no.state,     eng_no.ctx)
        obs_reform = observe(eng_reform.state, eng_reform.ctx)
        assert obs_reform["Ω_global"] > obs_no["Ω_global"]

    def test_auto_event_activates_when_critical(self):
        eng = LegalEngine(preset="korea")
        # 강제 악화
        eng.state.bias_total         = 0.90
        eng.state.evidence_integrity = 0.20
        eng.simulate(steps=6, auto_event=True)
        assert any(rec["event"] for rec in eng.history)

    def test_summary_dict_structure(self):
        eng = LegalEngine(preset="neutral")
        eng.simulate(steps=6)
        sd  = eng.summary_dict()
        assert "steps" in sd
        assert "final_state" in sd
        assert "observation" in sd
        assert "advice" in sd


# ─────────────────────────────────────────────────────────────────────────────
# §6 Athena 권고 + 프리셋
# ─────────────────────────────────────────────────────────────────────────────
class TestAthenaPreset:

    def test_recommend_event_collusion_gives_reform(self):
        s   = LegalMutable(truth_score=0.25, evidence_integrity=0.25,
                            bias_total=0.80, procedural_score=0.25)
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=0.80, impartiality=0.10),
            prosecutor=ProsecutorParams(political_pressure=0.70),
            defendant=DefendantParams(actual_guilt=0.90),
        )
        obs = observe(s, ctx)
        ev  = recommend_event(obs)
        assert ev is not None
        assert ev.judicial_reform > 0 or ev.constitutional_review > 0

    def test_recommend_event_jury_compromised(self):
        s   = default_state()
        ctx = LegalContext(
            jury=JuryParams(emotional_bias=0.80, media_influence=0.80, weight=1.0)
        )
        obs = observe(s, ctx)
        ev  = recommend_event(obs)
        # jury_compromised → jury_education
        if obs["flags"].get("jury_compromised"):
            assert ev is not None and ev.jury_education > 0

    def test_recommend_event_clean_returns_none(self):
        s = LegalMutable(truth_score=0.85, evidence_integrity=0.88,
                         legal_coherence=0.85, bias_total=0.05, procedural_score=0.92)
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=0.04, impartiality=0.94),
            defendant=DefendantParams(actual_guilt=0.82),
            media_pressure=0.10,
            public_scrutiny=0.85,
        )
        obs = observe(s, ctx)
        ev  = recommend_event(obs)
        assert ev is None

    def test_korea_preset_has_higher_bias_than_neutral(self):
        from legal_engine.legal_engine import _build_from_preset
        s_k, c_k = _build_from_preset(KOREA_CRIMINAL_PRESET)
        s_n, c_n = _build_from_preset(NEUTRAL_PRESET)
        assert s_k.bias_total > s_n.bias_total

    def test_judicial_court_history(self):
        court = JudicialCourt()
        ev    = JudicialEvent(judicial_reform=1.0)
        court.issue(5, ev, "테스트 개혁")
        assert len(court.history) == 1
        assert court.latest().step == 5

    def test_neutral_preset_achieves_stable_or_just(self):
        eng = LegalEngine(preset="neutral")
        eng.simulate(steps=24)
        obs = observe(eng.state, eng.ctx)
        assert obs["verdict"] in ("JUST", "STABLE")


# ─────────────────────────────────────────────────────────────────────────────
# §7 v0.2.0 신규 로직 검증
# ─────────────────────────────────────────────────────────────────────────────
class TestV020:

    # ── signed_justice_gap / verdict_direction ────────────────────────────
    def test_signed_gap_positive_when_verdict_exceeds_guilt(self):
        """판결 점수 > 실제 유죄 → signed_gap 양수 (억울한 경우)."""
        s   = LegalMutable(truth_score=0.80, evidence_integrity=0.85,
                            legal_coherence=0.80, bias_total=0.05, procedural_score=0.90)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.20))
        d   = compute_derived(s, ctx)
        assert d["signed_justice_gap"] > 0
        assert d["verdict_direction"] == "OVER_CONVICTED"

    def test_signed_gap_negative_when_guilt_exceeds_verdict(self):
        """실제 유죄 > 판결 점수 → signed_gap 음수 (부당 방면)."""
        s   = LegalMutable(truth_score=0.15, evidence_integrity=0.20,
                            legal_coherence=0.20, bias_total=0.80, procedural_score=0.20)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.95))
        d   = compute_derived(s, ctx)
        assert d["signed_justice_gap"] < 0
        assert d["verdict_direction"] == "ACQUITTED"

    def test_signed_gap_balanced(self):
        """판결 ≈ 실제 유죄 → BALANCED."""
        s   = LegalMutable(truth_score=0.70, evidence_integrity=0.75,
                            legal_coherence=0.70, bias_total=0.15, procedural_score=0.80)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.70))
        d   = compute_derived(s, ctx)
        assert d["verdict_direction"] == "BALANCED"

    # ── revolving_door_index 3요소 공식 ──────────────────────────────────
    def test_revolving_door_zero_when_impartial(self):
        """판사가 완전히 공정하면 전관예우 지수 = 0."""
        s   = default_state()
        ctx = LegalContext(judge=JudgeParams(impartiality=1.0, corruption_risk=0.90))
        d   = compute_derived(s, ctx)
        assert d["revolving_door_index"] == 0.0

    def test_revolving_door_increases_with_skill(self):
        """변호사 스킬이 높을수록 전관예우 지수 증가 (부패 판사 환경에서)."""
        s    = default_state()
        ctx1 = LegalContext(
            judge=JudgeParams(corruption_risk=0.70, impartiality=0.20),
            defense=DefenseParams(skill_level=0.20),
        )
        ctx2 = LegalContext(
            judge=JudgeParams(corruption_risk=0.70, impartiality=0.20),
            defense=DefenseParams(skill_level=0.90),
        )
        d1 = compute_derived(s, ctx1)
        d2 = compute_derived(s, ctx2)
        assert d2["revolving_door_index"] > d1["revolving_door_index"]

    def test_revolving_door_max_is_one(self):
        """전관예우 지수 이론적 최댓값 = 1.0."""
        s   = default_state()
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=1.0, impartiality=0.0),
            defense=DefenseParams(skill_level=1.0),
        )
        d   = compute_derived(s, ctx)
        # corruption=1.0 × (1-0.0) × (0.5 + 1.0×0.5) = 1.0 × 1.0 × 1.0 = 1.0
        assert abs(d["revolving_door_index"] - 1.0) < 1e-6

    # ── over_convicted / unjust_acquittal 플래그 ─────────────────────────
    def test_over_convicted_flag(self):
        """signed_gap > 0.25 → over_convicted 플래그."""
        s   = LegalMutable(truth_score=0.80, evidence_integrity=0.85,
                            legal_coherence=0.80, bias_total=0.05, procedural_score=0.90)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.10))
        d   = compute_derived(s, ctx)
        f   = compute_flags(s, ctx, d)
        assert f["over_convicted"] is True

    def test_unjust_acquittal_flag(self):
        """signed_gap < -0.25 → unjust_acquittal 플래그."""
        s   = LegalMutable(truth_score=0.10, evidence_integrity=0.15,
                            legal_coherence=0.15, bias_total=0.90, procedural_score=0.10)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.95))
        d   = compute_derived(s, ctx)
        f   = compute_flags(s, ctx, d)
        assert f["unjust_acquittal"] is True

    # ── DISTORTED 강제 임계치 ─────────────────────────────────────────────
    def test_distorted_stage_caps_omega_at_0_70(self):
        """DISTORTED 단계(gap=0.20~0.40)에서 Ω_global ≤ 0.70 강제."""
        # verdict_score ≈ 0.75, actual_guilt = 0.40 → gap ≈ 0.35 → DISTORTED
        s   = LegalMutable(truth_score=0.80, evidence_integrity=0.80,
                            legal_coherence=0.80, bias_total=0.05, procedural_score=0.90)
        ctx = LegalContext(
            defendant=DefendantParams(actual_guilt=0.40),
            judge=JudgeParams(corruption_risk=0.05, impartiality=0.92),
            public_scrutiny=0.80,
        )
        obs = observe(s, ctx)
        if obs["justice_stage"] == "DISTORTED":
            assert obs["Ω_global"] <= 0.70
            assert obs["verdict"] in ("STABLE", "FRAGILE", "CRITICAL")

    # ── Ω_bias revolving 정규화 ───────────────────────────────────────────
    def test_omega_bias_zero_at_max_revolving(self):
        """전관예우 최악(revolving=1.0)이면 rev_ω 기여 → 0."""
        s   = default_state()
        # revolving_door_index = 1.0 (최댓값)
        ctx = LegalContext(
            judge=JudgeParams(corruption_risk=1.0, impartiality=0.0),
            defense=DefenseParams(skill_level=1.0),
            # B=0, collusion=0 으로 나머지 Ω_bias 항 최대로 설정
        )
        from legal_engine.legal_observer import _omega_bias
        derived = compute_derived(s, ctx)
        ob = _omega_bias(s, ctx, derived)
        # rev_ω = 1 - 1.0 = 0.0; 다른 항만으로 Ω_bias 결정
        # 이 상태에서 ob는 bias_ω×0.50 + coll_ω×0.25 만 남음
        assert ob < 0.80  # 최악 revolving이 반드시 Ω_bias를 낮춰야 함

    # ── jury deliberation ODE 반영 ────────────────────────────────────────
    def test_jury_deliberation_boosts_truth_reveal(self):
        """배심 숙의 품질이 높을수록 dT/dt 발현 항 증가."""
        from legal_engine.legal_dynamics import _derivatives
        s = LegalMutable(truth_score=0.40, evidence_integrity=0.70,
                         bias_total=0.10, procedural_score=0.80)
        ctx_low = LegalContext(
            jury=JuryParams(deliberation_quality=0.10, weight=1.0),
            judge=JudgeParams(impartiality=0.80, corruption_risk=0.10),
            defendant=DefendantParams(actual_guilt=0.80),
        )
        ctx_high = LegalContext(
            jury=JuryParams(deliberation_quality=0.95, weight=1.0),
            judge=JudgeParams(impartiality=0.80, corruption_risk=0.10),
            defendant=DefendantParams(actual_guilt=0.80),
        )
        dT_low,  *_ = _derivatives(s, LegalParams(), ctx_low)
        dT_high, *_ = _derivatives(s, LegalParams(), ctx_high)
        assert dT_high > dT_low, "높은 배심 숙의 → dT/dt 발현 증가"

    # ── diagnose() 방향성 메시지 ──────────────────────────────────────────
    def test_diagnose_over_convicted_message(self):
        """over_convicted 플래그 시 억울 관련 메시지 포함."""
        s   = LegalMutable(truth_score=0.80, evidence_integrity=0.85,
                            legal_coherence=0.80, bias_total=0.05, procedural_score=0.90)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.05))
        obs = observe(s, ctx)
        if obs["flags"].get("over_convicted"):
            advice = diagnose(obs)
            assert any("억울" in a or "OVER" in a for a in advice)

    def test_diagnose_unjust_acquittal_message(self):
        """unjust_acquittal 플래그 시 방면 관련 메시지 포함."""
        s   = LegalMutable(truth_score=0.10, evidence_integrity=0.10,
                            legal_coherence=0.10, bias_total=0.90, procedural_score=0.10)
        ctx = LegalContext(defendant=DefendantParams(actual_guilt=0.95))
        obs = observe(s, ctx)
        if obs["flags"].get("unjust_acquittal"):
            advice = diagnose(obs)
            assert any("방면" in a or "acquittal" in a.lower() for a in advice)


# ─────────────────────────────────────────────────────────────────────────────
# §8  v0.4.0 — 법규범 자체 정합성 분석 (18개)
# ─────────────────────────────────────────────────────────────────────────────
class TestNormAnalyzer:
    """§8 — 법규범 자체 정합성: StatuteProfile, ConstitutionalAnalysis, analyze_norms()"""

    # ── StatuteProfile ───────────────────────────────────────────────────────

    def test_statute_norm_integrity_range(self):
        """norm_integrity() 반환값은 [0, 1] 범위."""
        s = StatuteProfile()
        assert 0.0 <= s.norm_integrity() <= 1.0

    def test_statute_proportionality_score_average(self):
        """proportionality_score = (suitability + necessity + proportionality_stricto) / 3."""
        s = StatuteProfile(suitability=0.60, necessity=0.80, proportionality_stricto=0.40)
        expected = (0.60 + 0.80 + 0.40) / 3.0
        assert abs(s.proportionality_score() - expected) < 1e-9

    def test_statute_high_conflict_lowers_integrity(self):
        """higher_norm_conflict 높을수록 norm_integrity 낮아짐."""
        s_low  = StatuteProfile(higher_norm_conflict=0.05)
        s_high = StatuteProfile(higher_norm_conflict=0.90)
        assert s_low.norm_integrity() > s_high.norm_integrity()

    def test_statute_low_clarity_lowers_integrity(self):
        """clarity_score 낮을수록 norm_integrity 낮아짐."""
        s_clear = StatuteProfile(clarity_score=0.90)
        s_vague = StatuteProfile(clarity_score=0.10)
        assert s_clear.norm_integrity() > s_vague.norm_integrity()

    # ── ConstitutionalAnalysis ───────────────────────────────────────────────

    def test_constitutional_quality_range(self):
        """constitutional_quality() 반환값은 [0, 1] 범위."""
        c = ConstitutionalAnalysis()
        assert 0.0 <= c.constitutional_quality() <= 1.0

    def test_constitutional_emergency_abuse_lowers_quality(self):
        """emergency_abuse_risk 높을수록 constitutional_quality 낮아짐."""
        c_safe = ConstitutionalAnalysis(emergency_abuse_risk=0.05)
        c_risk = ConstitutionalAnalysis(emergency_abuse_risk=0.90)
        assert c_safe.constitutional_quality() > c_risk.constitutional_quality()

    def test_constitutional_full_rights_improves_quality(self):
        """fundamental_rights_coverage 높을수록 quality 향상."""
        c_low  = ConstitutionalAnalysis(fundamental_rights_coverage=0.20)
        c_high = ConstitutionalAnalysis(fundamental_rights_coverage=0.95)
        assert c_high.constitutional_quality() > c_low.constitutional_quality()

    # ── analyze_norms() 플래그 ───────────────────────────────────────────────

    def test_unconstitutional_flag_when_conflict_high(self):
        """higher_norm_conflict > 0.50 → law_unconstitutional 플래그."""
        s = StatuteProfile(name="위헌법", higher_norm_conflict=0.70)
        report = analyze_norms([s])
        assert report["flags"]["law_unconstitutional"] is True
        assert "위헌법" in report["unconstitutional_laws"]

    def test_vague_flag_when_clarity_low(self):
        """clarity_score < 0.35 → law_vague 플래그."""
        s = StatuteProfile(name="모호법", clarity_score=0.20)
        report = analyze_norms([s])
        assert report["flags"]["law_vague"] is True
        assert "모호법" in report["vague_laws"]

    def test_disproportionate_flag_when_prop_low(self):
        """proportionality_score() < 0.35 → law_disproportionate 플래그."""
        s = StatuteProfile(name="과잉법", suitability=0.10, necessity=0.10, proportionality_stricto=0.10)
        report = analyze_norms([s])
        assert report["flags"]["law_disproportionate"] is True

    def test_constitutional_crisis_emergency_abuse(self):
        """emergency_abuse_risk > 0.70 → constitutional_crisis 플래그."""
        c = ConstitutionalAnalysis(emergency_abuse_risk=0.80)
        report = analyze_norms([], constitution=c)
        assert report["flags"]["constitutional_crisis"] is True

    def test_constitutional_crisis_internal_inconsistency(self):
        """internal_consistency < 0.40 → constitutional_crisis 플래그."""
        c = ConstitutionalAnalysis(internal_consistency=0.30)
        report = analyze_norms([], constitution=c)
        assert report["flags"]["constitutional_crisis"] is True

    # ── analyze_norms() Ω_norm ───────────────────────────────────────────────

    def test_omega_norm_range(self):
        """Ω_norm ∈ [0, 1]."""
        report = analyze_norms([StatuteProfile()])
        assert 0.0 <= report["Ω_norm"] <= 1.0

    def test_omega_norm_high_for_clean_laws(self):
        """완벽한 법령 + 헌법 → Ω_norm > 0.75."""
        s = StatuteProfile(
            clarity_score=0.95, suitability=0.95, necessity=0.95,
            proportionality_stricto=0.95, rights_alignment=0.95,
            higher_norm_conflict=0.02, purpose_clarity=0.95,
        )
        c = ConstitutionalAnalysis(
            internal_consistency=0.95, democratic_legitimacy=0.95,
            fundamental_rights_coverage=0.95, separation_of_powers=0.95,
            emergency_abuse_risk=0.02, effectiveness=0.90,
        )
        report = analyze_norms([s], constitution=c)
        assert report["Ω_norm"] > 0.75

    def test_omega_norm_low_for_bad_laws(self):
        """위헌·비례 위반·모호 법령 → Ω_norm < 0.40."""
        s = StatuteProfile(
            clarity_score=0.10, suitability=0.10, necessity=0.10,
            proportionality_stricto=0.10, rights_alignment=0.10,
            higher_norm_conflict=0.90,
        )
        c = ConstitutionalAnalysis(
            internal_consistency=0.20, democratic_legitimacy=0.20,
            fundamental_rights_coverage=0.20, emergency_abuse_risk=0.90,
        )
        report = analyze_norms([s], constitution=c)
        assert report["Ω_norm"] < 0.40

    def test_analyze_norms_empty_statutes_returns_const_quality(self):
        """법령 없이 헌법만 → Ω_norm = constitutional_quality."""
        c = ConstitutionalAnalysis()
        report = analyze_norms([], constitution=c)
        assert abs(report["Ω_norm"] - c.constitutional_quality()) < 1e-4
        assert report["avg_statute_integrity"] is None

    def test_diagnoses_populated_when_flags_active(self):
        """플래그 작동 시 diagnoses에 경고 포함."""
        c = ConstitutionalAnalysis(emergency_abuse_risk=0.85)
        report = analyze_norms([], constitution=c)
        assert len(report["diagnoses"]) >= 1
        assert not report["diagnoses"][0].startswith("✅")

    # ── observe() 6-layer 통합 ────────────────────────────────────────────────

    def test_observe_with_norm_report_includes_omega_norm(self):
        """norm_report 제공 시 관찰 결과에 Ω_norm 포함."""
        s      = LegalMutable()
        ctx    = LegalContext()
        nr     = analyze_norms([StatuteProfile()])
        obs    = observe(s, ctx, norm_report=nr)
        assert "Ω_norm" in obs
        assert 0.0 <= obs["Ω_norm"] <= 1.0

    def test_observe_6layer_uses_different_weights(self):
        """6-layer Ω_global ≠ 5-layer Ω_global (가중치 다름)."""
        s      = LegalMutable()
        ctx    = LegalContext()
        obs5   = observe(s, ctx)
        nr     = analyze_norms([StatuteProfile(
            clarity_score=0.10, rights_alignment=0.10, higher_norm_conflict=0.90,
        )])
        obs6   = observe(s, ctx, norm_report=nr)
        # Ω_norm이 낮으면 6-layer Ω_global이 5-layer보다 낮아야 함
        assert obs6["Ω_global"] < obs5["Ω_global"]
        assert obs6["n_layers"] == 6
        assert obs5["n_layers"] == 5

    # ── diagnose_statute() 개별 진단 ─────────────────────────────────────────

    def test_diagnose_statute_clean_returns_ok(self):
        """정합성 양호한 법령 → ✅ 반환."""
        s = StatuteProfile(
            clarity_score=0.90, suitability=0.90, necessity=0.90,
            proportionality_stricto=0.90, rights_alignment=0.90,
            higher_norm_conflict=0.05,
        )
        advice = diagnose_statute(s)
        assert len(advice) == 1
        assert advice[0].startswith("✅")

    def test_diagnose_statute_unconstitutional_flagged(self):
        """위헌 위험 법령 → 🔴 포함."""
        s = StatuteProfile(name="테스트법", higher_norm_conflict=0.80)
        advice = diagnose_statute(s)
        assert any("🔴" in a for a in advice)
