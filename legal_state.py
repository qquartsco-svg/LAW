# -*- coding: utf-8 -*-
"""
legal_state.py — 법정 동역학 상태 변수 정의  (v0.2.0)

RK4 적분 대상 (LegalMutable):
    truth_score       T — 진실이 법정에서 드러난 정도
    evidence_integrity E — 증거 신뢰성
    legal_coherence   L — 법리 정합성 (판례·헌법 일치)
    bias_total        B — 편향 총합 (높을수록 위험: 전관예우+감정+정치)
    procedural_score  P — 절차적 정당성

핵심 통찰:
    숨겨진 진실 ctx.defendant.actual_guilt 와 판결 verdict_score 의 괴리
    = justice_gap = 사법 왜곡의 정도.

    signed_justice_gap = verdict_score − actual_guilt
        양수(+): 실제보다 높은 유죄 판결 → 억울한 경우 (OVER_CONVICTED)
        음수(−): 실제보다 낮은 유죄 판결 → 부당 방면 (ACQUITTED)

    revolving_door_index = corruption × (1 − impartiality) × (0.5 + skill × 0.5)
        판사 부패 × 공정성 결여 × 변호사 연계 역량 — 전관예우의 3요소
        이론적 최댓값: 1.0 × 1.0 × 1.0 = 1.0
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
    """
    판사 파라미터.

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  impartiality (공정성)                                                    │
    │    프록시 ①  검찰 구형 수용률 역산                                            │
    │              구형의 80% 이상을 그대로 선고 → impartiality ≈ 0.50~0.60       │
    │              구형의 60% 미만으로 재량 발휘  → impartiality ≈ 0.75~0.85       │
    │    프록시 ②  동일 법원 내 양형 편차                                           │
    │              동일 죄종·죄질에서 판사 간 형량 표준편차 → 편차 클수록 낮게 설정    │
    │    프록시 ③  기피신청 인용률                                                  │
    │              인용 0건 / 전체 재판 → 0.80+   인용 다수 → 0.50~             │
    │    데이터:   양형위원회 "양형기준 이탈 비율" 보고서, 코트넷 판결문 통계           │
    │                                                                          │
    │  experience (법률 경험·역량)                                               │
    │    프록시 ①  사법연수원/법학전문대학원 졸업 후 경력 연수                        │
    │              5년 미만 → 0.50,  10년 → 0.65,  20년+ → 0.80               │
    │    프록시 ②  고등법원 이상 재직 경력 여부 (형사합의부 ≥ 0.70)                  │
    │    데이터:   법원 공개 인사기록, 법조인 검색 서비스                             │
    │                                                                          │
    │  corruption_risk (부패·전관예우 취약도)                                     │
    │    프록시 ①  퇴직 후 법무법인 이직까지의 기간                                  │
    │              6개월 내 전관 법무법인 이직 → 0.55~0.70                        │
    │              2년 이상 유예 준수 → 0.10~0.25                               │
    │    프록시 ②  현직 판사와 동기·선후배 관계 변호사가 선임된 사건 비율              │
    │              동기 변호사 사건 비율 20%+ → 0.50+                            │
    │    프록시 ③  청탁금지법·공직자윤리법 위반 신고 건수 (법원 내)                   │
    │    데이터:   법원공직자윤리위원회 공개 자료, 언론 기사 수집·점수화              │
    └──────────────────────────────────────────────────────────────────────────┘
    """
    impartiality:    float = 0.70  # 공정성 [0=완전 편향, 1=완전 공정]
    experience:      float = 0.70  # 법률 경험·역량
    corruption_risk: float = 0.20  # 부패/전관예우 위험도


@dataclass
class ProsecutorParams:
    """
    검사 파라미터.

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  evidence_quality (증거 수집 품질)                                         │
    │    점수표 방식 (아래 §증거 신뢰성 점수표 참고)                               │
    │    DNA·CCTV·디지털 포렌식 기반 → 0.75~0.90                               │
    │    목격자 진술 위주, 물증 부족   → 0.40~0.60                               │
    │    데이터:   공소장 증거 목록, 1심 증거조사 결과                               │
    │                                                                          │
    │  manipulation_tendency (증거 조작 경향)                                    │
    │    프록시 ①  수사 과정에서 영장 기각율 (기각 多 → 위법 수사 의심)              │
    │              기각율 30%+ → manipulation ≈ 0.40~0.60                      │
    │    프록시 ②  공소장 변경 빈도 (변경 多 → 초기 증거 부실)                      │
    │    프록시 ③  항소심 무죄 환송율 (무죄 환송 多 → 1심 증거 왜곡 가능성)         │
    │    데이터:   영장발부 통계(대법원 사법연감), 공판기록                          │
    │                                                                          │
    │  political_pressure (상부·정치 압력)                                       │
    │    프록시 ①  정권 교체 이후 수사 기소 패턴 역전 빈도                          │
    │              고위직·여당 사건 불기소율 ↑ → 0.45~0.65                        │
    │    프록시 ②  특별수사팀 해산·수사 중단 사례 빈도                              │
    │    프록시 ③  수사검사 좌천·불이익 인사 사례 (내부고발 자료)                    │
    │    데이터:   국감 자료, 법무부 공개 통계, 언론·학술 연구                       │
    └──────────────────────────────────────────────────────────────────────────┘
    """
    evidence_quality:      float = 0.70  # 증거 수집 품질
    manipulation_tendency: float = 0.20  # 증거 조작 경향
    political_pressure:    float = 0.30  # 상부·정치 압력


@dataclass
class DefenseParams:
    """
    변호사(피고측) 파라미터.

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  skill_level (법률 기술·전관예우 연계 역량)                                  │
    │    프록시 ①  전직 판사·검사 경력 연수                                        │
    │              전관 10년+ 법무법인  → skill ≈ 0.75~0.90                     │
    │              신진 변호사          → skill ≈ 0.35~0.55                     │
    │    프록시 ②  유사 사건 무죄·감형 성공률 (최근 5년)                           │
    │              무죄율 30%+ → skill ≈ 0.70+                                 │
    │    프록시 ③  수임료 분위 (시장 평가 프록시)                                   │
    │              상위 10% 수임료 → skill ≈ 0.70~0.85                         │
    │    데이터:   변호사협회 등록 경력, 판결문 대리인 분석, 수임 공개 자료           │
    │                                                                          │
    │  loophole_exploitation (법의 허점 활용도)                                   │
    │    프록시 ①  증거능력 배제 신청 성공 빈도 (독수독과 원칙 적용)                  │
    │    프록시 ②  절차적 하자 기피신청·소송중지 신청 빈도                           │
    │    프록시 ③  법령 위헌 소원 또는 위헌 심사 신청 빈도                           │
    │    데이터:   공판 기록, 헌법재판소 사건 접수 통계                              │
    └──────────────────────────────────────────────────────────────────────────┘
    """
    skill_level:           float = 0.50  # 법률 기술·경험 (전관예우 연계 역량 포함)
    loophole_exploitation: float = 0.30  # 법의 허점 활용도
    unethical_tendency:    float = 0.10  # 비윤리적 전략 경향


@dataclass
class JuryParams:
    """
    배심원 파라미터 (배심제 미적용 시 weight=0).

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  emotional_bias (감정적 편향)                                              │
    │    프록시 ①  피해자 진술의 감정 강도 — 법정 녹취 감성분석 (NLP)              │
    │    프록시 ②  사건 유형: 아동 피해·성범죄 → 높음(0.55+), 경제사범 → 낮음      │
    │    프록시 ③  배심원 선발 시 사건 사전 인지도 설문 결과                         │
    │    데이터:   배심원 선발 기록, 사건 유형 코딩                                  │
    │                                                                          │
    │  media_influence (미디어·여론 영향도)                                       │
    │    프록시 ①  배심원 선정 전 해당 사건 언론 보도량 (기사 건수 × 영향력 가중)     │
    │              기사 100건+ / 1개월 → media_influence ≈ 0.60+               │
    │    프록시 ②  SNS 트렌드 노출도 (트위터·유튜브 조회수 기준 정규화)              │
    │    데이터:   빅카인즈 기사 검색량, 네이버 트렌드 지수                          │
    │                                                                          │
    │  deliberation_quality (숙의 품질 — 진실 발현 보조)                          │
    │    프록시 ①  배심원 숙의 시간 (시간 ∝ 품질)                                  │
    │              2시간 미만 → 0.40,  8시간+ → 0.75+                          │
    │    프록시 ②  평결 만장일치 여부 및 재숙의 횟수                                │
    │    프록시 ③  배심원 교육 이수 시간                                           │
    │                                                                          │
    │  weight (판결 반영 비중)                                                   │
    │    고정값 — 사법 제도 설계에 의해 결정됨                                      │
    │    한국 국민참여재판: 0.10~0.20 (권고적 효력)                               │
    │    미국·영국 완전 배심제: 1.00                                              │
    └──────────────────────────────────────────────────────────────────────────┘
    """
    emotional_bias:      float = 0.30  # 감정적 편향
    media_influence:     float = 0.30  # 미디어/여론 영향도
    deliberation_quality: float = 0.60  # 숙의 품질 — 높을수록 진실 발현 보조
    weight:              float = 0.0   # 배심원 판결 반영 비중 (한국=0.15, 미국=1.0)


@dataclass
class DefendantParams:
    """
    피고인/피의자 파라미터.

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  actual_guilt (실제 유죄 — 숨겨진 진실)                                     │
    │    ※ 이 값은 시뮬레이션이 유일하게 알고 있는 "지면 아래 진실"이다.             │
    │    실전 추정 방법 ①  재심 역추산                                             │
    │      재심 무죄 판결 → actual_guilt ≈ 0.10~0.20으로 역산                    │
    │      재심 유죄 확정 → actual_guilt ≈ 0.80~0.90으로 역산                    │
    │    실전 추정 방법 ②  물증 비율 점수화                                        │
    │      DNA·CCTV·디지털 포렌식 직접 증거 존재 → 0.75~0.95                    │
    │      목격자 2인+ + 알리바이 부재                → 0.55~0.70               │
    │      목격자 1인, 정황 증거만                    → 0.25~0.45               │
    │    실전 추정 방법 ③  진술 일관성 분석                                        │
    │      피고인·피해자 진술 일관성 점수(0~1) → actual_guilt에 대한 사전 확률       │
    │    데이터:   재심 판결문, 수사 기록 증거 목록, 전문가 판단                      │
    │                                                                          │
    │  cooperation (수사·재판 협조도)                                             │
    │    프록시 ①  자백 여부 (완전 자백 → 0.80+, 부인 → 0.20~)                   │
    │    프록시 ②  증거 제출·참고인 협조 요청 응낙 빈도                             │
    │    프록시 ③  플리바게닝 수용 여부                                            │
    │                                                                          │
    │  resource_level (재력)                                                    │
    │    프록시 ①  선임 변호인 시간당 수임료 분위 (상위 10% → 0.80+)               │
    │    프록시 ②  변호인단 구성 규모 (3인+ → 0.70+)                              │
    │    데이터:   선임계 공개 정보, 법원 수임료 신고자료                            │
    └──────────────────────────────────────────────────────────────────────────┘
    """
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

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  파라미터 수치화 방법론                                                      │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  constitution_score (헌법 적합성)                                          │
    │    프록시 ①  헌법재판소 위헌·헌법불합치 결정 비율                             │
    │              최근 5년 위헌 결정 10건+ → 0.70~,  3건 미만 → 0.90+          │
    │    데이터:   헌법재판소 결정문 통계                                          │
    │                                                                          │
    │  statute_score (법률 적합성)                                               │
    │    프록시 ①  법률 개정·폐지 빈도 (잦은 개정 = 불안정)                         │
    │    프록시 ②  국회 법률 충돌 건수 (상위 법과의 충돌 인정 건수)                  │
    │    데이터:   국가법령정보센터 개정 이력                                       │
    │                                                                          │
    │  regulation_score (시행령 적합성)                                          │
    │    프록시 ①  행정심판·행정소송 인용율 (시행령 위법 인정 빈도)                  │
    │    데이터:   행정심판위원회 연간 통계                                         │
    │                                                                          │
    │  precedent_score (판례 정합성)                                             │
    │    프록시 ①  대법원 파기환송율 (파기 多 = 하급심 판례 불일치)                  │
    │              파기환송율 20%+ → 0.60~,  5% 미만 → 0.85+                  │
    │    데이터:   대법원 사법연감 "사건처리 현황"                                  │
    │                                                                          │
    │  doctrine_score (법리 해석 적합성)                                         │
    │    프록시 ①  학설 대립 상황 (주류·소수 학설 분열도)                           │
    │    프록시 ②  판례 변경 빈도 (대법원 전원합의체 파기 건수)                      │
    │    데이터:   법학 학술지 인용 분석, 대법원 전원합의체 결정 목록                │
    └──────────────────────────────────────────────────────────────────────────┘
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

# ── 증거 신뢰성(E) 초기값 점수표 ──────────────────────────────────────────────
# evidence_integrity 초기값을 산정할 때 아래 점수표로 합산 후 clamp(0, 1) 적용:
#
#   증거 종류                   가중치    조건
#   ─────────────────────────────────────────
#   DNA / 디지털 포렌식          +0.30    1건 이상 존재
#   CCTV 영상 (직접 증거)        +0.25    피고인 특정 가능
#   목격자 진술 (2인 이상)        +0.20    진술 일관성 70%+
#   목격자 진술 (1인)            +0.10
#   피해자 진술 (일관성 80%+)    +0.15
#   물증 (흉기·물품 등)          +0.15    현장 연계 확인
#   정황 증거                   +0.08    복수 경로 확인
#   ─────────────────────────────────────────
#   영장 하자 (위법 수집)        −0.20    법원 인정 기준
#   체인오브커스터디 단절        −0.15    증거 경로 불명
#   감정서 신뢰성 문제           −0.10    전문가 의견 대립
#   공동피의자 진술 의존도 높음  −0.08    단독 진술 의존
#
#   예시: DNA(+0.30) + CCTV(+0.25) + 목격자1인(+0.10) = 0.65  → E_0 = 0.65
#   예시: 목격자1인(+0.10) + 정황(+0.08) + 영장하자(−0.20)  = −0.02 → E_0 = 0.10

@dataclass
class LegalMutable:
    """
    RK4 적분 대상 상태 변수 (5개).

    초기값 설정 지침:
        truth_score (T):         수사 단계 진실 발현 정도
            - 수사 기간 중 피의자 자백 + 물증 확보  → 0.60~0.75
            - 부인, 물증 미확보                   → 0.35~0.50
            - 수사 초기 단계                      → 0.30~0.45

        evidence_integrity (E):  §위 점수표 참조
            - 강력한 직접 증거 복수 확보            → 0.70~0.90
            - 정황 위주, 직접 증거 부족             → 0.35~0.55

        legal_coherence (L):     관련 법령의 해석 일관성
            - 대법원 판례 명확히 확립된 사안         → 0.75~0.85
            - 신규 법령, 해석 대립 상황              → 0.45~0.60

        bias_total (B):          전관예우 + 정치 압력 + 감정 편향 합산
            - NEUTRAL 프리셋: 0.20  /  KOREA 프리셋: 0.45

        procedural_score (P):    수사~기소 절차 정당성
            - 모든 영장 적법, 변호인 접견 보장        → 0.80~0.90
            - 영장 기각 후 재신청, 변호인 접견 제한    → 0.45~0.60
    """
    t: float = 0.0

    truth_score:        float = 0.50  # T: 진실 발현도   [0, 1]
    evidence_integrity: float = 0.70  # E: 증거 신뢰성   [0, 1]  ← 위 점수표 참조
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
    """
    사건 컨텍스트 — 참여자 파라미터 + 법률 계층 + 외부 환경.

    ── 외부 환경 수치화 방법론 ─────────────────────────────────────────────────────

    media_pressure (언론 압박 강도):
        프록시 ①  재판 시작 전 1개월 기사량 (빅카인즈 기준 정규화)
                   기사 200건+ → 0.70+,  50건 미만 → 0.20~
        프록시 ②  포털 실시간 검색 노출 횟수, 유튜브 관련 영상 조회수
        프록시 ③  사설·오피니언 논조 분석 (유죄 단정 비율)
        데이터:   빅카인즈, 네이버 뉴스 검색량, 구글 트렌드

    political_interference (정치 개입 강도):
        프록시 ①  피고인이 현직 공직자·정치인인 경우 → 0.50+
        프록시 ②  정권 교체 이후 수사 개시·종결 패턴 변화 (역사적 빈도)
        프록시 ③  청와대·법무부 장관 공개 발언 빈도 (해당 사건 언급)
        데이터:   국감 자료, 언론 분석, 수사 개시·기소 타임라인

    public_scrutiny (공개 감시 강도):
        프록시 ①  시민단체·법학 교수 의견서 제출 빈도
        프록시 ②  공판 방청 신청자 수, 재판 중계 요청 여부
        프록시 ③  국제 인권단체(앰네스티·HRW) 모니터링 여부 → 0.70+
        데이터:   법원 방청 기록, 시민단체 성명서

    institutional_resistance (제도적 부패 저항력):
        프록시 ①  사법부 내 내부 감찰 기구 활성도 (연간 처분 건수)
        프록시 ②  법관윤리위원회·검사윤리위원회 운영 실적
        프록시 ③  내부고발자 보호 실적 (보복 인사 발생율 역산)
        0.0~0.30: 제도 저항력 형식적 — 부패 압력이 구조적으로 스며듦
        0.50~0.70: 제도 작동 — 비리 적발 및 제재 효과적
        0.80+:    독립 기구 강력 — 부패 압력 차단 효과 큼
    """
    judge:      JudgeParams      = field(default_factory=JudgeParams)
    prosecutor: ProsecutorParams = field(default_factory=ProsecutorParams)
    defense:    DefenseParams    = field(default_factory=DefenseParams)
    jury:       JuryParams       = field(default_factory=JuryParams)
    defendant:  DefendantParams  = field(default_factory=DefendantParams)
    hierarchy:  LegalHierarchy   = field(default_factory=LegalHierarchy)

    # 외부 환경
    media_pressure:           float = 0.30  # 언론 압박 강도 (빅카인즈 기사량 정규화)
    political_interference:   float = 0.20  # 정치 개입 강도 (공직자 사건·정권 패턴)
    public_scrutiny:          float = 0.50  # 공개 감시 강도 — 시민·단체 견제력
    institutional_resistance: float = 0.50  # 제도적 부패 저항력 — 감찰·윤리위 활성도


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

    # 정의 괴리: 실제 유죄와 판결 점수의 거리 (절댓값 — 방향 없음)
    justice_gap = abs(verdict_score - actual_guilt)

    # 방향 있는 정의 괴리:
    #   양수(+) → 실제보다 높은 유죄 판결 (억울한 경우, OVER_CONVICTED)
    #   음수(−) → 실제보다 낮은 유죄 판결 (부당 방면, ACQUITTED)
    signed_justice_gap = verdict_score - actual_guilt

    # 판결 방향
    if signed_justice_gap > 0.20:
        verdict_direction = "OVER_CONVICTED"   # 억울한 유죄
    elif signed_justice_gap < -0.20:
        verdict_direction = "ACQUITTED"         # 부당 방면
    else:
        verdict_direction = "BALANCED"          # 균형 범위

    # 헌법 계층 온전성
    constitutional_integrity = ctx.hierarchy.hierarchy_integrity()

    # 전관예우 지수 — 3요소 통합:
    #   판사 부패 위험 × 공정성 결여 × 변호사 연계 역량
    #   이론적 최댓값: 1.0 × 1.0 × (0.5 + 0.5) = 1.0
    revolving_door_index = _clamp(
        ctx.judge.corruption_risk
        * (1.0 - ctx.judge.impartiality)
        * (0.5 + ctx.defense.skill_level * 0.5)
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
        "signed_justice_gap":     round(signed_justice_gap, 4),
        "verdict_direction":      verdict_direction,
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
    """13개 위험 플래그.

    § 기본 플래그 (11개):
        evidence_tampered    증거 신뢰성 붕괴
        bias_critical        편향 임계
        procedural_violation 절차 위반
        legal_incoherent     법리 불일치
        truth_suppressed     진실 억압
        revolving_door_active 전관예우 작동
        media_capture        언론 포획
        constitutional_breach 헌법 위기
        verdict_unjust       판결 불공정 (방향 무관 절대 괴리)
        collusion_suspected  검-판 유착
        jury_compromised     배심원 오염

    § 방향성 플래그 (2개):
        over_convicted       억울한 유죄 — 판결이 실제보다 과도하게 유죄
        unjust_acquittal     부당 방면 — 실제 유죄이나 무죄·경감 판결
    """
    T, E, L, B, P = (
        state.truth_score,
        state.evidence_integrity,
        state.legal_coherence,
        state.bias_total,
        state.procedural_score,
    )
    signed_gap = derived["signed_justice_gap"]

    return {
        # ── 기본 11개 ──
        "evidence_tampered":     E < 0.35,
        "bias_critical":         B > 0.65,
        "procedural_violation":  P < 0.35,
        "legal_incoherent":      L < 0.35,
        "truth_suppressed":      T < 0.30,
        "revolving_door_active": derived["revolving_door_index"] > 0.25,
        "media_capture":         ctx.media_pressure > 0.65,
        "constitutional_breach": derived["constitutional_integrity"] < 0.55,
        "verdict_unjust":        derived["justice_gap"] > 0.40,
        "collusion_suspected":   derived["collusion_risk"] > 0.45,
        "jury_compromised":      derived["jury_bias_raw"] > 0.40,  # weight 미적용 원시 편향
        # ── 방향성 2개 ──
        "over_convicted":        signed_gap > 0.25,   # 억울: 판결 > 실제유죄 + 0.25
        "unjust_acquittal":      signed_gap < -0.25,  # 방면: 판결 < 실제유죄 − 0.25
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
