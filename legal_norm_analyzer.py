# -*- coding: utf-8 -*-
"""
legal_norm_analyzer.py — 법규범 자체 정합성 분석  (v0.4.0)

헌법·법률의 내재적 품질을 독립 평가한다.
사법 시스템이 법을 올바르게 '적용'하는지(observer)와 별개로,
법 자체가 헌법 원칙에 부합하는지(norm)를 판단한다.

주요 컴포넌트:
    StatuteProfile        — 개별 법령/조항 내재적 정합성 프로파일
    ConstitutionalAnalysis — 헌법 자체의 민주적 정당성·내부 정합성
    analyze_norms()       — 법규범 군 종합 분석 → Ω_norm + 플래그 + 진단

분석 6차원:
    ① 명확성    — 법문의 모호성, 위임 남발, 예측 가능성
    ② 비례성    — 적합성·필요성·상당성 (3단계 비례 원칙)
    ③ 기본권 정합성 — 헌법상 기본권과의 충돌·제한 수준
    ④ 상위법 정합성 — 헌법→법률→시행령 계층별 위반 여부
    ⑤ 입법 목적 명확성 — 목적의 정당성·구체성
    ⑥ 헌법 내부 정합성 — 조항 간 충돌, 권력분립, 민주적 정당성

Ω_norm (5-layer 독립):
    avg_statute_integrity × 0.45  (법령 적용 빈도 가장 높음)
    constitutional_quality × 0.40  (모든 법령의 상위 기반)
    (1 − conflict_index)  × 0.15  (계층 일관성)

6-layer Ω_global (norm_report 제공 시):
    Ω_truth×0.25 + Ω_evidence×0.20 + Ω_legal×0.15
    + Ω_bias×0.15 + Ω_procedural×0.10 + Ω_norm×0.15
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .legal_state import _clamp


# ─── 개별 법령 프로파일 ──────────────────────────────────────────────────────────
@dataclass
class StatuteProfile:
    """
    단일 법령(또는 주요 조항)의 내재적 정합성 프로파일.

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  clarity_score (명확성 원칙)                                               │
    │    측정 ①  법령 조문 내 불확정 개념 빈도 역산                                │
    │              ('정당한 이유', '합리적 기간', '필요한 경우' 등)                 │
    │              모호어 비율 > 30% → 0.30,   < 10% → 0.80+                   │
    │    측정 ②  헌재 한정합헌·한정위헌 결정 빈도                                  │
    │              (조문 해석 범위를 한정해야 했다 = 명확성 부족)                    │
    │    측정 ③  법원 유권해석 요청 건수 역산                                       │
    │    데이터:  헌재 결정 DB, 법제처 법령해석례                                   │
    │                                                                          │
    │  suitability (적합성 — 비례 원칙 1단계)                                    │
    │    측정:   입법 목적 vs 규제 수단의 인과 타당성                               │
    │            전문가 패널(법학 교수) 평가 또는 입법영향평가 보고서                  │
    │            사회과학적 효과 연구 존재 여부 (증거기반 입법 여부)                   │
    │                                                                          │
    │  necessity (필요성 — 비례 원칙 2단계)                                       │
    │    측정:   동일 목적 달성 가능한 경한 수단 존재 여부                            │
    │            비교법: OECD 국가 중 덜 제한적 수단 채택국 비율                     │
    │            헌재 과잉금지 원칙 위반 결정 이력                                   │
    │                                                                          │
    │  proportionality_stricto (상당성 — 비례 원칙 3단계)                         │
    │    측정:   제한되는 기본권의 중요도 vs 달성 공익의 크기                         │
    │            기본권 핵심 영역 제한 여부 (핵심 침해 → 0.10~0.30)                 │
    │            헌재 '법익 균형성 위반' 인정 사례                                   │
    │                                                                          │
    │  rights_alignment (기본권 정합성)                                          │
    │    측정:   침해 기본권 목록 vs 헌법 기본권 카탈로그 매핑                        │
    │            자유권(0.40) + 평등권(0.25) + 사회권(0.20) + 절차권(0.15) 가중     │
    │            침해 기본권의 가중치 합산 역산                                      │
    │            국가인권위원회 의견서, 헌재 결정문                                   │
    │                                                                          │
    │  higher_norm_conflict (상위법 충돌 위험)                                    │
    │    측정:   위헌 심사 청구율 (청구 건수 / 시행 연도 수)                          │
    │            헌재 위헌·헌법불합치 결정 이력                                      │
    │            학설 다수설 위헌 견해 비율                                          │
    │            0.00~0.20: 정합   0.40~0.60: 충돌 의심   0.70+: 위헌 고위험       │
    │                                                                          │
    │  purpose_clarity (입법 목적 명확성)                                         │
    │    측정:   국회 심의 기록의 목적 명시 정도 (입법이유서 구체성 점수)              │
    │            법률 제명과 내용의 일치도                                          │
    │            입법 목적이 조문에 명시적으로 선언되어 있는지 여부                    │
    └──────────────────────────────────────────────────────────────────────────┘
    """
    name: str = "unnamed_statute"

    # ── 명확성 원칙 (Bestimmtheitsgrundsatz) ─────────────────────────────────
    clarity_score: float = 0.70           # [0=완전 모호, 1=완전 명확]

    # ── 비례 원칙 3단계 (Verhältnismäßigkeit) ────────────────────────────────
    suitability:             float = 0.70  # 적합성: 수단이 목적 달성에 적합
    necessity:               float = 0.70  # 필요성: 더 경한 수단 없음
    proportionality_stricto: float = 0.70  # 상당성: 공익 ↔ 기본권 균형

    # ── 기본권 정합성 ─────────────────────────────────────────────────────────
    rights_alignment: float = 0.70        # [0=기본권 심각 침해, 1=충돌 없음]

    # ── 상위법 충돌 위험 ──────────────────────────────────────────────────────
    higher_norm_conflict: float = 0.10    # [0=충돌 없음, 1=명백 위헌]

    # ── 입법 목적 명확성 ──────────────────────────────────────────────────────
    purpose_clarity: float = 0.70         # [0=목적 불명, 1=목적 명확]

    # ─────────────────────────────────────────────────────────────────────────
    def proportionality_score(self) -> float:
        """비례 원칙 3단계 통합 점수 (3요소 평균)."""
        return (self.suitability + self.necessity + self.proportionality_stricto) / 3.0

    def norm_integrity(self) -> float:
        """
        법령 내재적 정합성 종합 점수.

        가중치 설계 근거:
          비례 원칙 0.30: 헌법상 가장 핵심적 법령 통제 원리
          기본권   0.25: 법률의 존재 이유 — 기본권 실현·보호
          명확성   0.25: 법치주의의 형식적 토대 — 예측가능성
          상위법   0.15: 계층 정합성 — 위헌 법률은 무효
          목적     0.05: 해석 지침 제공 (보완적)
        """
        return _clamp(
            self.clarity_score          * 0.25
            + self.proportionality_score() * 0.30
            + self.rights_alignment     * 0.25
            + (1.0 - self.higher_norm_conflict) * 0.15
            + self.purpose_clarity      * 0.05
        )


# ─── 헌법 자체 분석 ──────────────────────────────────────────────────────────────
@dataclass
class ConstitutionalAnalysis:
    """
    헌법 자체의 내부 정합성·민주적 정당성 분석.

    개별 법령의 상위 규범으로서 헌법이 얼마나 건전한지를 평가한다.
    헌법이 내부적으로 모순되거나, 민주적 정당성이 없거나,
    기본권 보장이 부실하면 그 위에 세워진 법률 전체의 정합성이 흔들린다.

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  internal_consistency (헌법 조항 간 내부 정합성)                             │
    │    측정:   헌법 조항 간 논리적 충돌 수 (헌법학 교수 패널 분석)                  │
    │            예: 긴급명령권(제76조) vs 기본권 침해금지(제37조 2항) 긴장 관계       │
    │            헌재 조항 충돌 해석 사건 빈도                                       │
    │            0.80+: 정합   0.50~0.70: 긴장 관계   < 0.40: 심각 충돌          │
    │                                                                          │
    │  democratic_legitimacy (민주적 정당성)                                     │
    │    측정 ①  제정·개정 국민투표 찬성 비율                                       │
    │              찬성 90%+ → 0.90,  찬성 60%대 → 0.65~                        │
    │    측정 ②  헌법 개정 이후 경과 연수 (오래된 헌법 = 현세대 정당성 의문)           │
    │    측정 ③  소수 의견 보호 조항 완전성                                         │
    │    데이터:  국민투표 결과, 헌법 개정 이력                                      │
    │                                                                          │
    │  fundamental_rights_coverage (기본권 보장 범위·수준)                        │
    │    측정:   ICCPR·ICESCR 권리 목록 vs 헌법 기본권 조항 매핑                    │
    │            국제 기준 대비 보장 비율 (90%+ → 0.85+)                           │
    │            핵심 권리 (생명·신체·표현·선거) 완전 보장 여부                       │
    │    데이터:  UN 인권이사회 UPR 심의 결과                                       │
    │                                                                          │
    │  separation_of_powers (권력분립 원칙 준수도)                                 │
    │    측정 ①  입법·행정·사법 권한 명확성 (헌법 조항 명시도)                        │
    │    측정 ②  견제 메커니즘 완전성 (탄핵·헌법소원·국정조사 등 포함 여부)            │
    │    측정 ③  헌재 권한쟁의심판 인용률 역산 (인용 多 = 침범 빈번)                   │
    │    데이터:  헌재 권한쟁의심판 통계                                             │
    │                                                                          │
    │  emergency_abuse_risk (비상권한 남용 위험) — 낮을수록 좋음                    │
    │    측정 ①  계엄·긴급명령 발동 이력 (건수/연도)                                 │
    │              발동 이력 없음 → 0.05~0.15,  복수 발동 → 0.55+               │
    │    측정 ②  비상권한 발동 시 국회·헌재 견제 성공률 역산                           │
    │    측정 ③  헌법상 비상권한 발동 요건 명확성 역산 (모호할수록 ↑)                   │
    │                                                                          │
    │  effectiveness (헌법 실효성)                                               │
    │    측정 ①  헌재 위헌 결정으로 법률 무효화 연간 평균 건수                         │
    │    측정 ②  헌법소원 인용률 (현실 기본권 보호력)                                 │
    │    측정 ③  WJP Rule of Law Index 중 헌법 항목 점수                           │
    │    데이터:  헌재 연간 통계, WJP 지수                                          │
    └──────────────────────────────────────────────────────────────────────────┘
    """
    # 헌법 조항 간 내부 정합성
    internal_consistency:       float = 0.85

    # 제정·개정 절차의 민주적 정당성
    democratic_legitimacy:      float = 0.80

    # 기본권 보장 범위·수준 (국제 인권 기준 대비)
    fundamental_rights_coverage: float = 0.80

    # 권력분립 원칙 준수도
    separation_of_powers:       float = 0.80

    # 비상권한 남용 위험 [0=위험 없음, 1=매우 위험] ↑ 나쁨
    emergency_abuse_risk:        float = 0.20

    # 실효성: 헌재 인용률, 법률 무효화 비율
    effectiveness:               float = 0.75

    def constitutional_quality(self) -> float:
        """
        헌법 품질 종합 점수.

        가중치 설계 근거:
          기본권 보장  0.25: 헌법의 핵심 목적 — 기본권 보장
          권력분립    0.20: 민주주의의 구조적 토대
          내부 정합   0.20: 법치의 예측가능성 기반
          민주 정당성 0.15: 국민 주권 원리
          실효성      0.10: 선언적 조항 vs 실제 작동
          비상 남용   0.10: 민주주의 붕괴 위험 방지
        """
        return _clamp(
            self.fundamental_rights_coverage * 0.25
            + self.separation_of_powers      * 0.20
            + self.internal_consistency      * 0.20
            + self.democratic_legitimacy     * 0.15
            + self.effectiveness             * 0.10
            + (1.0 - self.emergency_abuse_risk) * 0.10
        )


# ─── 법규범 종합 분석 ────────────────────────────────────────────────────────────
def analyze_norms(
    statutes: List[StatuteProfile],
    constitution: Optional[ConstitutionalAnalysis] = None,
) -> Dict[str, Any]:
    """
    법규범 군 종합 정합성 분석.

    Args:
        statutes:      분석할 법령 목록 (빈 리스트 가능)
        constitution:  헌법 분석 객체 (None 시 기본값 사용)

    Returns dict:
        Ω_norm                  법규범 정합성 레이어 [0, 1]
        avg_statute_integrity   법령 평균 정합성 (None: 법령 미제공)
        constitutional_quality  헌법 품질 점수
        statute_conflict_index  상위법 충돌 지수 (높을수록 위험)
        statute_scores          개별 법령별 {name: score}
        weakest_statute         가장 취약한 법령 이름 (있는 경우)
        flags                   위험 플래그 4개
        unconstitutional_laws   위헌 의심 법령 목록
        vague_laws              명확성 위반 법령 목록
        disproportionate_laws   비례 원칙 위반 법령 목록
        diagnoses               플래그 기반 진단 조언

    Ω_norm 계산:
        법령 있을 때:
            avg_statute_integrity × 0.45
          + constitutional_quality × 0.40
          + (1 − conflict_index)   × 0.15

        법령 없을 때 (헌법만):
            constitutional_quality × 1.00
    """
    if constitution is None:
        constitution = ConstitutionalAnalysis()

    const_q = constitution.constitutional_quality()

    # ── 법령 없는 경우 ───────────────────────────────────────────────────────
    if not statutes:
        flags = _compute_norm_flags([], const_q, 0.0, [], [], [], constitution)
        return {
            "Ω_norm":                round(const_q, 4),
            "avg_statute_integrity": None,
            "constitutional_quality": round(const_q, 4),
            "statute_conflict_index": None,
            "statute_scores":        {},
            "weakest_statute":       None,
            "flags":                 flags,
            "unconstitutional_laws": [],
            "vague_laws":            [],
            "disproportionate_laws": [],
            "diagnoses":             _norm_diagnoses(flags, constitution),
        }

    # ── 법령 분석 ────────────────────────────────────────────────────────────
    statute_scores   = {s.name: s.norm_integrity() for s in statutes}
    avg_integrity    = sum(statute_scores.values()) / len(statutes)
    conflict_index   = sum(s.higher_norm_conflict for s in statutes) / len(statutes)

    # Ω_norm
    Ω_norm = _clamp(
        avg_integrity  * 0.45
        + const_q      * 0.40
        + (1.0 - conflict_index) * 0.15
    )

    # ── 플래그 판단 ──────────────────────────────────────────────────────────
    unconstitutional  = [s.name for s in statutes if s.higher_norm_conflict > 0.50]
    vague_laws        = [s.name for s in statutes if s.clarity_score < 0.35]
    disproportionate  = [s.name for s in statutes if s.proportionality_score() < 0.35]
    weakest           = min(statutes, key=lambda s: s.norm_integrity(), default=None)

    flags = _compute_norm_flags(
        statutes, const_q, conflict_index,
        unconstitutional, vague_laws, disproportionate, constitution,
    )

    return {
        "Ω_norm":                round(Ω_norm, 4),
        "avg_statute_integrity": round(avg_integrity, 4),
        "constitutional_quality": round(const_q, 4),
        "statute_conflict_index": round(conflict_index, 4),
        "statute_scores":        {k: round(v, 4) for k, v in statute_scores.items()},
        "weakest_statute":       weakest.name if weakest else None,
        "flags":                 flags,
        "unconstitutional_laws": unconstitutional,
        "vague_laws":            vague_laws,
        "disproportionate_laws": disproportionate,
        "diagnoses":             _norm_diagnoses(flags, constitution),
    }


def _compute_norm_flags(
    statutes:        List[StatuteProfile],
    const_q:         float,
    conflict_index:  float,
    unconstitutional: List[str],
    vague_laws:      List[str],
    disproportionate: List[str],
    constitution:    ConstitutionalAnalysis,
) -> Dict[str, bool]:
    """법규범 4개 위험 플래그."""
    return {
        # 위헌 의심: 개별 법령 상위법 충돌 위험 > 0.50
        "law_unconstitutional":  len(unconstitutional) > 0,

        # 명확성 위반: clarity_score < 0.35
        "law_vague":             len(vague_laws) > 0,

        # 비례 원칙 위반: proportionality_score() < 0.35
        "law_disproportionate":  len(disproportionate) > 0,

        # 헌법 위기: 내부 충돌 심각 OR 민주 정당성 붕괴 OR 비상권한 남용 고위험
        "constitutional_crisis": (
            constitution.internal_consistency  < 0.40
            or constitution.democratic_legitimacy < 0.40
            or constitution.emergency_abuse_risk  > 0.70
        ),
    }


def _norm_diagnoses(
    flags:        Dict[str, bool],
    constitution: ConstitutionalAnalysis,
) -> List[str]:
    """
    법규범 플래그 기반 진단 조언.

    최우선: 헌법 위기 → 개별 법령 위헌 → 비례 위반 → 명확성 위반 순서.
    """
    advice = []

    if flags.get("constitutional_crisis"):
        if constitution.emergency_abuse_risk > 0.70:
            advice.append(
                "🔴 헌법 위기 — 비상권한 남용 위험 임계 (emergency_abuse_risk > 0.70). "
                "헌법재판소 권한쟁의심판 즉시 청구 및 비상권한 요건 명확화 개헌 논의 필요"
            )
        elif constitution.internal_consistency < 0.40:
            advice.append(
                "🔴 헌법 내부 충돌 심각 — 조항 간 모순이 법적 안정성을 훼손. "
                "헌법재판소 전원합의체 통일 해석 또는 헌법 개정 절차 개시 필요"
            )
        elif constitution.democratic_legitimacy < 0.40:
            advice.append(
                "🔴 헌법 민주적 정당성 위기 — 현 헌법의 제정·개정 절차 정당성 부족. "
                "헌법 개정 논의 및 국민투표 절차 개시 권고"
            )

    if flags.get("law_unconstitutional"):
        advice.append(
            "🔴 위헌 의심 법령 존재 — higher_norm_conflict > 0.50. "
            "헌법재판소 위헌 심사 청구 및 해당 조항 적용 유보 권고"
        )

    if flags.get("law_disproportionate"):
        advice.append(
            "🔶 비례 원칙 위반 법령 존재 — 목적 달성을 위해 더 경한 수단 검토. "
            "입법 개정 또는 법원의 비례 원칙 위반 선언 필요"
        )

    if flags.get("law_vague"):
        advice.append(
            "⚠️  명확성 원칙 위반 법령 존재 — 불확정 개념 정의 조항 추가 및 "
            "법제처 유권해석 통일 필요. 한정합헌 결정 고려"
        )

    if not advice:
        advice.append("✅ 법규범 정합성 정상 — 위헌·비례 위반·명확성 위반 신호 없음")

    return advice


# ─── 개별 법령 진단 ──────────────────────────────────────────────────────────────
def diagnose_statute(s: StatuteProfile) -> List[str]:
    """
    단일 법령의 문제점 진단 조언.
    analyze_norms()의 전체 분석과 별개로 개별 법령을 빠르게 진단한다.
    """
    advice = []

    if s.higher_norm_conflict > 0.50:
        advice.append(f"🔴 [{s.name}] 위헌 위험 — conflict={s.higher_norm_conflict:.2f}. 위헌 심사 청구 권고")

    if s.proportionality_score() < 0.35:
        advice.append(
            f"🔶 [{s.name}] 비례 원칙 위반 — "
            f"적합성={s.suitability:.2f} / 필요성={s.necessity:.2f} / 상당성={s.proportionality_stricto:.2f}"
        )
    elif s.proportionality_score() < 0.55:
        advice.append(f"⚠️  [{s.name}] 비례 원칙 주의 — 경한 수단 검토 권고")

    if s.clarity_score < 0.35:
        advice.append(f"🔴 [{s.name}] 명확성 원칙 심각 위반 — clarity={s.clarity_score:.2f}. 조문 재작성 필요")
    elif s.clarity_score < 0.55:
        advice.append(f"⚠️  [{s.name}] 명확성 주의 — 불확정 개념 범위 명시 필요")

    if s.rights_alignment < 0.35:
        advice.append(f"🔴 [{s.name}] 기본권 침해 심각 — rights_alignment={s.rights_alignment:.2f}")
    elif s.rights_alignment < 0.55:
        advice.append(f"⚠️  [{s.name}] 기본권 제한 주의 — 헌법 제37조 2항 비례 검토")

    if not advice:
        advice.append(f"✅ [{s.name}] 정합성 양호 (score={s.norm_integrity():.3f})")

    return advice
