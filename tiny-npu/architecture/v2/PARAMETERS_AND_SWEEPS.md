# Current parameter and performance sweep guide

최신 native LQ16 FMA는11 arithmetic stages이며 gate-depth cap은40이다. 기본12contexts·32slots를 사용한다. [FMA 보고서](FMA_PIPELINE_REPORT.md), [단일 source](../../configs/revb/default.json), [resolved parameter CSV](parameters.csv)를 함께 참조한다.

Latency와II, 용량과BW는 별도 변수다. 모든 경로는 자체 clock domain을 갖는다. MAC operand read2cycle·feedback extra1cycle·TARGETR store1cycle은 명시적 integration 계획값이며 필요시 변경한다. L0↔RF 기본16cycle/설계bound32cycle은 그대로 독립적이다.

```bash
python3 tiny-npu/architecture/v2/sweep_l0.py \
 --l0-mib 2 4 6 8 10 12 16 --bank-factor 0.25 0.5 1 2 \
 --path-cycles 10 16 32 64 128 --axi-ports 1 2 \
 --slots-policy AUTO FIXED32 --bw-gbs 20
```

560개 구성의 계획 모델이다. Gate-depth 검증은 실제 합성 netlist에서 수행하며 성능 모델이 이를 대신하지 않는다. 아래 TOPS는 기존1GHz 참조 clock의 계산값으로 실제 주파수·지속 성능 증명이 아니다.

| Local cycles | Policy | RF slots | Group II | Planning useful TOPS |
|---:|---|---:|---:|---:|
| 10 | AUTO | 32 | 32.00 | 10.793 |
| 10 | FIXED32 | 32 | 32.00 | 10.793 |
| 16 | AUTO | 32 | 32.00 | 10.772 |
| 16 | FIXED32 | 32 | 32.00 | 10.772 |
| 32 | AUTO | 32 | 32.00 | 10.716 |
| 32 | FIXED32 | 32 | 32.00 | 10.716 |
| 64 | AUTO | 32 | 32.00 | 10.607 |
| 64 | FIXED32 | 32 | 32.00 | 10.607 |
| 128 | AUTO | 32 | 32.00 | 10.394 |
| 128 | FIXED32 | 32 | 32.00 | 10.394 |

Context12의 최소 이중 buffer가24slots이므로 기본은 power-of-two32slots다. 이 범위에서는 AUTO와FIXED32가 같을 수 있다. 더 긴 경로를 검사할 때는 ID/in-flight 한도도 명시적으로 늘린다.

```python
from configuration import load_profile
from sweep_l0 import evaluate
p = load_profile(overrides={
 'PATH_LATENCIES_CYCLES': {'SRCA':512,'SRCB':512,'SRCC':512,'TARGETR':512},
 'LOCAL_MAX_INFLIGHT_VECTORS':512, 'LOCAL_VECTOR_ID_BITS':9})
a = evaluate(config=p,slots_policy='AUTO')     #64slots
b = evaluate(config=p,slots_policy='FIXED32')  #32slots; credit stalls
```

경로별 지연은 `per_path`로 따로 override할 수 있다. Operand/feedback/store 경로 변경은 canonical parameter로 반영한다. FIFO·counter·byte credit·bank conflict·physical wire 검증은 후속 통합 RTL에서 수행한다.

Register/PE 자원은 L0 밖이다. FMA latency를11보다 작게 설정하면 생성이 거부된다.11보다 큰 값은 추가 output transport이며 산술 stage가 더 분할됐다는 뜻이 아니다. 새 latency는 gate audit 증거를 생성해야 하며 contexts≥FMA+feedback extra여야 한다.
