# RevB 실행 Job List

순서는 의존 관계를 기준으로 한다. 각 단계에서 모델 예상, RTL 기능 검증, RTL 성능 측정, 합성 결과를 구분한다.

| Job | 작업 | 산출물·완료 기준 | 상태 |
|---:|---|---|---|
| 1 | 단일 파라미터 원본과 생성 체계 | JSON/schema, 제약 검증, SV package, C header, L0 주소맵, 모델 입력·리포트, 공통 hash 및 변경 전파 테스트 | 완료: 아래 검증 범위 참조 |
| 2 | 수치 연산 계약과 독립 golden 검증 강화 | MXFP4/MXINT8 scale, LQ16/TF32 per-FMA, C 입력 변환, NaN/Inf/underflow/rounding/tail 정의; 작은 matmul golden | 기존 reference 기반 확장 예정 |
| 3 | TC/OIC·slot·credit RTL 및 검증 환경 | 32×32 주소 생성, atomic multi-acquire, epoch/slot-generation, 전체 commit 후 publish, randomized backpressure/deadlock 검증 | 예정 |
| 4 | L0 single-port subbank fabric·register 경로 | VOQ/중재/reorder/bitmap, 동시 R/W, 경로별 지연·II/clock sweep, BW와 stall 계측 | primitive 검증 완료; fabric 예정 |
| 5 | 대표 MAC·vector 경로 초기 합성 | LQ16/TF32 FMA의 latency/II/면적/타이밍; context·slot·credit 재산정 | 예정 |
| 6 | MAC·SRCA/B/C·TARGETR RTL 통합 | 32×32 matmul·다중 K·tail, golden 비교, pipeline/feedback/결과 burst 검증 | 새 구조 통합 예정 |
| 7 | AXI DMA·DRAM 모델 통합 | 256bit 다중 port, MO/byte-credit/4KiB split, 700ns 범위 명시, 공유 BW·turnaround·효율 중복 적용 방지 | 예정 |
| 8 | Vector·8 Rocket·role별 RoCC 통합 | LUT/activation/TF32→FP32, 명령 권한·descriptor, 실제 producer/consumer 실행 | 예정 |
| 9 | End-to-end simulation·성능 평가 | RoCC 수락→최종 write B, useful TOPS, 정확도, path BW·stall, latency/II/용량/clock sweep | 예정 |
| 10 | 합성·성능 교정 및 자동 리포트 | 모델↔RTL 차이 분석, 지속≥10 TOPS 판정, x2/x4 성능·자원·BW 확대 가이드 | 예정 |

Job 1의 RTL 산출물은 설정 package와 isolated SRAM wrapper이다. 새 MAC/TC/OIC/AXI/RoCC 전체 RTL을 생성하거나 지속 10 TOPS를 입증한 것은 아니다. [실행·검증 안내](CONFIGURATION_GENERATION.md), [완료 보고](JOB1_REPORT.md), [검증 결과](config_tests.json).
