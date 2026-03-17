# -*- coding: utf-8 -*-
"""
legal_engine.py — 법정 동역학 시뮬레이션 엔진

LegalEngine:
    preset    → 사건 초기 조건 (한국 형사 / 중립)
    simulate  → RK4 스텝 반복 (외부 이벤트 주입 or Athena 자동 권고)
    report    → 콘솔 결과 출력
    summary_dict → 최종 상태 dict

프리셋:
    "korea"   — 한국 형사 사법 시스템 (전관예우·검찰 권력 반영)
    "neutral" — 편향 최소, 완전 배심제 가정

사용 예:
    engine = LegalEngine(preset="korea")
    engine.simulate(steps=24)
    engine.report()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .legal_state import (
    LegalMutable, LegalParams, LegalContext,
    JudgeParams, ProsecutorParams, DefenseParams,
    JuryParams, DefendantParams, LegalHierarchy,
    to_snapshot,
)
from .legal_dynamics import step_rk4, apply_legal_event
from .legal_observer import observe, diagnose
from .pharaoh_decree_legal import JudicialEvent, JudicialCourt, recommend_event


# ─── 프리셋 ────────────────────────────────────────────────────────────────────
KOREA_CRIMINAL_PRESET: Dict[str, Any] = {
    # 초기 상태
    "truth_score":        0.55,
    "evidence_integrity": 0.65,
    "legal_coherence":    0.65,
    "bias_total":         0.45,  # 전관예우·검찰 권력 반영
    "procedural_score":   0.70,

    # 판사
    "judge_impartiality":    0.65,
    "judge_experience":      0.75,
    "judge_corruption_risk": 0.35,  # 전관예우 위험 높음

    # 검사
    "prosecutor_evidence_quality": 0.70,
    "prosecutor_manipulation":     0.30,
    "prosecutor_political_pressure": 0.45,  # 검찰 권력·정치 압력

    # 변호사
    "defense_skill":    0.55,
    "defense_loophole": 0.35,

    # 배심원 (국민참여재판 — 비중 낮음)
    "jury_emotional_bias":      0.35,
    "jury_media_influence":     0.50,  # 높은 미디어 영향
    "jury_deliberation_quality": 0.55,
    "jury_weight":              0.15,

    # 피고인
    "actual_guilt":   0.80,
    "cooperation":    0.40,
    "resource_level": 0.50,

    # 법률 계층
    "constitution_score": 0.85,
    "statute_score":      0.80,
    "regulation_score":   0.72,
    "precedent_score":    0.72,
    "doctrine_score":     0.68,

    # 외부 환경
    "media_pressure":           0.55,
    "political_interference":   0.40,
    "public_scrutiny":          0.45,
    "institutional_resistance": 0.40,
}

NEUTRAL_PRESET: Dict[str, Any] = {
    "truth_score":        0.60,
    "evidence_integrity": 0.72,
    "legal_coherence":    0.72,
    "bias_total":         0.20,
    "procedural_score":   0.82,

    "judge_impartiality":    0.82,
    "judge_experience":      0.75,
    "judge_corruption_risk": 0.10,

    "prosecutor_evidence_quality":    0.75,
    "prosecutor_manipulation":        0.10,
    "prosecutor_political_pressure":  0.15,

    "defense_skill":    0.65,
    "defense_loophole": 0.25,

    "jury_emotional_bias":      0.20,
    "jury_media_influence":     0.20,
    "jury_deliberation_quality": 0.70,
    "jury_weight":              1.00,  # 완전 배심제

    "actual_guilt":   0.75,
    "cooperation":    0.55,
    "resource_level": 0.50,

    "constitution_score": 0.92,
    "statute_score":      0.85,
    "regulation_score":   0.80,
    "precedent_score":    0.80,
    "doctrine_score":     0.75,

    "media_pressure":           0.20,
    "political_interference":   0.10,
    "public_scrutiny":          0.72,
    "institutional_resistance": 0.72,
}

PRESETS: Dict[str, Dict[str, Any]] = {
    "korea":   KOREA_CRIMINAL_PRESET,
    "neutral": NEUTRAL_PRESET,
}


# ─── 프리셋 → 상태 + 컨텍스트 변환 ──────────────────────────────────────────
def _build_from_preset(preset: Dict[str, Any]):
    state = LegalMutable(
        truth_score        = preset["truth_score"],
        evidence_integrity = preset["evidence_integrity"],
        legal_coherence    = preset["legal_coherence"],
        bias_total         = preset["bias_total"],
        procedural_score   = preset["procedural_score"],
    )
    ctx = LegalContext(
        judge=JudgeParams(
            impartiality    = preset["judge_impartiality"],
            experience      = preset["judge_experience"],
            corruption_risk = preset["judge_corruption_risk"],
        ),
        prosecutor=ProsecutorParams(
            evidence_quality      = preset["prosecutor_evidence_quality"],
            manipulation_tendency = preset["prosecutor_manipulation"],
            political_pressure    = preset["prosecutor_political_pressure"],
        ),
        defense=DefenseParams(
            skill_level           = preset["defense_skill"],
            loophole_exploitation = preset["defense_loophole"],
        ),
        jury=JuryParams(
            emotional_bias      = preset["jury_emotional_bias"],
            media_influence     = preset["jury_media_influence"],
            deliberation_quality = preset["jury_deliberation_quality"],
            weight              = preset["jury_weight"],
        ),
        defendant=DefendantParams(
            actual_guilt   = preset["actual_guilt"],
            cooperation    = preset["cooperation"],
            resource_level = preset["resource_level"],
        ),
        hierarchy=LegalHierarchy(
            constitution_score = preset["constitution_score"],
            statute_score      = preset["statute_score"],
            regulation_score   = preset["regulation_score"],
            precedent_score    = preset["precedent_score"],
            doctrine_score     = preset["doctrine_score"],
        ),
        media_pressure           = preset["media_pressure"],
        political_interference   = preset["political_interference"],
        public_scrutiny          = preset["public_scrutiny"],
        institutional_resistance = preset["institutional_resistance"],
    )
    return state, ctx


# ─── 엔진 ──────────────────────────────────────────────────────────────────────
class LegalEngine:
    """
    법정 동역학 시뮬레이션 엔진.

    steps  = 심급 or 월 단위 타임스텝
    events = {step: JudicialEvent} 형식으로 외부 이벤트 주입
    """

    def __init__(
        self,
        preset: str = "korea",
        params: Optional[LegalParams] = None,
    ) -> None:
        preset_dict        = PRESETS.get(preset, KOREA_CRIMINAL_PRESET)
        self.state, self.ctx = _build_from_preset(preset_dict)
        self.params         = params or LegalParams()
        self.court          = JudicialCourt()
        self.history: List[Dict[str, Any]] = []

    # ── 시뮬레이션 ──────────────────────────────────────────────────────────
    def simulate(
        self,
        steps: int = 24,
        event_at: Optional[Dict[int, JudicialEvent]] = None,
        auto_event: bool = False,
    ) -> None:
        """
        steps 단위 시뮬레이션.

        event_at   : {step(0-based): JudicialEvent} — 외부 이벤트 직접 지정
        auto_event : True 시 Athena 자동 권고 이벤트 발동
        """
        event_at = event_at or {}

        for step in range(steps):
            # 이벤트 결정
            ev = event_at.get(step)
            if ev is None and auto_event:
                obs_now = observe(self.state, self.ctx)
                ev = recommend_event(obs_now)
                if ev:
                    self.court.issue(step, ev, "Athena 자동 권고")

            # 이벤트 충격 적용
            if ev is not None:
                for etype, mag in vars(ev).items():
                    if mag > 0:
                        self.state, self.ctx = apply_legal_event(
                            self.state, self.ctx, etype, mag
                        )

            # RK4 적분
            self.state = step_rk4(self.state, self.params, self.ctx)

            # 기록
            obs = observe(self.state, self.ctx)
            self.history.append({
                "step":          step + 1,
                "t":             self.state.t,
                "T":             round(self.state.truth_score,        3),
                "E":             round(self.state.evidence_integrity, 3),
                "L":             round(self.state.legal_coherence,    3),
                "B":             round(self.state.bias_total,         3),
                "P":             round(self.state.procedural_score,   3),
                "verdict_score": obs["verdict_score"],
                "justice_gap":   obs["justice_gap"],
                "justice_stage": obs["justice_stage"],
                "Ω":             obs["Ω_global"],
                "verdict_Ω":     obs["verdict"],
                "event":         ev is not None,
            })

    # ── 리포트 ──────────────────────────────────────────────────────────────
    def report(self, every: int = 4) -> None:
        """시뮬레이션 결과 콘솔 출력."""
        print(f"\n{'=' * 76}")
        print("  LEGAL ENGINE — 법정 동역학 시뮬레이션 리포트")
        print(f"{'=' * 76}")
        print(
            f"  {'Stp':>3}  {'T':>5}  {'E':>5}  {'L':>5}  {'B':>5}  {'P':>5}  "
            f"{'Verdict':>7}  {'Gap':>5}  {'Ω':>6}  {'Status':>10}"
        )
        print(f"  {'-' * 74}")
        for rec in self.history:
            if rec["step"] % every == 0 or rec["event"]:
                ev_mark = " ◀ EVENT" if rec["event"] else ""
                print(
                    f"  {rec['step']:>3}  "
                    f"{rec['T']:>5.3f}  {rec['E']:>5.3f}  {rec['L']:>5.3f}  "
                    f"{rec['B']:>5.3f}  {rec['P']:>5.3f}  "
                    f"{rec['verdict_score']:>7.3f}  {rec['justice_gap']:>5.3f}  "
                    f"{rec['Ω']:>6.3f}  {rec['verdict_Ω']:>10}{ev_mark}"
                )

        # 최종 진단
        final_obs = observe(self.state, self.ctx)
        advice    = diagnose(final_obs)
        print(f"\n{'─' * 76}")
        print("  최종 진단 (Pharaoh Advisory):")
        for a in advice:
            print(f"    {a}")
        print(f"{'=' * 76}\n")

    # ── 요약 ────────────────────────────────────────────────────────────────
    def summary_dict(self) -> Dict[str, Any]:
        """최종 상태 요약 dict."""
        obs = observe(self.state, self.ctx)
        return {
            "steps": len(self.history),
            "final_state": {
                "truth_score":        self.state.truth_score,
                "evidence_integrity": self.state.evidence_integrity,
                "legal_coherence":    self.state.legal_coherence,
                "bias_total":         self.state.bias_total,
                "procedural_score":   self.state.procedural_score,
            },
            "observation": obs,
            "advice":      diagnose(obs),
        }


# ─── 직접 실행 샘플 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("▶ 시나리오 A: 이벤트 없음 (한국 형사, 24 스텝)")
    eng_a = LegalEngine(preset="korea")
    eng_a.simulate(steps=24)
    eng_a.report()

    print("▶ 시나리오 B: 증거 조작(stp3) → 사법 개혁(stp12) → 위헌 심사(stp18)")
    events_b = {
        2:  JudicialEvent(evidence_fabrication=1.0),
        11: JudicialEvent(judicial_reform=1.0, transparency_law=0.8),
        17: JudicialEvent(constitutional_review=1.0, precedent_establish=0.5),
    }
    eng_b = LegalEngine(preset="korea")
    eng_b.simulate(steps=24, event_at=events_b)
    eng_b.report()
