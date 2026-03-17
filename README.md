# Legal Engine — 법정 동역학 시뮬레이션 엔진

> **ENGINE_HUB / 60_APPLIED_LAYER** — 사법 정의 판단 엔진
> Observer 24레이어 × KEMET 국가 동역학 × Pharaoh 칙령 시스템 연동

---

## 설계 철학

법정은 단순한 진실 발견 기관이 아니다.
**전관예우·증거 조작·법의 허점·감정 편향·정치 압력** 다섯 축이 동시에 작용하는 복잡계다.

이 엔진은 그 복잡계를 **연립 ODE(결합 동역학)**로 모형화하고,
파라오가 "지금 이 재판이 정당한가"를 판단할 수 있는 **단순 플래그**로 압축한다.

```
복잡한 현실                         →   파라오가 보는 것
──────────────────────────────────────────────────────────────
판사·검사·변호사·배심원·피고인       →   justice_stage  +  Ω
증거 조작 × 전관예우 × 정치 압력     →   flags (bias? corrupted?)
헌법·법률·판례·법리 계층 정합성      →   legal_coherence_signal
플리바게닝 × 위헌 심사 × 배심원 교육 →   advice  +  이벤트 권고
```

**핵심 통찰**: 이 엔진은 시뮬레이션에서만 알 수 있는 **숨겨진 진실(actual_guilt)**을 가진다.
→ `justice_gap = |verdict_score − actual_guilt|`
→ 재판이 얼마나 진실에서 벗어나 있는가 = 사법 왜곡의 정도.

---

## 상태 변수 (State Variables)

### Tier 1 — 동역학 상태 (RK4 적분 대상)

| 변수 | 기호 | 기준값 | 단위 | 의미 |
|------|------|--------|------|------|
| `truth_score` | T | 0.50 | [0, 1] | 진실이 법정에서 드러난 정도 |
| `evidence_integrity` | E | 0.70 | [0, 1] | 증거 신뢰성 |
| `legal_coherence` | L | 0.70 | [0, 1] | 법리 정합성 (판례·헌법 일치) |
| `bias_total` | B | 0.30 | [0, 1] | 편향 총합 ↑ 높을수록 위험 |
| `procedural_score` | P | 0.80 | [0, 1] | 절차적 정당성 |

> **표기 규칙**: 이 문서의 모든 `clamp(x)`는 `clamp(x, 0.0, 1.0)` — 즉 max(0, min(1, x)) 를 의미한다.

### Tier 2 — 파생 지표

| 지표 | 공식 | 의미 |
|------|------|------|
| **verdict_score** | `clamp(T×0.35 + E×0.30 + L×0.20 + P×0.15 − B×0.35)` | 사법 시스템이 도달한 판결 점수 |
| **justice_gap** | `|verdict_score − actual_guilt|` | 진실과 판결의 괴리 — 사법 왜곡 지표 |
| **revolving_door_index** | `judge.corruption_risk × defense.skill × 0.5` | 전관예우 강도 |
| **collusion_risk** | `judge.corruption_risk × (1−impartiality) + prosecutor.political × 0.3` | 검-판 유착 위험 |

### Tier 3 — 참여자 파라미터 (LegalContext)

| 참여자 | 파라미터 | 한국 프리셋 |
|--------|---------|-----------|
| **판사** | `impartiality`, `experience`, `corruption_risk` | 0.65 / 0.75 / 0.35 |
| **검사** | `evidence_quality`, `manipulation_tendency`, `political_pressure` | 0.70 / 0.30 / 0.45 |
| **변호사** | `skill_level`, `loophole_exploitation` | 0.55 / 0.35 |
| **배심원** | `emotional_bias`, `media_influence`, `weight` | 0.35 / 0.50 / 0.15 |
| **피고인** | `actual_guilt` (숨겨진 진실), `cooperation`, `resource_level` | 0.80 / 0.40 / 0.50 |

---

## 사법 정의 단계 판정

| 단계 | 조건 | 민스키 서사 |
|------|------|-----------|
| ✅ **FAIR** | gap < 0.20 | 진실과 판결 일치 — 사법 시스템 정상 작동 |
| ⚠️ **DISTORTED** | 0.20 ≤ gap < 0.40 | 편향 존재하나 판결 대체로 정당 — 모니터링 필요 |
| 🔶 **COMPROMISED** | 0.40 ≤ gap < 0.60 | 심각한 왜곡 — 진실이 절반 이상 가려짐 |
| 🔴 **CORRUPTED** | gap ≥ 0.60 | 사법 붕괴 — 재판이 진실을 반영하지 않음 → 즉각 개입 |

