# LAW — 법정 동역학 시뮬레이션 레포지토리

> **Qqarts co. / qquartsco-svg**
> ENGINE_HUB 60_APPLIED_LAYER → 독립 배포 레포

---

## 포함 엔진

| 엔진 | 버전 | 설명 |
|------|------|------|
| `legal_engine` | v0.1.1 | 법정 동역학 — 판사·검사·변호사·배심원·피고인 5축 ODE 시뮬레이션 |

---

## 빠른 시작

```bash
pip install pytest
python -m pytest legal_engine/tests/test_legal.py -v
```

```python
import sys
sys.path.insert(0, ".")          # LAW/ 루트에서 실행 시

from legal_engine import LegalEngine, JudicialEvent

engine = LegalEngine(preset="korea")
engine.simulate(steps=24)
engine.report()
```

---

## 라이선스

MIT License.
