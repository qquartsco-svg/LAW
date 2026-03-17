# Legal Engine — 법정 동역학 시뮬레이션 엔진

> **ENGINE_HUB / 60_APPLIED_LAYER** — 사법 정의 흐름 분석 엔진
> Observer 5레이어 Ω × KEMET 국가 동역학 × Pharaoh 칙령 시스템 연동

---

## 설계 철학

법정은 단순한 진실 발견 기관이 아니다.
**전관예우·증거 조작·법의 허점·감정 편향·정치 압력** 다섯 축이 동시에 작용하는 복잡계다.

이 엔진은 그 복잡계를 **연립 ODE(결합 동역학)**로 모형화하고,
파라오가 "지금 이 재판이 어디로 흘러가는가"를 판단할 수 있는 **압축 신호**로 변환한다.

```
복잡한 현실                         →   파라오가 보는 것
──────────────────────────────────────────────────────────────
판사·검사·변호사·배심원·피고인       →   justice_stage  +  Ω_global
증거 조작 × 전관예우 × 정치 압력     →   flags (bias? corrupted?)
헌법·법률·판례·법리 계층 정합성      →   legal_coherence + constitutional_integrity
플리바게닝 × 위헌 심사 × 배심원 교육 →   advice  +  이벤트 권고
```

### 핵심 통찰 — 두 가지 괴리

**① 방향 없는 절대 괴리 (사법 왜곡 지표)**
```
justice_gap = |verdict_score − actual_guilt|
```
진실과 판결 사이의 거리. 방향을 따지지 않고 얼마나 벗어났는지를 측정한다.

**② 방향 있는 괴리 (억울/방면 구분)**
```
signed_justice_gap = verdict_score − actual_guilt

  양수(+): 판결 > 실제 유죄  →  OVER_CONVICTED (억울한 유죄 가능성)
  음수(−): 판결 < 실제 유죄  →  ACQUITTED (부당 방면 가능성)
```
같은 gap=0.40이어도 억울한 유죄와 부당 방면은 처방이 다르다.
이 차이를 방향 플래그(`over_convicted` / `unjust_acquittal`)로 명시한다.

---

## 상태 변수 (State Variables)

### Tier 1 — 동역학 상태 (RK4 적분 대상)

| 변수 | 기호 | 기준값 | 범위 | 의미 |
|------|------|--------|------|------|
| `truth_score` | T | 0.50 | [0, 1] | 진실이 법정에서 드러난 정도 |
| `evidence_integrity` | E | 0.70 | [0, 1] | 증거 신뢰성 |
| `legal_coherence` | L | 0.70 | [0, 1] | 법리 정합성 (판례·헌법 일치) |
| `bias_total` | B | 0.30 | [0, 1] | 편향 총합 ↑ 높을수록 위험 |
| `procedural_score` | P | 0.80 | [0, 1] | 절차적 정당성 |

> **표기 규칙**: `clamp(x)` = `max(0, min(1, x))`

### Tier 2 — 파생 지표

| 지표 | 공식 | 의미 |
|------|------|------|
| **verdict_score** | `clamp(T×0.35 + E×0.30 + L×0.20 + P×0.15 − B×0.35)` | 사법 시스템이 도달한 판결 점수 |
| **justice_gap** | `\|verdict_score − actual_guilt\|` | 정의 괴리 절댓값 — 방향 없음 |
| **signed_justice_gap** | `verdict_score − actual_guilt` | 방향 있는 정의 괴리 (+억울 / −방면) |
| **verdict_direction** | `OVER_CONVICTED / ACQUITTED / BALANCED` | signed_gap ±0.20 기준 분기 |
| **revolving_door_index** | `corruption × (1−impartiality) × (0.5 + skill×0.5)` | 전관예우 강도 (3요소 통합) |
| **collusion_risk** | `corruption × (1−impartiality) + prosecutor.political × 0.3` | 검-판 유착 위험 |
| **constitutional_integrity** | `hierarchy_integrity()` 가중 평균 | 법률 계층 전체 온전성 |

> **revolving_door_index 공식 해설**:
> 전관예우는 단독 요소가 아니라 **3요소가 동시에 성립**해야 발생한다.
> - `corruption_risk`: 판사가 부패에 취약할 것
> - `(1 − impartiality)`: 판사가 공정하지 않을 것
> - `(0.5 + skill × 0.5)`: 변호사가 연계를 활용할 역량이 있을 것
>
> 판사가 완전히 공정하면(impartiality=1.0) 부패 위험이 아무리 높아도 index = 0.
> 이론적 최댓값 = 1.0.

