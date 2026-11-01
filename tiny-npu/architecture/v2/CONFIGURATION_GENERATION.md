# Job 1: 단일 파라미터 원본과 생성 체계

설정 원본은 [configs/revb/default.json](../../configs/revb/default.json)이다. `defaults`와 x1/x2/x4의 `scale_overrides`, parameter 설명을 함께 관리한다. [schema.json](../../configs/revb/schema.json)은 타입·필드 계약이며 기본값 원본이 아니다. `baseline_expected.json`은 이전 RevB 값과 비교하는 고정 테스트 fixture로, 생성기에 입력되지 않는다.

RevB `analyze.py`, parameter CSV와 생성기는 모두 `configuration.load_profile()`을 사용한다. 이전 FP32 R1/R2 생성기는 과거 RTL 재현용으로 유지하며 새 RevB 설정의 입력으로 사용하지 않는다.

## 실행

```bash
cd /workspace/TINY-NPU
source tiny-npu/scripts/env.sh
make -C tiny-npu generate-revb
make -C tiny-npu check-revb
# 파일을 수정하지 않고 원본과 생성물의 불일치 검사
python3 tiny-npu/tools/generate_revb.py --check
```

기본 산출물은 `tiny-npu/generated-revb/x1`, `x2`, `x4`에 생성한다. 각 폴더는 다음을 포함한다.

| 산출물 | 사용처 |
|---|---|
| parameters.json | 검증·파생 계산을 마친 설정 |
| tiny_npu_revb_config_pkg.sv | RTL이 import할 scalar/nested parameter 상수 |
| tiny_npu_revb_config.h | SW용 같은 상수와 hash |
| address_map.json | L0 region별 base/limit, bank/subbank geometry |
| model_input.json | parameters.json과 동일한 성능 모델 입력 |
| performance.json / REPORT.md | 해당 입력을 실제로 evaluate한 계획 성능 |
| parameters.csv | resolved 값과 설명 |
| parameter_coverage.json | 모델에 반영되는 필드와 향후 구현용 필드 구분 |
| rtl.f / config_smoke.sv / SRAM source | 생성 설정을 사용하는 isolated SRAM RTL |
| manifest.json | source·resolved 설정 hash, 산출물별 hash |

주소는 **NPU-local byte offset**이다. CPU MMIO base나 SoC system AXI decode가 구현된 주소로 해석하지 않는다. 모든 region은 연속·비중첩이며 마지막 exclusive limit은 L0 실제 용량과 같다. 10MiB처럼 2의 거듭제곱이 아닌 용량은 exact bounds 검사가 필요하다.

## 변경 방법

아래 명령은 원본 파일을 수정하지 않고 별도 실험 결과를 만든다.

```bash
# SRCA 경로만 128cycle: 해당 슬롯을 AUTO16으로 산정, 다른 경로는 유지
python3 tiny-npu/tools/generate_revb.py --scale 1 --lint \
  --set PATH_LATENCIES_CYCLES.SRCA=128 --out tiny-npu/build/revb-long

# MAC feedback 6cycle: context도 늘려서 II1 제약 충족
python3 tiny-npu/tools/generate_revb.py --scale 1 --lint \
  --set PATH_LATENCIES_CYCLES.FMA=6 --set MAC_ACC_CONTEXTS=8 \
  --out tiny-npu/build/revb-fma6
```

L0 용량은 `L0_REGIONS`의 bank/subbank/width/depth로 변경한다. 용량만 바꿀 때는 depth를 바꾸고, BW를 바꿀 때는 bank/subbank·II·clock을 별도로 조정한다. `L0_BYTES`, 주소폭, peak TOPS처럼 파생되는 값은 직접 override할 수 없다.

슬롯 입력 `0`은 AUTO 산정을 뜻한다. 경로별 왕복 지연·최대 sizing bound·MAC/L0 clock·context를 사용해 계산한다. 명시한 슬롯이 부족하면 AUTO 정책에서 생성 전에 거부한다. `FIXED8`은 의도적으로 credit stall을 평가할 때 사용하는 정책이며 II1/bubbleless를 보장하지 않는다. 256cycle 이상의 경우 local in-flight limit과 ID 폭도 함께 늘려야 한다.

스케일 선택은 명시된 override template을 적용한다. 기본 x1 값만 바꾼 뒤 x2/x4가 자동으로 같은 변경을 상속한다고 가정하지 말고, 생성된 resolved 값과 report를 검토한다.

## 제약과 검증

생성 전에 schema·타입·unknown key, geometry, single-port 조건, 역할 매핑, format, context/FMA 관계, slot/credit RTT, local ID 공간, AXI burst·ID·MO·buffer 및 요청 BW 상한을 검사한다. 유효한 source라도 실제 지속 10 TOPS에 부족할 수 있으며, 성능 pass/fail은 별도 평가한다.

테스트는 x1/x2/x4 기준값, 23개 잘못된 설정의 거부, nested override, L0 depth 변경의 용량·주소폭 전파, 생성 결과·manifest 재현성, 모델 입력 roundtrip, 생성 C header compile과 SV package 소비를 검사한다. 생성 RTL 시뮬레이션에서 기본16cycle, SRCA128cycle, L0 20MiB 설정의 데이터·응답 지연을 검사한다. 기존 single-port backpressure 회귀도 수행한다.

## 모델 적용 범위

모든 설정은 SV/C 상수로 전달하지만 모든 기능을 RTL로 구현한 것은 아니다. 모델은 경로 총지연 `PATH_LATENCIES_CYCLES`를 사용한다. 개별 stage breakdown은 구현 계획값이며 자동 합산되지 않는다. TC/OIC 세부 중재, SRAM physical timing, LUT 함수별 service, DMA FIFO의 실제 credit 동작은 후속 RTL 검증 대상이다. `parameter_coverage.json`을 참고한다.

현재 AXI 생성·모델 지원 폭은256bit이며 port 수를 조절한다. 다른 폭은 계약·모델·RTL 확장 후 사용한다. FP32 최종 저장과 TF32 container32 정책을 유지한다.