---

## 법정 동역학 ODE

> **표기**: `bias_suppress = β_suppress`, `α, β, γ, δ, ε, ζ, η, θ, ι, κ, λ, μ, ν` = LegalParams 기본값

### 진실 발현 ODE

```
dT/dt = α_reveal × E × judge.impartiality × max(0, 1 − B × β_suppress)   [발현]
       − B × β_suppress × prosecutor.manipulation − political_interference×0.08  [억압]
       + γ_converge × (actual_guilt − T) × P × judge.impartiality          [자연 수렴]
```

→ 공정한 판사 + 신뢰할 수 있는 증거 + 낮은 편향 = 진실 발현 가속
→ 편향 × 검사 조작 + 정치 개입(×0.08) = 진실 억압
→ 실제 유죄(actual_guilt)로의 자연 수렴력은 절차 × 공정성에 비례

### 증거 신뢰성 ODE

```
dE/dt = δ_investigate × prosecutor.evidence_quality × (1 − manipulation) × (1 + cooperation×0.2)
       − ε_decay × E                                                        [자연 감쇠]
       − ζ_defense × defense.skill × (loophole×0.5 + 0.5) × E             [변호 도전]
```

> **구현 참고**: 변호 도전항은 `skill × (loophole×0.5 + 0.5) × E` — 허점 활용이 0이어도
> 스킬의 50%는 기본 도전력으로 작동한다. (loophole=0 → factor=0.5, loophole=1 → factor=1.0)

→ 피고인 협조가 증거 강화 보너스 제공
→ 스타 변호사는 존재하는 증거 자체의 신뢰성에 도전

### 법리 정합성 ODE

```
dL/dt = η_precedent × (hierarchy_integrity − L)                            [판례 수렴]
       − θ_loophole × defense.loophole × (1 − doctrine_score)             [허점 왜곡]
       − political_interference × 0.08
```

→ 법리가 모호할수록(doctrine_score 낮을수록) 허점 활용이 효과적
→ 정치 개입은 법리 해석을 왜곡

### 편향 총합 ODE

```
revolving = judge.corruption_risk × (1 − judge.impartiality)
dB/dt = ι_corrupt × (revolving + political_pressure×0.3 + media_pressure×0.2) × (1−resist)
       − κ_reform × public_scrutiny × judge.impartiality                   [개혁 억제]
       − λ_decay × B                                                        [자연 감쇠]
```

→ **전관예우 메커니즘**: corruption_risk × (1−impartiality) = 부패 판사의 편향 기여도
→ 공개 감시 + 공정한 판사 = 편향의 자연 감소

### 절차적 정당성 ODE

```
dP/dt = μ_restore × (1 − P) × judge.experience                            [자연 회복]
       − ν_violation × B × (1 − institutional_resistance)                  [편향 훼손]
```

### ODE 파라미터 기본값

| 파라미터 | 기호 | 기본값 | 의미 |
|---------|------|--------|------|
| `alpha_reveal` | α | 0.30 | 증거 → 진실 발현 속도 |
| `beta_suppress` | β | 0.40 | 편향 → 진실 억압 강도 |
| `gamma_converge` | γ | 0.10 | 진실 자연 수렴 속도 |
| `delta_investigate` | δ | 0.25 | 수사 품질 → 증거 강화 |
| `epsilon_decay` | ε | 0.05 | 증거 자연 감쇠율 |
| `zeta_defense` | ζ | 0.15 | 변호 → 증거 신뢰 도전 |
| `eta_precedent` | η | 0.20 | 판례 → 법리 수렴 속도 |
| `theta_loophole` | θ | 0.25 | 허점 활용 → 법리 왜곡 |
| `iota_corrupt` | ι | 0.35 | 부패 압력 → 편향 증가 |
| `kappa_reform` | κ | 0.15 | 공개 감시 → 편향 감소 |
| `lambda_decay` | λ | 0.05 | 편향 자연 감쇠 |
| `mu_restore` | μ | 0.20 | 절차 자연 회복 속도 |
| `nu_violation` | ν | 0.30 | 편향 → 절차 훼손 강도 |
| `dt` | h | 1.0 | 타임스텝 (1 심급 또는 1개월) |