### Tier 3 — 참여자 파라미터 (LegalContext)

| 참여자 | 파라미터 | 한국 프리셋 | 의미 |
|--------|---------|-----------|------|
| **판사** | `impartiality` | 0.65 | 공정성 [0=완전 편향, 1=완전 공정] |
| | `experience` | 0.75 | 법률 경험·역량 |
| | `corruption_risk` | 0.35 | 부패·전관예우 취약도 |
| **검사** | `evidence_quality` | 0.70 | 증거 수집 품질 |
| | `manipulation_tendency` | 0.30 | 증거 조작 경향 |
| | `political_pressure` | 0.45 | 상부·정치 압력 |
| **변호사** | `skill_level` | 0.55 | 법률 기술 (전관예우 연계 역량 포함) |
| | `loophole_exploitation` | 0.35 | 법의 허점 활용도 |
| **배심원** | `emotional_bias` | 0.35 | 감정적 편향 |
| | `media_influence` | 0.50 | 미디어·여론 영향도 |
| | `deliberation_quality` | 0.55 | 숙의 품질 (진실 발현 보조) |
| | `weight` | 0.15 | 판결 반영 비중 (한국=0.15, 미국=1.0) |
| **피고인** | `actual_guilt` | 0.80 | **숨겨진 진실** — 시뮬레이션만 앎 |
| | `cooperation` | 0.40 | 수사·재판 협조도 |
| | `resource_level` | 0.50 | 재력 (변호인 품질에 영향) |

---

## 사법 정의 4단계 판정

| 단계 | 조건 | 강제 Ω 상한 | 서사 |
|------|------|------------|------|
| ✅ **FAIR** | gap < 0.20 | 없음 | 진실과 판결 일치 — 정상 작동 |
| ⚠️ **DISTORTED** | 0.20 ≤ gap < 0.40 | **Ω ≤ 0.70** | 편향 존재 — 모니터링 필요, JUST 불가 |
| 🔶 **COMPROMISED** | 0.40 ≤ gap < 0.60 | **Ω ≤ 0.45** | 심각 왜곡 — FRAGILE 이하 강제 |
| 🔴 **CORRUPTED** | gap ≥ 0.60 | **Ω ≤ 0.25** | 사법 붕괴 — CRITICAL 이하 강제 |

> **강제 임계치의 의미**: 5개 레이어 수치가 아무리 좋아도, 정의 괴리가 크면
> 전역 Ω를 강제로 낮춘다. 구조적 불의를 수치적으로 "세탁"하지 못하게 방지.

---

## 법정 동역학 ODE

> **표기**: `α β γ δ ε ζ η θ ι κ λ μ ν` = LegalParams 기본값
> **clamp 범위**: 각 dX는 ±0.30~0.40 이내로 발산 방지

### 1. 진실 발현 dT/dt

```
dT/dt = α_reveal × E × judge.impartiality × max(0, 1 − B×β_suppress)   [발현]
        × (1 + jury.weight × jury.deliberation_quality × 0.08)           [배심 숙의 보조]
       − B × β_suppress × prosecutor.manipulation − political×0.08       [억압]
       + γ_converge × (actual_guilt − T) × P × judge.impartiality       [자연 수렴]
```

| 항 | 의미 |
|----|------|
| **발현항** | 공정한 판사 + 신뢰할 증거 + 낮은 편향 → 진실이 드러남 |
| **배심 보조** | deliberation_quality×weight×8% 승수 — 한국(weight=0.15): ~+0.7%, 완전 배심제(weight=1.0): ~+5.6% |
| **억압항** | 편향 × 조작 경향 + 정치 개입 → 진실을 가림 |
| **수렴항** | 진실(actual_guilt)로의 자연 회귀력 — 절차와 공정성에 비례 |

### 2. 증거 신뢰성 dE/dt

```
dE/dt = δ_investigate × prosecutor.quality × (1−manipulation) × (1 + cooperation×0.2)
       − ε_decay × E                                                [자연 감쇠]
       − ζ_defense × skill × (loophole×0.5 + 0.5) × E             [변호 도전]
```

