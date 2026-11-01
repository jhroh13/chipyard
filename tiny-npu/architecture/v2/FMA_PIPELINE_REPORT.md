# FMA pipeline 최적화·40-gate 제약 검증

**합격 기준은 각 register stage의 조합 논리 깊이≤40 gate다. 주파수 달성 여부로 대체하지 않는다.**

Gate basis는2-input AND/OR와 NOT이다. XOR/MUX, flop enable·synchronous reset mux를 모두 이 gate로 분해하고 plain DFF에서 경로를 끊었다. Unknown cell, combinational cycle, 숨겨진 enabled/reset flop은 검사 오류다.

## 합성 결과

| 구성 | 최대 gate depth | 조합 gate 수 | Register bits | 판정 |
|---|---:|---:|---:|---|
| 이전 wide reference,4 transport stages | 583 | 19,252 | 68 | FAIL |
| 새11 arithmetic stages +0 output stages | 39 | 5,407 | 543 | PASS |
| 새11 arithmetic stages +2 output stages | 36 | 5,538 | 577 | PASS |

Pipeline11의 stage별 최대값:

| Stage | 연산 | Depth |
|---:|---|---:|
| 1 | decode/classify +9×5/9×4 partial products | 39 |
| 2 | exact product recombination | 29 |
| 3 | product/C normalization | 24 |
| 4 | normalized exponent correction | 23 |
| 5 | magnitude ordering / exponent distance | 29 |
| 6 | sticky right alignment | 17 |
| 7 | prefix add/sub | 39 |
| 8 | sum normalization | 26 |
| 9 | sum exponent correction | 18 |
| 10 | subnormal alignment + rounding predicate | 25 |
| 11 | RNE increment / format pack | 28 |

Valid/reset/hold 제어는 최대6단, module output 제어는 최대4단이다. Register-to-register 경로뿐 아니라 primary input/output, reset/hold용 조합 논리도 포함했다. Wire/fanout/clock tree/PDK delay는 이 구조적 수치에 포함하지 않는다.

이전438단 수치는 XOR/MUX를 한 cell로 세고 enabled flop을 primitive로 남긴 초기 결과다. 이번 표는 기존/신규 모두 더 엄격한 같은 AND/OR/NOT + plain-DFF 조건으로 다시 합성한 결과다. 서로 다른 gate basis의 수치를 직접 비교하지 않는다.

## 수치·흐름 검증

- 고유 입력262,144개: 모든16-bit encoding의 multiply-by-one/add-to-zero,256×256 mantissa product grid, NaN/Inf/subnormal, cancellation-neighbor, random을 포함했다.
- 정확한 Fraction RNE 및 기존 wide RTL과 총786,422개 결과가 일치했다. Reset에서 취소한10개 in-flight 입력은 별도로 집계했다.
- 연속 valid, valid gap, output backpressure·hold, reset flush,11/13cycle latency를 검사했다.
- 실제 결과 feedback의32×32 K32/K64 테스트: useful FMA 229,376건, masked tail 포함230,656건 PASS. Context12/latency11 및 context16/latency13을 검사했다.
- Per-stage valid/ready trace, VCD와 offline HTML을 `build/lq16-pipe-*/analysis`에 생성했다. Trace의 test clock은100MHz이며 이를 물리 Fmax나 전체 NPU TOPS로 해석하지 않는다.

## 변경한 구조

272-bit fixed-point 정렬·부호 반전·wide absolute value를 제거했다.18-bit exact product와9-bit C significand를32-bit normalized window에 정렬하고, 작은 항의 tail은 sticky로 보존한다. 큰 항의 크기·sign을 먼저 정해 unsigned add/sub를 수행한다.

지수가 가까워 cancellation이 큰 경우18/9-bit significand 전체가 window 안에 있어 정확하다. Tail이 잘리는 큰 exponent gap에서는 심한 cancellation이 없고, guard/sticky 아래의 정보만 손실된다. Post-normalization 후 subnormal 정렬과 단 한 번의 fused RNE를 수행한다. 이는 FP32 accumulator가 아니다. 전체48-bit 입력 조합의 formal equivalence 증명은 아직 수행하지 않았다.

## 파라미터·데이터 이동 영향

| Parameter | 현재 값 |
|---|---:|
| FMA arithmetic / total cycles | 11 / 11 |
| Explicit PE feedback extra | 1 |
| Accumulator contexts | 12 |
| SRCA/B/C/TARGETR slots | 32 each |
| Near-RF bytes,10 arrays | 3,133,440 |
| PE accumulator bytes,LQ16 | 245,760 |
| Near operand read / TARGETR store planning latency | 2 / 1 cycles |

Contexts≥FMA latency+explicit feedback 여유이다. 기본12=11+1이며32-slot RF는12-context burst와 이중 buffering을 수용한다. L0↔RF latency는 별도이며1cycle로 가정하지 않는다. Cold prefill은12×32=384 MAC cycles를 명시적으로 모델에 더했다. Near RF·PE 상태는 L0 용량 밖의 추가 자원이다.

기존1GHz 참조 clock을 그대로 가정한 계획 모델은 vector 포함10.772 useful TOPS다. 이 수치는 실제 주파수 또는 지속10 TOPS의 증명이 아니다. 이번 합격 근거는 gate-depth와 기능 검증이다.

## 생성·회귀 및 다음 단계

Canonical JSON에서 profile·SV/C·모델을 생성하고, native LQ16 FMA wrapper도 연결했다. Source hash가 다르거나 선택 latency의 합성 증거가 없거나40단을 넘으면 생성/CI가 실패한다. TF32 arithmetic은 아직 구현되지 않았으며 해당 mode에서는 LQ16 FMA를 조용히 대신 생성하지 않는다.

```bash
source tiny-npu/scripts/env.sh
make -C tiny-npu check-fma-depth
make -C tiny-npu test-fma-pipe
make -C tiny-npu generate-revb
make -C tiny-npu check-revb
```

현재 단계에는 추가 사용자 입력이 필요하지 않다. 다음 array 연결에서는 operand RF mux·feedback·TARGETR conversion·scheduler를 포함한 stage budget을 다시 검사하고, 늘어난 RF/PE 자원 예산을 평가해야 한다. 실물 면적·delay를 평가할 때만 실제 library/PVT/물리 조건이 추가로 필요하다.

[Gate 측정 JSON](fma_gate_depth.json) · [수치 JSON](lq16_pipe_tests.json) · [Feedback JSON](lq16_pipe_tile_tests.json) · [RTL](../../rtl/tiny_npu_lq16_fma_pipe.sv)