> 수치 적분: **RK4 4계 Runge-Kutta** (real_estate_engine · kemet_engine과 동일 방식)

---

## 법률 계층 구조 (LegalHierarchy)

```
헌법 (constitution_score)    × 0.35  ← 최상위 규범
  ↓ 위헌심사
법률 (statute_score)         × 0.25
  ↓ 위임
시행령 (regulation_score)    × 0.15
  ↓ 해석
판례 (precedent_score)       × 0.15
  ↓ 적용
법리 (doctrine_score)        × 0.10

hierarchy_integrity = 가중 평균 → legal_coherence 자연 수렴점
```

위헌 상황 → constitution_score 하락 → hierarchy_integrity 급락 → legal_coherence 붕괴
→ Observer L_legal Ω 하락 → Ω_global 하락 → CRITICAL

---

## Observer 5레이어 — Ω 계산식

### 1. L_truth (진실 발현도)

```
Ω_truth = (T/0.80) × 0.60 + (1 − gap/0.60) × 0.40
```

### 2. L_evidence (증거 신뢰성)

```
Ω_evidence = ((E−0.20)/0.70) × 0.65 + (1−manipulation) × 0.35
```

### 3. L_legal (법리 정합성)

```
Ω_legal = ((L−0.20)/0.70) × 0.60 + ((hier−0.40)/0.55) × 0.40
```

### 4. L_bias (편향 억제)

```
Ω_bias = (1−B/0.80)×0.50 + (1−collusion/0.70)×0.25 + (1−revolving/0.70)×0.25
```

### 5. L_procedural (절차적 정당성)

> **레이어 성격**: 다른 4개 레이어가 법정 물리량을 측정하는 반면,
> L_procedural은 "절차 정당성이 유지되고 있는가"를 측정하는 행정 감시 레이어다.

```
Ω_procedural = ((P−0.20)/0.70) × 0.70 + public_scrutiny × 0.30
강제 임계치: CORRUPTED → Ω_global ≤ 0.25 / COMPROMISED → Ω_global ≤ 0.45
```

### 전역 Ω

```
Ω_global = Ω_truth×0.30 + Ω_evidence×0.25 + Ω_legal×0.20 + Ω_bias×0.15 + Ω_procedural×0.10

판정: JUST(≥0.80) / STABLE(0.60~) / FRAGILE(0.40~) / CRITICAL(<0.40)
```

---

## Athena 자동 권고 (recommend_event)

우선순위 순으로 평가, 첫 매칭에서 반환:

| 조건 | 권고 이벤트 |
|------|-----------|
| `evidence_tampered + bias_critical` | `judicial_reform×1.0 + transparency_law×1.0` |
| `collusion_suspected` | `judicial_reform×1.0 + constitutional_review×0.5` |
| `constitutional_breach` | `constitutional_review×1.0 + precedent_establish×0.5` |
| `revolving_door_active` | `transparency_law×1.0 + judicial_reform×0.5` |
| `truth_suppressed` | `plea_bargain×1.0 + transparency_law×0.7` |
| `jury_compromised` | `jury_education×1.0` |
| `legal_incoherent` | `precedent_establish×1.0 + constitutional_review×0.3` |
| `procedural_violation` | `transparency_law×0.5 + judicial_reform×0.3` |
| 이상 없음 | 이벤트 없음 |

> Athena는 권고만 한다. 최종 발동은 파라오(인간) 승인 필요.

---

## 사법 이벤트 12종