> **변호 도전 공식 해설**: `skill × (loophole×0.5 + 0.5) × E`
> - loophole=0 → factor=0.5 (기본 스킬의 50%는 항상 도전력으로 작동)
> - loophole=1 → factor=1.0 (허점 활용시 최대 도전력)
> - 존재하는 증거(E)에 비례 — 증거가 없으면 도전할 것도 없다

### 3. 법리 정합성 dL/dt

```
dL/dt = η_precedent × (hierarchy_integrity − L)                    [판례 수렴]
       − θ_loophole × defense.loophole × (1 − doctrine_score)      [허점 왜곡]
       − political_interference × 0.08                             [정치 왜곡]
```

> `hierarchy_integrity`가 자연 수렴점 — 법률 계층이 무너지면 L도 수렴점이 하락한다.
> 법리(doctrine_score)가 모호할수록 허점 활용이 더 효과적이다.

### 4. 편향 총합 dB/dt

```
revolving = judge.corruption_risk × (1−impartiality) × (0.5 + defense.skill×0.5)

dB/dt = ι_corrupt × (revolving + political_pressure×0.3 + media_pressure×0.2) × (1−resist)
       − κ_reform × public_scrutiny × judge.impartiality            [감시 억제]
       − λ_decay × B                                                [자연 감쇠]
```

> **revolving 공식**: `compute_derived`의 `revolving_door_index`와 동일 공식으로 통일.
> 판사 부패 + 공정성 결여 + 변호사 연계가 맞물릴 때만 편향이 구조적으로 증가한다.

### 5. 절차적 정당성 dP/dt

```
dP/dt = μ_restore × (1−P) × judge.experience       [자연 회복]
       − ν_violation × B × (1−institutional_resistance)   [편향 훼손]
```

### ODE 파라미터 기본값

| 파라미터 | 기호 | 기본값 | 역할 |
|---------|------|--------|------|
| `alpha_reveal` | α | 0.30 | 증거 → 진실 발현 속도 |
| `beta_suppress` | β | 0.40 | 편향 → 진실 억압 강도 |
| `gamma_converge` | γ | 0.10 | 진실 자연 수렴 속도 |
| `delta_investigate` | δ | 0.25 | 수사 품질 → 증거 강화 |
| `epsilon_decay` | ε | 0.05 | 증거 자연 감쇠율 |
| `zeta_defense` | ζ | 0.15 | 변호 → 증거 신뢰 도전 강도 |
| `eta_precedent` | η | 0.20 | 판례 → 법리 수렴 속도 |
| `theta_loophole` | θ | 0.25 | 허점 활용 → 법리 왜곡 |
| `iota_corrupt` | ι | 0.35 | 부패 압력 → 편향 증가 |
| `kappa_reform` | κ | 0.15 | 공개 감시 → 편향 감소 |
| `lambda_decay` | λ | 0.05 | 편향 자연 감쇠 |
| `mu_restore` | μ | 0.20 | 절차 자연 회복 속도 |
| `nu_violation` | ν | 0.30 | 편향 → 절차 훼손 강도 |
| `dt` | h | 1.0 | 타임스텝 (1 심급 or 1개월) |

> 수치 적분: **RK4 4계 Runge-Kutta** (real_estate_engine · kemet_engine과 동일 방식)

---

## 법률 계층 구조 (LegalHierarchy)

```
헌법 (constitution_score)    × 0.35  ← 최상위 규범
  ↓ 위헌 심사
법률 (statute_score)         × 0.25
  ↓ 위임
시행령 (regulation_score)    × 0.15
  ↓ 해석
판례 (precedent_score)       × 0.15
  ↓ 적용
법리 (doctrine_score)        × 0.10

hierarchy_integrity = 가중 평균 → legal_coherence의 자연 수렴점 역할
```

위헌 상황이 발생하면:
`constitution_score ↓` → `hierarchy_integrity ↓` → `dL/dt 수렴점 하락` → `L 붕괴`
→ `Ω_legal ↓` → `Ω_global ↓` → CRITICAL

---

## Observer 5레이어 — Ω 계산식

전역 Ω는 5개 레이어의 가중 평균이다. 각 레이어는 **정규화된 [0, 1] 값**이다.

### 1. Ω_truth — 진실 발현도

