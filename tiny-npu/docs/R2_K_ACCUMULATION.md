# R2: K-block FP32 누산 및 stream GEMM

현재 구현은 K=32 tile 결과들을 K 순서대로 FP32 누산하는 stream-fed GEMM이다. CPU L1/L2나 AXI DMA를 거치지 않고 testbench가 벡터를 직접 공급한다. 기본10배열의 완전한8MiB 메모리 subsystem이나 지속10TOPS 실증은 아니다.

## 구현 모듈

| Module | 기능 |
|---|---|
| tiny_npu_fp32_add_pipe | unpack/align → add/subtract → normalize → RNE round/pack의 실제4단계파이프라인 |
| tiny_npu_k_accumulator | lane당32-depth C SRAM, K그룹별 FP32누산, row scoreboard, 마지막K에서만출력 |
| tiny_npu_gemm_stream | job당K-block 수와ID를수락하고R1 core와C accumulator를연결 |
| tiny_npu_dma_burst_planner | 주소/길이를최대burst/4KiB경계로분할. 실제AXI master아님 |
| tiny_npu_dma_read_credits | outstanding ID와RX byte공간을동시에예약·반환. 실제DMA datapath아님 |

FP32가산기는RNE,gradualunderflow,±0,∞,canonicalqNaN을처리한다. IEEE exception flags와다른rounding mode는현재미지원이다. Globalelastic enable로출력stall시모든stage와tag를유지한다. 무stall조건에서latency4cycles,II1을검사한다.

C SRAM은현재lane별32-bit×32word,1-cycle동기read/1R1W이다. 이는전체256-bitbanking의전단계slice이다. First-K에서는이전C메모리를읽은값대신+0을사용하므로새job의C를물리적으로clear할필요가없다. Scoreboard는동일row의writeback전재발행을막는다.

## Job·stream 계약

- `job_valid/job_ready`, `job_k_blocks`(1..65535), `job_id`로작업시작. 한job씩실행한다. 0-block명령은지원하지않으며호스트가거부해야한다.
- 각배열은32×32출력을담당한다. 전체K는32×job_k_blocks이며M/Ntail은아직없다.
- 입력순서: K블록0의32벡터 → 블록1의32벡터 → … . 각블록첫벡터에서해당scale과active-mask를수락한다.
- 여러K블록에서동일배열에대응하는출력tile좌표를유지해야한다. 배열재배치는다음job에서한다.
- 각블록정수dot에scale을적용한FP32값을만들고, 매FP32add마다RNE로round한다. Blockscale을마지막에한번만적용하지않는다.
- 출력은마지막K블록의누산이완료된32개의rowchunk이다. lane=array_id×32+column. out_tile_id=job_id.
- inactive배열의해당블록기여분은0이다. 모든블록에서비활성이면전체결과0이다.
- reset은작업·scoreboard·valid를폐기한다. C저장소는reset하지않는다. 다음작업의first-K규약으로초기화한다.

## DMA 전단 계약

Planner는beat정렬시작주소만수락하고zero-length를no-op으로완료한다. 5000B를0xFC0에서전송하면64B@0xFC0,4096B@0x1000,840B@0x2000으로분할한다. 마지막read는ceil(bytes/beat)만큼물리전송하므로padding공간도예약해야한다. `plan_done`은request생성완료이며job/DMA완료가아니다.

Credit의`issue_bytes`는payload가아니라실제RX에예약할전송byte수이다. 최종beat의padding까지포함해야한다. `retire_valid`는전체response가버퍼에서배출된후에만올린다. FirstRbeat에서credit을돌려주면안된다. MO가남아도byte공간이없으면issue를막는다. 같은cycle의retire+issue와ID재사용을지원하고미할당ID의반환은fault로기록한다.

실제AR/R/AW/W/B,burstcounter,reorderbuffer,descriptorfetch,에러abort,CDC,AXI종료까지의job완료는후속R4작업이다.

## 재현

```bash
cd /workspace/TINY-NPU/tiny-npu
source scripts/env.sh
make extended                      # 기본 1/2/10배열
make extended EXT_ARRAYS="1 2"      # 빠른 회귀
make dma-frontend
make generate-gemm
make lint-gemm                     # 기본10배열stream wrapper
```

초기R1의`make test`는유지한다. GeneratedR1tile과R2GEMM wrapper는각각다른디렉터리이므로구현범위를혼동하지않는다.

## 다음 통합 순서

1. C slice를목표bank폭/전체용량/2-cycleread로확장하고SRAMlatency상응pipeline·FIFO를구현한다.
2. DMAplanner/credit를실제AXIread/write engine과연결하고700nslatency·reorder·backpressure·errors를검증한다.
3. Jobdescriptor·주소보호·RoCCwrapper를추가하고CPUcache우회데이터경로를확인한다.
4. 1024×1024×4096의첫DRAMload부터최종writeB완료까지≤858.993µs인지RTL로검사한다.
5. 그후MLP/TinyDecoder연결과LLMprefill/decode품질·성능측정을진행한다.