| 이벤트 | 즉각 효과 | 동역학 경로 |
|--------|---------|-----------|
| `evidence_fabrication` | E ↓0.30, T ↓0.15 | manipulation ↑ → dE 지속 하락 |
| `evidence_suppression` | T ↓0.20, E ↓0.10 | 진실 발현 차단 |
| `judicial_corruption` | B ↑0.25, impartiality ↓ | revolving_door ↑ → dB 지속 상승 |
| `media_manipulation` | media_pressure ↑, jury.media ↑ | bias ↑ → Ω_bias 하락 |
| `judicial_reform` | B ↓0.20, resist ↑ | dB 지속 감소, corruption_risk ↓ |
| `transparency_law` | public_scrutiny ↑, manipulation ↓ | dP 개선, dB 감소 |
| `jury_education` | emotional_bias ↓, deliberation ↑ | jury_bias 감소 |
| `precedent_establish` | precedent_score ↑, L ↑ | dL 수렴점 상승 |
| `constitutional_review` | constitution_score ↑, L ↑ | hierarchy_integrity ↑ → dL 개선 |
| `plea_bargain` | cooperation ↑, T ↑, E ↑ | dT 자연 수렴 가속 |
| `procedural_violation` | P ↓0.25, B ↑0.10 | 재심 필요 신호 |
| `star_defense` | skill ↑ × resource_level | dE 방어 도전 강화 |

---

## 11개 위험 플래그

> **주의**: `procedural_violation`은 **상태 플래그**(P < 0.35 감지)와 **이벤트 충격**(P ↓0.25 직접 주입) 두 가지로 사용된다. 혼동 주의.

| 플래그 | 조건 | 의미 |
|--------|------|------|
| `evidence_tampered` | E < 0.35 | 증거 훼손 |
| `bias_critical` | B > 0.65 | 심각 편향 |
| `procedural_violation` *(상태 플래그)* | P < 0.35 | 절차 위반 감지 |
| `legal_incoherent` | L < 0.35 | 법리 불일치 |
| `truth_suppressed` | T < 0.30 | 진실 억압 |
| `revolving_door_active` | revolving_door_index > 0.35 | 전관예우 동작 |
| `media_capture` | media_pressure > 0.65 | 언론 포획 |
| `constitutional_breach` | hierarchy_integrity < 0.55 | 헌법 위반 |
| `verdict_unjust` | justice_gap > 0.40 | 부당 판결 |
| `collusion_suspected` | collusion_risk > 0.45 | 검-판 유착 |
| `jury_compromised` | jury_bias_raw > 0.40 | 배심원 오염 (weight 미적용 원시 편향 기준) |

---

## 한국 형사 프리셋 초기값

| 변수 | 값 | 근거 |
|------|-----|------|
| `bias_total` | 0.45 | 전관예우·검찰 권력 구조 반영 |
| `judge.corruption_risk` | 0.35 | 변호사-판사 전관예우 비율 |
| `prosecutor.political_pressure` | 0.45 | 검찰의 정치 종속성 |
| `jury.weight` | 0.15 | 국민참여재판 비중 낮음 |
| `jury.media_influence` | 0.50 | 높은 SNS·언론 영향도 |
| `media_pressure` | 0.55 | 언론의 재판 선점 현상 |
| `political_interference` | 0.40 | 고위직 사건 정치 개입 |
| `truth_score` (초기) | 0.55 | 수사 단계 진실 발현 부분적 |
| `evidence_integrity` (초기) | 0.65 | 증거 신뢰성 양호하나 취약 |

---

## 시뮬레이션 결과 예시

```
시나리오 A: 이벤트 없음 (한국 형사, 24 스텝)

  Stp      T      E      L      B      P  Verdict    Gap       Ω      Status
  --------------------------------------------------------------------------
    4  0.708  0.857  0.557  0.489  0.580    0.532  0.268   0.693      STABLE
   12  1.000  1.000  0.497  0.547  0.432    0.623  0.177   0.711      STABLE
   24  1.000  1.000  0.483  0.601  0.321    0.584  0.216   0.685      STABLE

  최종 진단: 절차 위반, 배심원 오염 경고
  → T·E 조기 포화 (전관예우는 T·E 발현 자체를 막지 못함)
  → 그러나 B(편향) 지속 상승 + P(절차) 저하 → verdict_score 억제 → Ω 정체
  → T·E가 1.0이어도 B가 크면 JUST 도달 불가 — 구조 변수 해소 없이 STABLE 고착

시나리오 B: 증거 조작(stp3) → 사법 개혁(stp12) → 위헌 심사(stp18)

  Stp      T      E      L      B      P  Verdict    Gap       Ω      Status
  --------------------------------------------------------------------------
    3  0.434  0.508  0.574  0.480  0.606    0.342  0.458   0.450     FRAGILE  ◀ 증거 조작
    8  0.312  0.666  0.516  0.521  0.495    0.304  0.496   0.450     FRAGILE
   12  0.322  0.759  0.497  0.315  0.551    0.412  0.388   0.562     FRAGILE  ◀ 사법 개혁
   16  0.631  0.855  0.488  0.222  0.647    0.594  0.206   0.707      STABLE
   18  0.819  0.890  0.658  0.182  0.735    0.732  0.069   0.829        JUST  ◀ 위헌 심사
   24  1.000  0.959  0.567  0.084  0.826    0.846  0.046   0.838        JUST

  최종 진단: 배심원 오염 경고만 잔류 (나머지 플래그 해소)
  → 증거 조작으로 FRAGILE 고착 → 사법 개혁·위헌 심사 연쇄로 JUST 달성
  → B(편향) 0.480 → 0.084 급락, justice_gap 0.458 → 0.046 수렴

핵심 인사이트:
  단일 이벤트로는 JUST 달성 불가.
  judicial_reform(B 직접 감소) + constitutional_review(L·hierarchy 회복) 연쇄가 필수.
  전관예우 구조가 해소될 때까지 T·E 포화에도 Ω는 FRAGILE에 머문다.
```

