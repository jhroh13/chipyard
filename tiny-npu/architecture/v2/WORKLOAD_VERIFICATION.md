# Workload trace·bubble 검증·DRAM·초기 합성

요청한 선행 검증 도구를 구현하고 실행했다. 다음을 구분한다.

| 범위 | 현재 상태 |
|---|---|
| Passive RTL performance monitor와 JSONL/VCD 분석 도구 | 구현·검증 |
| 실제 single-port SRAM의 latency·bank/credit/OIC/consumer 주입 fixture | 16/64/128cycle 데이터·counter 대조 통과 |
| AXI ready/valid·ID·burst·MO·turnaround·재정렬 모델 | Python cycle-level traffic agents, protocol 검사 통과 |
| 실제 8 Rocket·새 MAC array·AXI DMA 전체 연결 | 아직 미구현; 이 도구의 후속 연결 대상 |
| LQ16 FMA 초안 및 scalar feedback matmul | RTL 기능 검증·generic 초기 합성 수행 |
| PDK 면적·STA·1GHz·지속 10 TOPS | 아직 미확인 |

## 1. 실행과 다운로드 산출물

```bash
source tiny-npu/scripts/env.sh
make -C tiny-npu verify-environment  # protocol/latency/효율/원인 분류 + 비교 실험
make -C tiny-npu workload            # trace / VCD / HTML / JSON / report / ZIP
make -C tiny-npu trace-rtl           # 실제 SRAM fixture + passive monitor + VCD
make -C tiny-npu numeric-prototype   # LQ16 FMA 및 32x32 feedback 연산
```

`tiny-npu/build/workload/analysis/workload.html`을 브라우저로 열면 인터넷 없이 사용한다. 채널 filter, 시간 구간, zoom/pan, hover, bubble 행 클릭을 지원한다. waveform은 동일 상태의 연속 sample을 lossless RLE로 묶으며 `period_ps`, `repeat_count`, `duration_ps`를 표시한다. 요약 통계는 압축 전 sample 전체에서 계산한다.

| 파일 | 의미 |
|---|---|
| trace.jsonl.gz | 시간·domain period·valid/ready·ID·bytes·stall·event 원본 |
| waveform.vcd.gz | JSONL의 valid/ready/active/stall waveform; 압축 해제 후 GTKWave 등 사용 |
| analysis/workload.html | 분석 가능한 offline waveform UI |
| analysis/summary.json | 채널별 시간·전송·BW·bubble·개선 후보 |
| analysis/axi_transactions.json | ID별 read, 포트의 AW/W 순서로 연결한 write latency |
| analysis/bubbles.json | 시작/끝/채널/원인이 있는 bubble 구간 |
| analysis/chrome_trace.json | Chrome trace/Perfetto 호환 구간·event |
| analysis/REPORT.md | 사람이 읽는 분석 결과 |
| results.json | AXI/축소 local fixture 결과 및 provenance |
| workload-artifacts.zip | 위 파일 묶음 |

실제 RTL fixture는 `build/bubble-rtl-{16,64,128}`에 `rtl_trace.jsonl`, 실제 DUT 신호가 있는 `bubble.vcd`, compile/simulation log와 동일한 분석 결과를 남긴다.

## 2. Passive performance monitor와 연결

[RTL monitor](../../rtl/tiny_npu_trace_monitor.sv)는 ready/valid를 구동하지 않는다. 실제 clock edge에서 관찰하고 synthesizable counter를 증가시킨다. 파일 출력은 simulation-only다.

- Rocket별 control valid/ready, memory request/response valid/ready·source/opcode/address, I-cache 요청/ready/miss, D-cache miss, retire를 입력으로 받는다.
- Hart별 `hart_period_ps`와 clock을 받는다. 서로 다른 주파수의 cycle을 직접 더하지 않는다.
- AXI 포트별 AR/R/AW/W/B, ID, ARLEN/AWLEN, 주소, LAST와 WSTRB를 기록한다. 현재 데이터 모델은256bit full-width burst다.
- MAC active/valid/ready, 명시적으로 검증된 useful ops, stall mask를 입력으로 받는다.
- configuration hash와 provenance를 trace header에 기록한다.