```
T_ω   = clamp(T / 0.80)              T=0.80 이상이면 모두 1.0
gap_ω = clamp(1 − |gap| / 0.60)     gap=0 → 1.0, gap≥0.60 → 0.0
방향 패널티 = |signed_gap| × 0.20   억울하거나(+) 방면(−) 방향 강도에 비례 추가 감산

Ω_truth = T_ω × 0.60 + (gap_ω − 방향 패널티) × 0.40
```

> justice_gap이 동일하더라도 방향이 뚜렷할수록 Ω_truth가 낮아진다.
> 억울한 유죄와 부당 방면 모두 진실 발현 실패로 본다.

### 2. Ω_evidence — 증거 신뢰성

```
E_ω = clamp((E − 0.20) / 0.70)      E=0.20 → 0.0, E=0.90 → 1.0
m_ω = clamp(1 − manipulation)       조작 경향 없으면 1.0

Ω_evidence = E_ω × 0.65 + m_ω × 0.35
```

> E의 정규화 하한 0.20: 법정에서 최소한의 증거는 항상 존재한다는 구조적 전제.
> manipulation_tendency를 별도 반영하는 이유: E가 아직 높더라도 조작 성향이 있으면 미래 위험 신호.

### 3. Ω_legal — 법리 정합성

```
L_ω    = clamp((L − 0.20) / 0.70)    L=0.20 → 0.0, L=0.90 → 1.0
hier_ω = clamp((hier − 0.40) / 0.55) hier=0.40 → 0.0, hier=0.95 → 1.0

Ω_legal = L_ω × 0.60 + hier_ω × 0.40
```

> hierarchy_integrity의 실용 범위: 기본 파라미터에서 약 0.81. 위헌 상황에서 0.40 이하.
> 정규화 구간 [0.40, 0.95]는 실제 운용 범위를 커버한다.

### 4. Ω_bias — 편향 억제

```
bias_ω = clamp(1 − B / 0.80)         B=0.80 이상이면 bias_ω=0
coll_ω = clamp(1 − collusion / 0.70) 유착 위험 역산
rev_ω  = clamp(1 − revolving)        전관예우 역산 (이론적 최댓값 1.0 → 최악시 0.0)

Ω_bias = bias_ω × 0.50 + coll_ω × 0.25 + rev_ω × 0.25
```

> **rev_ω 정규화 해설**:
> revolving_door_index의 이론적 최댓값은 1.0이므로 `1 − revolving`이면 최악시 0.0.
> 이전 공식(1 − revolving/0.70)은 최악이어도 rev_ω ≥ 0.29 → 전관예우 패널티 불완전.

### 5. Ω_procedural — 절차적 정당성

```
P_ω = clamp((P − 0.20) / 0.70)    P=0.20 → 0.0, P=0.90 → 1.0

Ω_procedural = P_ω × 0.70 + public_scrutiny × 0.30
```

> `public_scrutiny`(공개 감시)를 포함하는 이유: 절차적 정당성은 내부 절차 준수(P)만으로
> 충분하지 않다. 외부 시민 감시가 존재할 때 진정한 정당성이 확보된다.

### 전역 Ω 및 강제 임계치

```
Ω_global = Ω_truth×0.30 + Ω_evidence×0.25 + Ω_legal×0.20 + Ω_bias×0.15 + Ω_procedural×0.10

강제 임계치 (단계별 상한):
  CORRUPTED   → Ω_global ≤ 0.25  (CRITICAL 이하 강제)
  COMPROMISED → Ω_global ≤ 0.45  (FRAGILE 이하 강제)
  DISTORTED   → Ω_global ≤ 0.70  (STABLE 이하 강제, JUST 불가)
  FAIR        → 제한 없음

판정 기준: JUST(≥0.80) / STABLE(0.60~) / FRAGILE(0.40~) / CRITICAL(<0.40)
```

**가중치 설계 근거**:

| 레이어 | 가중 | 이유 |
|--------|------|------|
| Ω_truth | 0.30 | 진실이 드러나지 않으면 다른 모든 것이 무의미 |
| Ω_evidence | 0.25 | 증거는 진실의 물질적 기반 |
| Ω_legal | 0.20 | 법리 없는 판결은 자의적 처분 |
| Ω_bias | 0.15 | 편향은 위의 세 레이어를 왜곡하는 외부 작용 |
| Ω_procedural | 0.10 | 절차는 신뢰 가능성을 담보하는 형식 |

