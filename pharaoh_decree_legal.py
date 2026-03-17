# -*- coding: utf-8 -*-
"""
pharaoh_decree_legal.py — 사법 이벤트 12종 + Athena 자동 권고

JudicialEvent: 이벤트 magnitude 필드 (12개)
JudicialCourt: 이벤트 발동 + 히스토리 기록
recommend_event(): Athena 자동 권고 (우선순위 규칙 트리)

Athena는 권고만 한다. 최종 발동은 파라오(인간) 승인 필요.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class JudicialEvent:
    """
    사법 이벤트 칙령.
    각 필드 = magnitude [0, 1] (0이면 발동 안 함).
    """
    evidence_fabrication:   float = 0.0  # 증거 조작 (부패 충격)
    evidence_suppression:   float = 0.0  # 증거 은폐
    judicial_corruption:    float = 0.0  # 판사 부패/매수
    media_manipulation:     float = 0.0  # 여론 조작
    judicial_reform:        float = 0.0  # 사법 개혁
    transparency_law:       float = 0.0  # 수사 투명성 법제화
    jury_education:         float = 0.0  # 배심원 교육 강화
    precedent_establish:    float = 0.0  # 새 판례 확립
    constitutional_review:  float = 0.0  # 위헌 심사 청구
    plea_bargain:           float = 0.0  # 플리바게닝
    procedural_violation:   float = 0.0  # 절차 위반
    star_defense:           float = 0.0  # 스타 변호사 투입 (재력 비례)


@dataclass
class JudicialEventRecord:
    step:  int
    event: JudicialEvent
    desc:  str


class JudicialCourt:
    """이벤트 발동 + 히스토리 기록."""

    def __init__(self) -> None:
        self.history: List[JudicialEventRecord] = []

    def issue(self, step: int, event: JudicialEvent, desc: str = "") -> None:
        self.history.append(JudicialEventRecord(step=step, event=event, desc=desc))

    def latest(self) -> Optional[JudicialEventRecord]:
        return self.history[-1] if self.history else None


# ─── Athena 자동 권고 ─────────────────────────────────────────────────────────
def recommend_event(observation: Dict[str, Any]) -> Optional[JudicialEvent]:
    """
    Athena 자동 권고 — 우선순위 규칙 트리.
    첫 매칭 조건에서 반환.

    우선순위:
    1. evidence_tampered + bias_critical   → 사법 개혁 + 투명성
    2. collusion_suspected                 → 사법 개혁 + 위헌 심사
    3. constitutional_breach               → 위헌 심사 + 판례 확립
    4. revolving_door_active               → 투명성 + 사법 개혁
    5. truth_suppressed                    → 플리바게닝 + 투명성
    6. jury_compromised                    → 배심원 교육
    7. legal_incoherent                    → 판례 확립 + 위헌 심사
    8. procedural_violation                → 투명성 + 사법 개혁 (약)
    """
    flags = observation["flags"]

    # 1순위: 증거 조작 + 심각 편향
    if flags.get("evidence_tampered") and flags.get("bias_critical"):
        return JudicialEvent(judicial_reform=1.0, transparency_law=1.0)

    # 2순위: 검-판 유착
    if flags.get("collusion_suspected"):
        return JudicialEvent(judicial_reform=1.0, constitutional_review=0.5)

    # 3순위: 헌법 위반
    if flags.get("constitutional_breach"):
        return JudicialEvent(constitutional_review=1.0, precedent_establish=0.5)

    # 4순위: 전관예우
    if flags.get("revolving_door_active"):
        return JudicialEvent(transparency_law=1.0, judicial_reform=0.5)

    # 5순위: 진실 억압
    if flags.get("truth_suppressed"):
        return JudicialEvent(plea_bargain=1.0, transparency_law=0.7)

    # 6순위: 배심원 오염
    if flags.get("jury_compromised"):
        return JudicialEvent(jury_education=1.0)

    # 7순위: 법리 불일치
    if flags.get("legal_incoherent"):
        return JudicialEvent(precedent_establish=1.0, constitutional_review=0.3)

    # 8순위: 절차 위반
    if flags.get("procedural_violation"):
        return JudicialEvent(transparency_law=0.5, judicial_reform=0.3)

    return None  # 개입 불필요