`mac_useful_ops`에는 padding을 제외한 실제 연산만 넣는다. 축소 traffic fixture는 arithmetic을 하지 않으므로 useful ops를0으로 두며, 별도 `capacity_ops`는 scheduler의 가상 용량 태그다. 이를 실제 TOPS로 보고하지 않는다.

실제 Rocket 연결 시 RoCC command/response, TileLink A/D 또는 선택한 cache CPU interface를 정확히 지정한다. memory response의 ready가 없는 interface는 ready=1로 두고 그 의미를 기록한다. retire와 cache event를 실신호에 연결하기 전에는 IPC/cache 개선을 실증했다고 하지 않는다. 상세 연결 계약은 [PROBE_BINDING.md](../../verification/PROBE_BINDING.md)를 따른다.

`TRACE_START_PS`, `TRACE_END_PS`(0=무제한), `TRACE_HART_MASK`/`TRACE_AXI_MASK`(hex), `TRACE_MAC_ENABLE` plusarg로 capture 구간·채널을 선택할 수 있다. Counter는 전체 실행을 세며 capture window와 구분한다. 기본은 모든 sample이며 암묵적 decimation을 하지 않는다.

현재 RTL fixture에서 request는 실제 SRAM arbitration에 연결되지만 hart/MAC는 synthetic probe이며, AXI와 Rocket memory response는 미연결이다. 비활성 채널은 회색으로 표시한다. 별도 behavioral workload에서 AXI 전체 채널과8개 control/cache agent를 구동한다. 이 둘은 하나의 연결된 NPU가 아니다.

## 3. Bubbleless 검증과 원인 분류

| Bit | 원인 | 관찰할 근거 |
|---:|---|---|
|0|wait-data|입력 slot completion bitmap·ready sequence·load 완료|
|1|no-credit|free slot·destination/byte credit·반환 RTT|
|2|bank-conflict|같은 physical subbank의 동시 요청·R/W 중재|
|3|OIC-conflict|counter bank/atomic issue 경쟁·event FIFO|
|4|consumer-stall|결과/응답 valid 동안 ready=0|
|5|control-starved|작업은 있으나 control 발행 기회 부족|
|6|cache-miss|실측 cache miss와 control stall의 상관|
|7|memory-wait|주소 요청·payload·완료 대기|

Raw cause는 중첩될 수 있다. Primary cause는 낮은 bit 우선으로 하나만 선택하며 합은 bubble 시간과 일치한다. 모든 원인에 대해 channel/time interval을 보존한다. 원인 bit는 실제 RTL 조건에서 만들어야 하며 monitor 자체가 원인을 추측하지 않는다.

검증은 fixed latency10/16/64/128cycle, 요청별 jitter, 물리 subbank alias, 제한된 read credit, consumer stall, OIC 주입, AXI cross-ID reorder를 포함한다. 같은 ID의 순서와 포트별 W 순서를 유지한다. 전체 TC/OIC의 atomicity/epoch/deadlock 검증은 Job3에서 실제 RTL을 연결해 확장한다.

## 4. DRAM 700ns 정의

Read의 명목 기준은 **ARVALID&&ARREADY → 첫 RVALID&&RLAST**다. RLAST를 수락하는 최종 handshake까지의 시간도 별도로 기록한다. burst service 시간은700ns에 포함하며, 경합·jitter·backpressure가 있으면 관측 지연이 늘어난다. 따라서700ns를 first-data 대기 뒤에 다시 burst 시간으로 더하지 않는다.

Write는 **첫 AWVALID → 첫 WVALID**의 명목 준비 지연을700ns로 둔다. 이 지연은 master/DMA의 데이터 준비 모델이며 DRAM이 WVALID를 구동한다는 뜻이 아니다. **WVALID는 AWREADY와 독립**이다. AW handshake→WVALID도 함께 보고하며, AW 수락이 늦으면 이 값은 음수가 될 수 있다. AXI상 허용된 동작이다. AWREADY를1.6µs 지연시킨 테스트에서도 WVALID가 약700.8ns에 먼저 올라가는 것을 검증했다.

B는 WLAST 이후 별도32ns 기본 응답 모델이다. 사용자 지정700ns를 B tail로 재사용하지 않는다. B 지연은 변경 가능하고 실제 memory controller로 교정해야 한다.