---

## 13개 위험 플래그

> **주의**: `procedural_violation`은 **상태 플래그**(P < 0.35 감지)와 **이벤트 충격**(P ↓0.25 직접 주입) 두 가지로 사용된다.

### 기본 11개 플래그

| 플래그 | 조건 | 의미 |
|--------|------|------|
| `evidence_tampered` | E < 0.35 | 증거 훼손 |
| `bias_critical` | B > 0.65 | 심각 편향 |
| `procedural_violation` *(상태)* | P < 0.35 | 절차 위반 감지 |
| `legal_incoherent` | L < 0.35 | 법리 불일치 |
| `truth_suppressed` | T < 0.30 | 진실 억압 |
| `revolving_door_active` | revolving_door_index > **0.25** | 전관예우 동작 |
| `media_capture` | media_pressure > 0.65 | 언론 포획 |
| `constitutional_breach` | hierarchy_integrity < 0.55 | 헌법 위기 |
| `verdict_unjust` | justice_gap > 0.40 | 부당 판결 (방향 무관) |
| `collusion_suspected` | collusion_risk > 0.45 | 검-판 유착 |
| `jury_compromised` | jury_bias_raw > 0.40 | 배심원 오염 (weight 미적용 원시 편향) |

### 방향성 플래그 2개 (v0.2.0 신규)

| 플래그 | 조건 | 의미 |
|--------|------|------|
| `over_convicted` | signed_justice_gap > 0.25 | 억울한 유죄 — 판결이 실제보다 과도 |
| `unjust_acquittal` | signed_justice_gap < −0.25 | 부당 방면 — 실제 유죄이나 낮은 판결 |

> `verdict_unjust`는 방향을 따지지 않는 절대 괴리(gap > 0.40).
> `over_convicted` / `unjust_acquittal`은 방향이 있어 처방이 달라진다.
>
> `revolving_door_active` 임계치: 0.35 → **0.25** (3요소 공식으로 수치 범위 조정)

---

## Athena 자동 권고 (recommend_event)

우선순위 순으로 평가, 첫 매칭에서 반환:

| 우선순위 | 조건 | 권고 이벤트 |
|---------|------|-----------|
| 1 | `evidence_tampered + bias_critical` | `judicial_reform×1.0 + transparency_law×1.0` |
| 2 | `collusion_suspected` | `judicial_reform×1.0 + constitutional_review×0.5` |
| 3 | `constitutional_breach` | `constitutional_review×1.0 + precedent_establish×0.5` |
| 4 | `revolving_door_active` | `transparency_law×1.0 + judicial_reform×0.5` |
| 5 | `truth_suppressed` | `plea_bargain×1.0 + transparency_law×0.7` |
| 6 | `jury_compromised` | `jury_education×1.0` |
| 7 | `legal_incoherent` | `precedent_establish×1.0 + constitutional_review×0.3` |
| 8 | `procedural_violation` | `transparency_law×0.5 + judicial_reform×0.3` |
| — | 이상 없음 | 이벤트 없음 |

> Athena는 권고만 한다. 최종 발동은 파라오(인간) 승인 필요.

---

## 사법 이벤트 12종

| 이벤트 | 즉각 충격 | 동역학 경로 |
|--------|---------|-----------|
| `evidence_fabrication` | E ↓0.30, T ↓0.15 | manipulation ↑ → dE 지속 하락 |
| `evidence_suppression` | T ↓0.20, E ↓0.10 | 진실 발현 차단 |
| `judicial_corruption` | B ↑0.25, impartiality ↓ | revolving ↑ → dB 구조적 상승 |
| `media_manipulation` | media_pressure ↑0.30, jury.media ↑ | bias ↑ → Ω_bias 하락 |
| `judicial_reform` | B ↓0.20, resist ↑0.15 | dB 지속 감소, corruption_risk ↓ |
| `transparency_law` | public_scrutiny ↑, manipulation ↓, P ↑0.10 | dP 개선, dB 감소 |
| `jury_education` | emotional_bias ↓0.15, deliberation ↑0.15 | jury_bias 감소, dT 발현 향상 |
| `precedent_establish` | precedent_score ↑0.15, L ↑0.10 | dL 수렴점 상승 |
| `constitutional_review` | constitution_score ↑0.10, L ↑0.15, P ↑0.05 | hierarchy_integrity ↑ |
| `plea_bargain` | cooperation ↑0.30, T ↑0.15, E ↑0.10 | dT 자연 수렴 가속 |
| `procedural_violation` *(이벤트)* | P ↓0.25, B ↑0.10 | 재심 필요 신호 |
| `star_defense` | skill ↑×resource_level, loophole ↑ | dE 도전 강화 |

