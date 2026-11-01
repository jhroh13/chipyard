# Job 1 완료 보고

> 이 보고서의 성능 수치는 당시 DRAM 지연 정의를 사용했다. 최신 계약·계측 결과는 [Workload 검증](WORKLOAD_VERIFICATION.md)을 참조한다.

단일 원본 `configs/revb/default.json`과 `schema.json`, resolver, generator를 추가했다. RevB 모델의 이전 P0 profile 상속을 제거했고 JSON 입력을 모델·SV package·SW header·주소맵으로 함께 전파한다. 모든 생성물은 resolved configuration SHA256와 파일별 hash로 추적한다.

| 검증 | 결과 |
|---|---|
| x1/x2/x4 resolve 및 이전 기준 주요 값 비교 | PASS |
| x1/x2/x4 생성 SV package·SRAM wrapper lint | PASS |
| 잘못된 설정 23건 거부 | PASS |
| 원본과 생성물 불일치 검사 `--check` | PASS |
| 동일 입력의 byte-identical 재생성·manifest 검사 | PASS |
| generated parameters = model input, 모델 재실행 결과 일치 | PASS |
| 생성 C header compile / L0 주소 범위 연속·비중첩 | PASS |
| 생성 SV 소비: 10MiB / SRCA16cycle | PASS |
| 생성 SV 소비: 10MiB / SRCA128cycle·AUTO16slots | PASS |
| 생성 SV 소비: 20MiB / SRCA16cycle | PASS |
| 기존 SRAM backpressure 10/16/32/64cycle | PASS |
| 경로별 latency·clock·II 민감도 | 21건 및 지연 감소 검사 PASS |
| 이전 P0 model 회귀 | PASS, 이전 설계 기록으로 유지 |

128cycle 생성 RTL lint에서 procedural array loop에 대한 Verilator 제한을 발견해 SRAM transport stage를 generate로 명시했다. 변경 후 긴 경로와 기존 backpressure 회귀를 모두 통과했다.

생성된 x1/x2/x4 계획 TOPS는 각각 12.306098 / 24.879291 / 49.314824다. 각 profile의 기준 GEMM 크기도 달라지므로 동일 workload의 배속 비교로 해석하지 않는다. 실제 통합 RTL 측정이나 지속 10 TOPS 입증은 아니다.

전체 NPU datapath가 아니라 설정 package와 isolated SRAM wrapper까지 생성한다. TC/OIC, MAC, vector, AXI, RoCC 및 SoC 주소 매핑은 후속 Job이다. [Job 목록](JOB_LIST.md), [사용 방법·한계](CONFIGURATION_GENERATION.md), [테스트 결과 JSON](config_tests.json), [x1 생성 리포트](../../generated-revb/x1/REPORT.md).

재현:

```bash
source tiny-npu/scripts/env.sh
make -C tiny-npu generate-revb
make -C tiny-npu check-revb
python3 tiny-npu/architecture/v2/test_singleport.py
make -C tiny-npu model
```