- `bandwidth_mode=effective`: 이미 효율을 반영한20GB/s를 그대로 사용. 추가0.6 곱셈 없음.
- `bandwidth_mode=raw`: raw33.333…GB/s에0.6을 **한 번** 적용.
- 두 모드의 동일 seed 결과를 비교해 중복 적용을 검사한다.
- shared R+W service, 방향 전환4 AXI cycles, 포트별 read/write MO,128/512/2048/4096B burst, R/B backpressure와 cross-ID reorder를 반영한다.
- Write payload는 포트별 AW 순서를 따른다. AXI4 W에는 WID가 없으므로 JSON의 behavioral W ID는 분석용 tag이며 실제 wire가 아니다.
- 현재 보수적 shared service 구현 상한은 AXI clock당256bit beat 하나다.625MHz에서20GB/s이며, 더 큰 service는 모델의 병렬 service 확장이 필요하다.

20GB/s는 baseline service budget이다. 명시적 turnaround·추가 consumer stall 주입은 그 이후의 stress 비용이므로 관측 BW는 더 낮다. 같은 overhead를 baseline 효율과 explicit 주입에 동시에 포함시키려면 calibration에서 한쪽을 제거한다. 실제 controller/DRAM의 bank/refresh/row timing을 모두 구현한 모델은 아니다. AXI 모델은 data word 내용 대신 ID·beat/LAST·시점·metadata 안정성을 검증하며 실제 payload 정확성 검증은 후속 DMA RTL 연결에서 추가한다.

`verification.json`의 null 값은 canonical hardware profile에서 상속한다. non-null 값은 명시적 stress override다. 이전 R1/R2 모델은 과거 지연 정의로 보존하고, RevB event model은 새 모드를 선택한다. Cycle-level trace 결과가 정밀 검증의 근거이며 event model은 근사다.

## 5. 초기 합성과 다음 gate

```bash
python3 -m pip install --target tiny-npu/build/synth-tools -r tiny-npu/synthesis/requirements.txt
make -C tiny-npu synth-initial
```

Native Yosys 또는 workspace-local YoWASP Yosys를 사용한다. [합성 결과 JSON](synthesis_results.json)에 source hash와 도구 버전을 남긴다. 표준 cell library·PVT·SRAM macro mapping이 없으므로 generic cell 수와 논리 깊이만 보고한다. 면적µm², critical path ns, Fmax는 null이다.

LQ16 exact FMA는 기능 기준 RTL이다.4cycle transport 뒤에 조합 연산을 두었으므로 실제4단 산술 pipeline이 아니다. Generic mapping 후12,821 bit-cell, topological depth438로 나왔다. 이 상태를10,240 PE에 그대로 복제하지 않는다. 제한된 significand 경로·sticky 처리·균형 leading-zero/normalization 구조와 실제 arithmetic stage 분할을 설계하고 exact reference와 동치 검증해야 한다.

SRAM은256×1024 bits, 추상 memory의 logical read/write 각1port가 추론됐다. command는 R 또는 W 하나만 수락하므로 물리적으로 동시1R1W를 요구하지 않는다. Macro mapping은 미완료다.16cycle 설정의 memory 외 transport register는3,856bits이다.

후속 acceptance는 실제 PDK liberty·SRAM timing model로 mapping/STA를 수행한 뒤 FMA latency/II, context, register slot, credit을 다시 산정하는 것이다. [참조 SDC](../../synthesis/reference.sdc)는1GHz 목표용 초안이며 signoff constraint가 아니다.

## 6. 다음 stage 진행

도구 준비 후 LQ16 FMA4/6cycle에서6,000개씩 검사했고, scalar FMA의 실제 결과 feedback·4context interleave·backpressure로32×32의 zero/identity/random K32와 random-scale K64를 검사했다. 총163,840개 FMA 결과가 golden과 일치했다. MX decode/scale은 host가 수행하므로 새 MAC array/decoder/TF32 store 통합을 의미하지 않는다.

Job2는 이 기준을 사용한 수치 계약·최적화 RTL 검증을 계속한다. Job3 이후 TC/OIC·fabric·실제 Rocket/AXI를 같은 trace 계약에 연결해 bubble 및 개선 후보를 실제 시스템 데이터로 교정한다. [실행 결과와 판단](WORKLOAD_REPORT.md), [Job 목록](JOB_LIST.md).