---

## 프리셋

### 한국 형사 (`"korea"`)

| 변수 | 값 | 근거 |
|------|-----|------|
| `bias_total` | 0.45 | 전관예우·검찰 권력 구조 |
| `judge.corruption_risk` | 0.35 | 전관 변호사-현직 판사 연계 |
| `judge.impartiality` | 0.65 | 구조적 편향 존재 |
| `prosecutor.political_pressure` | 0.45 | 검찰의 정치 종속성 |
| `jury.weight` | 0.15 | 국민참여재판 제한적 반영 |
| `jury.media_influence` | 0.50 | 높은 SNS·언론 영향도 |
| `media_pressure` | 0.55 | 재판 전 언론 선점 현상 |
| `political_interference` | 0.40 | 고위직 사건 정치 개입 |
| `truth_score` (초기) | 0.55 | 수사 단계 진실 부분 발현 |
| `evidence_integrity` (초기) | 0.65 | 증거 양호하나 취약 |

### 중립 (`"neutral"`)

편향 최소(bias=0.20), 완전 배심제(jury.weight=1.0), corruption_risk=0.10.
이상적 사법 시스템의 기준선으로 사용.

---

## 시뮬레이션 결과 (v0.2.0 기준)

```
시나리오 A: 이벤트 없음 (한국 형사, 24 스텝)

  Stp      T      E      L      B      P  Verdict    Gap       Ω      Status
  --------------------------------------------------------------------------
    4  0.718  0.857  0.557  0.468  0.586    0.544  0.256   0.696      STABLE
    8  0.949  0.993  0.516  0.483  0.515    0.641  0.159   0.730      STABLE
   12  1.000  1.000  0.497  0.495  0.468    0.646  0.154   0.722      STABLE
   16  1.000  1.000  0.488  0.505  0.437    0.636  0.164   0.715      STABLE
   20  1.000  1.000  0.485  0.513  0.415    0.629  0.171   0.709      STABLE
   24  1.000  1.000  0.483  0.520  0.399    0.624  0.176   0.706      STABLE

  최종: Ω=0.706 / STABLE / signed_gap=−0.176 (BALANCED)
  최종 진단: 배심원 오염 경고 (jury_bias_raw > 0.40)

분석:
  T·E는 8스텝 내 포화(1.0). 전관예우는 T·E 발현 자체를 막지 못한다.
  그러나 B(편향) 지속 상승(0.45→0.52) + P(절차) 지속 하락(0.70→0.40)
  → verdict_score 억제(0.62) → justice_gap ≈ 0.18 (FAIR 근접, DISTORTED 경계)
  → Ω_bias 하락, DISTORTED cap(Ω≤0.70)이 간헐적으로 작동
  → 구조 변수(B, institutional_resistance) 해소 없이 STABLE 고착


시나리오 B: 증거 조작(stp3) → 사법 개혁(stp12) → 위헌 심사(stp18)

  Stp      T      E      L      B      P  Verdict    Gap       Ω      Status
  --------------------------------------------------------------------------
    3  0.441  0.508  0.574  0.464  0.610    0.350  0.450   0.450     FRAGILE  ◀ 증거 조작
    4  0.414  0.546  0.557  0.468  0.586    0.344  0.456   0.450     FRAGILE
    8  0.354  0.666  0.516  0.483  0.515    0.335  0.465   0.450     FRAGILE
   12  0.407  0.759  0.497  0.266  0.585    0.464  0.336   0.592     FRAGILE  ◀ 사법 개혁
   16  0.751  0.855  0.488  0.173  0.686    0.659  0.141   0.753      STABLE
   18  0.952  0.890  0.658  0.133  0.775    0.801  0.001   0.852        JUST  ◀ 위헌 심사
   20  1.000  0.918  0.615  0.097  0.806    0.835  0.035   0.846        JUST
   24  1.000  0.959  0.567  0.035  0.869    0.869  0.069   0.842        JUST

  최종: Ω=0.842 / JUST / signed_gap=+0.069 (BALANCED)
  최종 진단: 배심원 오염 경고만 잔류

분석:
  증거 조작(stp3)으로 E 급락 → COMPROMISED(gap=0.45) → Ω cap≤0.45 → FRAGILE 고착
  사법 개혁(stp12): B 0.483→0.266 급락 → verdict_score 회복 → FRAGILE 탈출 준비
  위헌 심사(stp18): L ↑ + hierarchy_integrity ↑ → gap 0.336→0.001 → FAIR → JUST 달성
  → B 0.464→0.035 누적 해소, judicial_reform이 없으면 위헌 심사 단독으로 JUST 불가

핵심 인사이트:
  JUST 달성 = 단일 이벤트 불가. B(편향) 해소 + L(법리) 회복 연쇄 필수.
  B 해소(judicial_reform) 없이 constitutional_review만 적용하면 L이 올라도
  verdict_score가 bias에 의해 계속 억제된다.
```

