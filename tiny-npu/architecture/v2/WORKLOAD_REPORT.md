> 이 문서의 수치·fixture는 이전 baseline 기록이다. 최신 native FMA·자원 설정은 [FMA pipeline 보고서](FMA_PIPELINE_REPORT.md)를 참조한다.

# Workload 선행 검증 결과와 판단

이 보고서는 실제 SRAM RTL fixture, behavioral AXI/control agents, scalar FMA RTL의 결과를 구분한다. 전체8-Rocket NPU의 측정 결과가 아니다.

## 검증 결과

| 항목 | 결과 |
|---|---|
| Protocol/latency/효율/trace test | 16건 PASS |
| 실제 SRAM+monitor | 16/64/128cycle PASS;4종 stall 원인 모두 관찰·counter 대조 |
| Offline viewer | draw/zoom/filter/bubble-focus smoke test PASS |
| LQ16 FMA unit | 6,000 vectors ×4/6cycle, backpressure PASS |
| Scalar32×32 feedback | 163,840 FMA 비교 PASS, K32/K64 |

## AXI 결과

| 조건 | 관측 aggregate payload |
|---|---:|
| mixed burst128/512/2048/4096B, R/W각24개 | 16.168 GB/s |
| 4096B, R25개/W16개, payload25:16 | 17.075 GB/s |

모두20GB/s effective shared service에서 추가 turnaround/consumer stall을 주입한 결과다. 측정 BW가20GB/s에 못 미치므로 이를20GB/s 보장 증명으로 쓰지 않는다. 실제 DRAM/AXI RTL과 연결한 측정도 아니다.

기본 trace의 cross-ID read overtakes는 21건이다. ID별 beat 수·RLAST·포트별 W 순서와 backpressure 중 valid/payload 안정성을 검사했다. Unloaded AR→RLAST와 AWVALID→WVALID는 약700.8ns이며 AXI625MHz의 clock 양자화를 포함한다. AWREADY를1.6µs 지연시켜도 WVALID는 독립적으로 먼저 발생한다. B는 별도32ns 모델이다.

## Bubble 개선 우선순위

| 비교 조건 | 완료 token | Scheduler utilization | Source bank conflicts |
|---|---:|---:|---:|
| baseline | 108 | 85.77% | 351 |
| latency64_slots2 | 42 | 33.74% | 126 |
| latency64_slots8 | 107 | 85.94% | 338 |
| latency128_slots8 | 95 | 77.08% | 299 |
| latency128_slots16 | 103 | 84.23% | 373 |
| bank_skew | 109 | 86.30% | 0 |
| subbanks8_linear | 108 | 85.77% | 351 |
| rocket_half_clock | 107 | 84.57% | 346 |
| rocket_double_clock | 108 | 85.77% | 351 |
| icache16KiB_same_miss_trace | 108 | 85.77% | 351 |
| ideal_no_cache_miss | 111 | 87.35% | 366 |
| ideal_no_consumer_stall | 124 | 98.07% | 410 |

이 표는 축소 fixture에서 같은 실행 길이로 비교한 값이다. 실제 칩의 TOPS나 cache capacity별 miss 예측이 아니다.

1. 이 fixture에서는 consumer stall 감소가 우선이다. Source를 더 빠르게 만드는 것보다 결과 drain/vector/AXI downstream을 먼저 계측한다.
2. 긴128cycle 경로에서 slots8→16은 완료 token95→103으로 개선됐다. 실제 경로의 credit RTT와 slot high-water를 확인해 적용한다.
3. subbank 수4→8만으로 stride alias는 해소되지 않았다. Skew mapping은 충돌을0으로 줄였지만 처리량 개선은 작다. 숨겨진 충돌을 줄이는 것과 전체 병목을 줄이는 것을 구분한다.
4. Control-agent clock2배는 이 fixture에서 처리량 개선이 없었다. 실제 Rocket control valid/ready·retire·cache miss 자료가 없으면 코어 주파수 증설을 우선하지 않는다.
5. I-cache8→16KiB만 바꿔도 miss trace는 그대로다. 도구가 cache 용량 증가에 따른 성능을 임의로 만들어내지 않는지 검사한 것이다. 실제 cache size 효과는 Rocket 실행으로 검증한다.

## 초기 합성 판단

LQ16 exact FMA의 ABC simple bit-cell 수는 **12,821**, combinational topological depth는 **438**이다. 이 수치는 NAND2-equivalent나µm²가 아니며438단에 임의 gate delay를 곱해 Fmax를 추정하지 않는다.

현재4cycle은 산술 뒤 transport latency다. 실제 산술4단 pipeline이 아니므로, 배열 복제에 앞서 significand alignment·sticky·adder·normalization·rounding을 분할하고 정규화 경로를 균형화해야 한다. PDK liberty/PVT와 SRAM timing model이 없어 areaµm²·critical path ns·Fmax는 미확인이다.

SRAM256×1024는 262,144bits 추상 memory로 남았고,16cycle transport register는 3,856bits다. Logical read/write 각1port는 mutually-exclusive command 구조이며 동시 physical1R1W를 의미하지 않는다.

## 다음 stage 및 미완료 gate

준비 후 Job2의 LQ16 수치 RTL·실제 feedback 검증까지 진행했다. MX decode/scale은 host 입력 준비이며 full MAC array·TF32 arithmetic/store 통합은 남아 있다. 다음은 최적화 FMA의 수치 동치/산술 pipeline, 실제 TC/OIC 및8 Rocket/AXI probe 연결이다.

**지속10 TOPS는 아직 확인되지 않았다.** 이를 판정하려면 실제 통합 DUT의 RoCC accept→최종 B까지 useful ops와 시간을 연결하고, PDK STA의 clock 조건을 만족해야 한다. 현재 traffic-agent workload는 useful ops를0으로 기록한다.

[실행 방법·형식·한계](WORKLOAD_VERIFICATION.md) · [JSON 요약](workload_summary.json) · [개선 비교 JSON](workload_sweeps.json) · [합성 JSON](synthesis_results.json)