---

## 설치 및 사용

```bash
# 1단계: legal_engine 이름으로 클론 (패키지 이름 자동 설정)
git clone https://github.com/qquartsco-svg/LAW.git legal_engine

# 2단계: legal_engine/ 의 부모 디렉토리에서 실행
#   예시: ~/projects/legal_engine/ 에 클론했다면 ~/projects/ 에서 아래 명령 실행
cd ..                               # legal_engine/ 의 부모로 이동

# 테스트 (의존성: pytest만 필요)
python -m pytest legal_engine/tests/test_legal.py -v
```

```python
import sys
sys.path.insert(0, ".")   # legal_engine/ 의 부모 디렉토리를 sys.path에 추가

from legal_engine import LegalEngine, JudicialEvent

# 한국 형사 시스템 24 스텝
engine = LegalEngine(preset="korea")
engine.simulate(steps=24)
engine.report()

# 시나리오: 증거 조작(stp3) → 사법 개혁(stp12) → 위헌 심사(stp18)
events = {
    2:  JudicialEvent(evidence_fabrication=1.0),
    11: JudicialEvent(judicial_reform=1.0, transparency_law=0.8),
    17: JudicialEvent(constitutional_review=1.0, precedent_establish=0.5),
}
engine2 = LegalEngine(preset="korea")
engine2.simulate(steps=24, event_at=events)
engine2.report()

# Athena 자동 권고 발동
engine3 = LegalEngine(preset="korea")
engine3.simulate(steps=12, auto_event=True)

# 최종 상태 dict
summary = engine.summary_dict()
print(summary["observation"]["Ω_global"])
print(summary["advice"])
```

---

## 파일 구조

```
(legal_engine/)          ← git clone ... legal_engine 으로 클론
├── __init__.py          — 패키지 공개 API (LegalEngine, JudicialEvent 등)
├── legal_state.py       — 상태 변수·파생 지표·플래그·법률 계층·참여자 파라미터
├── legal_dynamics.py    — ODE 5개 미분 + RK4 + 이벤트 충격 12종
├── legal_observer.py    — Observer 5레이어 Ω + 진단 조언
├── legal_engine.py      — 시뮬레이션 엔진 (preset·simulate·report·summary)
├── pharaoh_decree_legal.py — 이벤트 12종 + Athena 자동 권고
└── tests/
    └── test_legal.py    — 52 테스트 (§1~§6 전체 PASS)
```

---

## 버전 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| **v0.1.2** | 2026-03-17 | README 문서 정밀화 — Ω_proc→Ω_procedural 표기 통일, 시나리오A 문장 교정(전관예우 T·E 억제 메커니즘), 설치 실행 위치 명시, procedural_violation 플래그·이벤트 이중 사용 구분 표시 |
| **v0.1.1** | 2026-03-17 | README 동기화 — 시나리오 A/B 실제 실행 결과 갱신, ODE 수식 정오, jury_compromised 플래그 weight 독립 계산, import 예시 수정 |
| **v0.1.0** | 2026-03-17 | 초기 구현 — 상태·동역학·Observer·이벤트·엔진, 52 테스트 PASS |

---

## 라이선스

MIT License.