---

## 사용

```python
import sys, os

# 60_APPLIED_LAYER를 sys.path에 추가 (패키지 루트)
sys.path.insert(0, "/path/to/60_APPLIED_LAYER")

from legal_engine import LegalEngine, JudicialEvent, observe, diagnose

# 한국 형사 시스템 24 스텝
engine = LegalEngine(preset="korea")
engine.simulate(steps=24)
engine.report()

# 최종 상태 확인
obs = observe(engine.state, engine.ctx)
print(f"Ω_global: {obs['Ω_global']}  판정: {obs['verdict']}")
print(f"justice_gap: {obs['justice_gap']}  방향: {obs['verdict_direction']}")
print(f"signed_gap: {obs['signed_justice_gap']}")
print(f"active_flags: {obs['active_flags']}")

# 방향성 플래그 확인
if obs['flags']['over_convicted']:
    print("⚠️  억울한 유죄 판결 위험")
if obs['flags']['unjust_acquittal']:
    print("⚠️  부당 방면 판결 위험")

# 시나리오 이벤트 주입
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

# 파라오 진단
advice = diagnose(obs)
for a in advice:
    print(a)
```

> **pytest 실행 위치**: `60_APPLIED_LAYER/` 디렉토리에서
> ```bash
> python -m pytest legal_engine/tests/test_legal.py -v
> ```

---

## 파일 구조

```
legal_engine/
├── __init__.py              — 공개 API (v0.2.0)
├── legal_state.py           — 상태·파생 지표·플래그(13개)·법률 계층·참여자 파라미터
├── legal_dynamics.py        — ODE 5개 + RK4 + 이벤트 충격 12종
├── legal_observer.py        — Observer 5레이어 Ω + 강제 임계치 + 방향성 진단
├── legal_engine.py          — 엔진 (preset·simulate·report·summary)
├── pharaoh_decree_legal.py  — 이벤트 12종 + Athena 자동 권고 우선순위 트리
└── tests/
    └── test_legal.py        — 65 테스트 (§1~§7 전체 PASS)
```

---

## 버전 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| **v0.2.0** | 2026-03-17 | 4단계·Observer 추상적 로직 보충보완. revolving_door_index 3요소 공식 통합(dynamics/state 불일치 해소), signed_justice_gap+verdict_direction 방향성 파생 지표 추가, 플래그 13개(over_convicted+unjust_acquittal), Ω_bias revolving 정규화 수정(max=1.0), DISTORTED 강제 임계치 추가(Ω≤0.70), dT/dt 배심 숙의 보조 항, diagnose() 방향성 처방 추가. 65 테스트 PASS |
| **v0.1.2** | 2026-03-17 | README 정밀화 — Ω_proc→Ω_procedural 표기 통일, 시나리오A 문장 교정, procedural_violation 이중 사용 구분 표시 |
| **v0.1.1** | 2026-03-17 | README 동기화 — 시나리오 A/B 실행 결과 갱신, ODE 수식 정오, jury_compromised weight 독립 계산, import 예시 수정 |
| **v0.1.0** | 2026-03-17 | 초기 구현 — 상태·동역학·Observer·이벤트·엔진, 52 테스트 PASS |

---

## 라이선스

MIT License.
