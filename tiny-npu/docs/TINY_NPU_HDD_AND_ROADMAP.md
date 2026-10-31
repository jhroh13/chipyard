# TINY NPU — Overview, HDD, RTL 및 LLM Simulation 실행 계획

기준일: 2026-11-01, Asia/Seoul. 기반: jhroh13/chipyard commit `262423bacd0b8bf65b4f628da4cceac28549e540`.

## 1. Overview

TINY NPU 는 4-core RV64 Rocket 시스템에 연결할 MXFP4(E2M1) × OCP MXINT8 matmul 가속기이다. RoCC 는 제어, 전용 AXI DMA 와 banked SRAM 은 행렬 데이터 이동을 담당한다. Host L1I/L1D·공유 L2 는 CPU 실행용이며 A/B/scale/C 의 NPU 데이터 경로에 포함하지 않는다.

P0 요구는 **지속 10 TOPS 이상**이다. 과거 10.24 TOPS 피크/2 MiB/유효 10GB/s 구성은 현재 C-resident schedule 에서 P0 를 만족하지 못한다. 따라서 이 문서는 **20.48 TOPS 피크, 8 MiB SRAM, 유효 20GB/s**를 기본 설계 구성으로 채택한다. SRAM·BW 예산 증가를 명시적으로 포함한 변경이며 기존 2MiB/10GB/s 예산을 유지한 채 달성했다는 의미가 아니다.

현재 실제 구현은 K=32 compute tile RTL 과 독립 SV SRAM template 이다. 전체 SRAM subsystem, 여러 K 블록의 FP32 누산, DMA·RoCC 연결, LLM 실행과 실제 지속 TOPS 는 아직 구현·검증 전이다. 기능 시뮬레이션과 장래 1GHz 물리 타이밍을 구분한다.

## 2. P0 의 정확한 수용 기준

| 항목 | 기준 |
|---|---|
| 기준 GEMM | M=1024, N=1024, K=4096; C=A×B, 초기 C=0 |
| 입력/출력 | MXFP4 weight A, OCP MXINT8 activation B, E8M0 block32, FP32 C |
| 연산량 | 2MNK=8,589,934,592 useful operations |
| P0 target | 전체 가속기 측 실행 평균 ≥10 useful TOPS |
| 시간 상한 | ≤858,993.4592ns =858.9934592µs |
| 측정 경계 | RoCC 작업 수락에서 모든 결과 write-response 완료까지; 최초 A/B/scale 을 DRAM 에서 읽고 결과 C 를 DRAM 에 저장 |
| 제외/별도 보고 | weight/activation 사전 quantization·packing, CPU tokenizer·sampling·attention, model loading, 측정용 warmup |
| 금지 | padding/idle MAC 을 useful ops 로 세기, SRAM preload 시간을 숨기기, compute-only 결과를 전체 P0 로 보고하기 |
| 메모리 | latency700ns, 합산 payload20GB/s 예약 목표, 효율 60% 이후에도 이 목표를 만족하는 물리 BW |

이는 대표 prefill/GEMM 기준이다. 모든 M/N/K, batch1 decode, 전체 LLM 서비스에서 10TOPS 를 보장하는 요구로 확장하지 않는다. 후자는 별도 workload·latency/tokens/s 계약이 필요하다.

현재 이벤트 모델은 기준 GEMM 에 약 13.4775TOPS/637.355µs 를 예측한다. 모델 여유는 약 35%지만 실제 RTL 이 이를 달성한 것은 아니다. RoCC·SRAM·FP32 pipeline·DRAM model 을 넣고 재검증해야 P0 수용 판정이 가능하다.


### 확정된 설계 목표

**지속 10 useful TOPS 이상은 선택 사항이 아닌 P0 필수 요구사항이다.** 10 TOPS를 연산 피크 수치로 대체하지 않는다. 기본 기준 GEMM은 `1024×1024×4096`이며, RoCC 작업 수락부터 최종 DMA write-response 완료까지 **858.9934592 µs 이하**여야 한다. 출력 정확도와 시간 기준을 동시에 통과해야 수용한다.

파라미터 `SUSTAINED_TOPS_TARGET=10`, `P0_MANDATORY=true`, `PERFORMANCE_REQUIREMENT=SUSTAINED_USEFUL_TOPS`로 명시한다. ×2/×4의 대응 목표는 지속 20/40 TOPS이다. `RTL_SUSTAINED_TARGET_VERIFIED=false`는 실제 통합 검증까지 유지한다. 20.48 TOPS 피크, 8 MiB SRAM, 유효20 GB/s는 이 목표를 위한 기본 설계 예산이며 공정·PPA 실현성 검증은 별도이다.

## 3. 파라미터 프로파일

`model/p0_model.py::profile(SCALE)`가 최신 단일 파라미터 원천이다. 과거 `model/spec_model.py`와 `docs/HDD.md`는 이전 10.24TOPS 피크 사양의 기록이다.

| Parameter | 기본 ×1 | ×2 | ×4 |
|---|---:|---:|---:|
| SCALE enum | 1 | 2 | 4 |
| 지속 TOPS 목표 | 10 | 20 | 40 |
| ARRAY_COUNT | 10 | 20 | 40 |
| Array rows × cols | 32×32 | 32×32 | 32×32 |
| MAC/clock | 10240 | 20480 | 40960 |
| Peak @1GHz | 20.48TOPS | 40.96TOPS | 81.92TOPS |
| Scale/FP32 result lanes | 320 | 640 | 1280 |
| SRAM | 8MiB | 16MiB | 32MiB |
| Operand / C | 2 / 5MiB | 4 / 10MiB | 8 / 20MiB |
| Partial / scale-meta | 512 /512KiB | 1024/1024KiB | 2048/2048KiB |
| AXI ports × data bits | 1×512 | 1×1024 | 2×1024 |
| AXI clock | 625MHz | 625MHz | 625MHz |
| Total raw BW | 40GB/s | 80GB/s | 160GB/s |
| Available @60% | 24GB/s | 48GB/s | 96GB/s |
| Payload target, R+W total | 20GB/s | 40GB/s | 80GB/s |
| Read/Write MO, aggregate | 64/32 | 128/64 | 256/128 |
| AXI ID bits per port | 7 | 8 | 8 |
| Max burst | 4096B | 4096B | 4096B |
| Representative macro M=N | 1024 | 1536 | 2048 |

모든 대역폭은 decimal GB/s, SRAM 은 binary MiB 이다. ×4 는 AXI data width 를 비표준 2048bit 로 늘리지 않고 1024bit 포트 2 개로 확장한다. 실제 DRAM 채널/컨트롤러가 aggregate80GB/s 를 지원해야 한다. 모델은 병렬포트의 aggregate 대역폭을 하나의 서비스 자원으로 근사하며, 포트별 arbitration 은 후속 검증 대상이다.

SCALE 변경은 모델 및 RTL wrapper 생성에서 지원한다. 현재 RTL 에는 이 표의 DMA·전체 SRAM 구현이 연결되어 있지 않다. 물리 SRAM 매크로/clock/전력과 SoC 포트 수를 파라미터만 바꿔 검증 없이 보장할 수는 없다.

## 4. Compute 구조

각 32×32 배열의 PE(i,j)는 C[i,j]의 K=32 부분합을 담당한다. 매사이클 A 열 32 개와 B 행 32 개를 broadcast 하여 1024MAC 을 수행한다. 배열 10 개는 10240MAC/clock, 1MAC=2operations 기준 20.48TOPS peak 이다.

32 클록마다 10 개의독립 tile 완료, 평균 3.2 클록/tile 이다. 개별 tile 의 K 누산지연은 32 클록이며, DMA·후처리·pipeline 지연은 별도이다. 일반 systolic 배열의 fill/drain 과혼동하지 않는다.

E2M1 코드를 2 배하여 {0,±1,±2,±3,±4,±6,±8,±12}로 decode 한다. MXINT8 는 signed byte q/128, E8M0 scale 은 2^(s−127)이다. 한그룹의정수 dot p 에대한최종값은:

```
y = p * 2^(scale_A + scale_B - 262)
```

RTL converter 는 RNE,gradual underflow, signed underflow zero, overflow infinity, E8M0=255 의 canonical qNaN 을 구현한다. 누산결과정확한 0 은+0 으로한다. 유한 MX 포맷의 signed-zero 의미는 곱셈 내부정수화에서합쳐진다.

K>32 에서는 각그룹결과에 scale 을적용한후 FP32 로누산해야한다. R1은 각 K=32 기여분을 출력하며, R2 stream GEMM이 그룹별 FP32 변환 결과를 순서대로 누산한다.

## 5. SRAM 및 data movement

목표매크로는 1R1W,main bank256bit,meta128bit 이다. 기본 bank 구성:

| Region | Banks ×1/×2/×4 | Depth | Width | 기본 용량 | 기본 최대 R / W |
|---|---|---:|---:|---:|---:|
| Operand | 32/64/128 | 2048 |256bit|2MiB|1024/1024GB/s|
| C |40/80/160|4096|256bit|5MiB|1280/1280GB/s|
| Partial |64/128/256|256|256bit|512KiB|2048/2048GB/s|
| Scale/meta |32/64/128|1024|128bit|512KiB|512/512GB/s|

기본 연산 입력: A160B/clock+B320B/clock+scale 평균 20B/clock=500GB/s. 결과 320 개/clock 이므로 partial R/W 각각 1280GB/s, C R/W 각각 1280GB/s 가필요하다. C port 용량은여유가없으므로 bank 충돌·DMA 추가 read·RMWhazard 를실제스케줄로해결해야한다. 필요하면 C bank 확장·tile drain 중첩을파라미터로추가한다.

R1 은 PE 누산레지스터와두개의결과 snapshot 레지스터를사용한다. SRAM template 은독립검증한 1-cycleread 이며,목표 SRAM2-cyclelatency/8MiBbank subsystem 은아직 연결되지않았다. C SRAM/FP32 feedback/DRAM 대역폭성능을 R1 결과로주장하지않는다.

출력 chunk 는동일 row 에대해배열별 32columns 를병렬출력한다. chunk0..31, lane=array_id*32+column 이다. 이배치는광범위한 flatcrossbar 대신 array/column 별로 row 를선택하도록한다.

## 6. DMA·AXI·메모리 ownership

- 전용 noncoherentAXI4master. RoCC `io.mem`/CPU L1D/L2 를 payload 경로로사용하지않는다.
- CPU 가접근하는 DMA 버퍼는 uncached,cacheablealias 금지,작업중 exclusiveownership. Fence 가 cachewriteback 을대체한다고가정하지않는다.
- AXI INCR, burst≤4KiB 이며 4KiB 경계분할,full-width 전송·WSTRBtail 기본. Source/ID/response 오류추적필수.
- Read latency700ns 는 issue→firstdata. Write B tail700ns 는임시가정이다. Out-of-orderread 응답과 AXI4 W 순서를분리관리한다.
- 기본 data512bit@625MHz=40GB/sraw;60%후 24GB/s 중 20GB/spayload 를목표예약한다. CPU 경쟁·refresh·turnaround 후 DRAM 실효성능을측정해야한다.
- Defaultaddr40bit,ID7bit,readMO64,writeMO32,AXI LEN8bit,SIZE3bit,LOCK/atomicOFF,USER 없음,endianlittle.
- AxCACHE0010/AxPROT000 은초기제안이며 SoC 보안·메모리정책에맞춰확정. QoS 숫자만으로 BW 예약을보장하지않는다.
- CDC asyncFIFO:1GHz↔625MHz. AR/AW/Bdepth16*S, R/W64*Sbeats;2-stagesynchronizer 기본. Inflight drain 후 reset.
- ID 점유를 burst 완료까지계산하면 minMO=ceil(1+BW*700ns/burst). 기본 20GB/s,4096B 이면 5 이지만작은 scale 트래픽을고려해 64 를선정한다.

## 7. 성능 모델의 의미

```
ops = 2*M*N*K
A_bytes = 17*M*K/32
B_bytes = 33*N*K/32
C_bytes = 4*M*N
AI = ops / (actual DMA payload bytes)
roofline = min(compute_peak, AI * effective_payload_BW)
```

모델은 burst/700nslatency/MO/4KiB 분할/두 operand slot/sharedread+writeBW 를이벤트로계산한다. Macro 별 C 를 SRAM 에유지하고마지막에저장하며 macro 사이의 A/B 재사용과 outputoverlap 은없다. Macro 입력이도착하면계산하고 K 그룹별 startup 를반영한다. 상세 bank conflict·RoCC·CPU packing·DDR row 스케줄은 생략한다. FP32 등의 pipeline 비용은 panel당14cycles의 보수적 항목으로 반영하며 RTL cycle simulation과 구분한다.

P0 후보의기준 GEMM 모델 13.4775TOPS 는향후 RTL 검증을진행할근거이며확정성능은아니다. 작은 608×320×4096 은약 8.2955TOPS 로 P0 아래이다. 따라서모든 shape 에 10TOPS 를주장하지않는다. 기존 2MiB/10GB/sprofile 은 regression 용으로만보존한다.

## 7.1 필수 Data Pipelining

[Data Pipelining 상세 규약](DATA_PIPELINING.md)을 P0 설계 요구사항으로 적용한다. DMA prefetch와 MAC, 이전 snapshot의 scale/FP32 누산을 중첩하고, C hazard는 scoreboard·8-context interleave/forwarding으로 관리한다. Byte credit 없이 MO만으로 DMA를 발행하지 않는다.

현재 모델에 **K-panel당14cycles**의 보수적 pipeline overhead를 추가했다. 기준 GEMM 예상치는 **13.4775TOPS /637.355µs**이며 지속10TOPS 모델 기준을 통과한다. 파이프라인 연결 후 실제 RTL 성능은 별도로 확인해야 한다. 현재 R1의 조합 converter를4-stage로 구현 완료했다는 의미는 아니다.

## 8. RTL 구현 실행 계획과 완료 정의

| 단계 | 산출물 | 완료 조건 | 현재 상태 |
|---|---|---|---|
| R0 | HDD/파라미터/event model | P0 기준 workload 가모델목표충족,capacity/ID/BW 제약통과 | 완료, 모델수준 |
| R1 | FP4decode,integerMAC,K32tile,double snapshot,scaledFP32,stream I/O | 독립 Python 기준값과 bit-exact,stall/active-mask/II 검사 | RTL 생성·시뮬레이션 수행 |
| R2 | K-loop FP32 accumulator | K64/128/4096,그룹별 scale,RNE·overflow 검증 | 구현, 결과는 R2 보고서 참조 |
| R3 | banked SRAM + load/store scheduler | 8MiB mapping,2-cycle read,bank conflict·RMW hazard | C SRAM slice·scoreboard 검증; 전체 subsystem 미구현 |
| R4 | AXI DMA + RoCC wrapper | latency700ns/reorder/errors,CPU cache 우회 | burst planner·byte credit 전단 검증; AXI/RoCC 미구현 |
| R5 | end-to-end RTL P0 | 1024×1024×4096,20GB/spayload 모델에서≤858.993µs | 미검증 |
| R6 | LLM operator/full-model simulation | 품질·tokens/s·prefill/decode 분리리포트 | 계획 |
| R7 | synthesis/STA/SRAMmacro/CDC | 실제공정 1GHz·625MHz,area/power/thermal 예산통과 | 미수행 |

### R1 인터페이스 계약

- `in_valid/in_ready`:K 벡터한개수락. 한 tile 그룹은 32acceptedbeats;stall 은 K 진행을멈춘다.
- 첫 beat 에서`in_scale_a/b`,active-mask,tile-id 를저장한다. 같은 tile 의후속 metadata 는무시한다.
- `in_a[array,row]`:4bit, `in_b[array,col]`:8bit. Output FP32 는`out_chunk=row`,lane=`array*32+col`.
- `out_valid/out_ready`:ready 가낮으면 data/id/chunk/valid 유지.32chunks 를수락하면 snapshot 반환.
- Reset 은진행중 tile/출력을폐기한다. 소비자는새 epoch 로구분해야한다. DMA 가없으므로현재외부 transactionabort 는없다.
- 연속입력·출력 ready 조건에서 tile-group II=32clock 을검사한다. 1nsTBclock 은 STA 결과가아니다.

### R2 설계 작업

검증된 FP32adder/변환 IP 후보를선정하고 license 를확인한다.320lanes 의 pipeline 목표와 Cfeedbackdependency 를설계한다.실행중다른 tile 문맥을교차해 adderlatency 를숨기거나 forwarding 을사용한다.그룹별 scale 이달라지는 K64·K128 부터검증후 K4096 으로확장한다.Independentgolden 은 FP32 연산마다 RNE 를적용하여동일누산순서를고정한다.

### R3/R4 설계 작업

SRAM address allocator/bankmapper,byte-mask,depthbounds,read-during-write 정책을고정한다. DMA 는 descriptorfetch/readIDreorder/writeBtracking 을분리한다.연산기용포트예약과 resultDMA 중재를설계하고실제 trace 로 FIFOdepth 를정한다.RoCC 는 CONFIG/SUBMIT/STATUS/WAIT 와 jobID/errorcode 를제공한다.기존 accumulatorconfig 는비교테스트이며 matmulwrapper 로간주하지않는다.

### 성능 acceptance test

1. DRAMpayload20GB/s,latency700ns,MO64/32 의 read/write/mixedtrace 를검증한다.
2. CPU 제출→모든 writeB 완료까지 cyclecounter 를측정한다.
3. Useful2MNK/elapsed 로 TOPS 를계산하고 padding/idlebubble 을제외한다.
4. Baselineworkload 정확도와 P0≥10 을동시에통과해야한다.
5. 순수 SRAMcompute/단일 tile/전체 system 성능을별도보고한다.

## 9. LLM 실행 검토·가이드

### 9.1 단계별 모델

| 단계 | 모델 | 목적 |
|---|---|---|
| L0 | 현재 12 개 syntheticMX tile patterns | bit-exact PE/scale/stream 검증 |
| L1 | MNIST MLP784→128→64→10 | 실제데이터분류,CPU bias/ReLU/requantize,NPUlinear |
| L2 | TinyDecoder2layers,d_model128,4heads,d_ff512,vocab512,context128,tiedembedding | attention/residual/norm/KV/prefill/decode 실행경로검증 |
| L3 | 공개소형 pretrained decoder 약 100–150M params 후보 | 품질과실제모델 trace/메모리병목검증 |

L2 는약 458,752 개의 embedding+denseweights 이며 MXFP4payload+scale 약 238KiB,FP16KVcache128KiB 가대략적하한이다.norm/bias/정렬/activation 은추가한다.임의가중치모델은기능검증용이며언어품질을주장하지않는다.L3 예시는 SmolLM2-135M 계열이며사용전실제 config/license/operator/tokenizer 를확인하고모델 revision/hash 를고정한다.현재모델 weights 를다운로드하거나추론한것은아니다.

### 9.2 Operator 매핑

NPU:Q/K/V/Oprojection,MLPlinear,LMhead 등 denseGEMM. CPU reference/fallback:embedding,RMSNorm/LayerNorm,RoPE,softmax,activation,residual,requantization,sampling. Attention QKᵀ/AV 를 NPU 에보내려면동적 activation 의 MXFP4 변환오차와추가 packing 비용을평가한다.처음에는 CPUattention 으로기능연결하고 operator 별시간을분리한다.

A=FP4weight[out,K],B=MXINT8activation[K,batch*sequence],C=FP32[out,batch*sequence].A 행·B 열 K 축 32 원소마다 scale 을붙인다.원래 tensor 를전용 packedlayout 으로변환하고 padding/mask 를기록한다.전체모델이한번의 matmul 이아니다.

### 9.3 Prefill 과 decode 를별도로평가

Prefill 은 N=batch×promptlength 가커서 tile 병렬성과 weight 재사용을확보하기쉽다.Decodebatch1 은 N=1 이라 32columns 중대부분이낭비되고 weights 재전송이주병목이된다.10TOPSP0 를 decode 일반목표로대체하지않는다.

135Mweights 를모두 FP4+blockscale 로전송한다고단순가정하면약 71.7MB/token 이다.20GB/s 에서도 weight-only 상한은약 279tokens/s,연산집약도는약 3.76ops/B→약 0.075TOPS 이다.실제로는 KV·비양자화 layer·CPU·sampling·packing 때문에더낮아진다.이는실측 tokens/s 예측이아닌대역폭상한이다.8MiBSRAM 에도전체 135M 모델은상주하지않는다.

### 9.4 재현 가능한 실행 순서

1. Modelmanifest:repo/revision/license,config,tokenizer,weightsha256,seed 를기록한다.
2. FP32/BF16CPUreference 로고정 prompt/next-tokenlogits 와작은평가셋을생성한다.
3. WeightMXFP4/activationMXINT8softwarequantization 을구현하고 scale 축·rounding 을고정한다.
4. Layertrace 로 GEMM shape/호출빈도/bytes,KVtraffic,CPUoperator 시간을저장한다.
5. Operatorgolden→R2RTL→DMA 통합의순서로 layer 별결과를비교한다.
6. TinyDecoder 전체 forward 를실행하고 prefill/decode 를분리측정한다.
7. Pretrained 모델의 logiterror/top-kagreement/perplexity 저하를확인한다.
8. Promptlength32/128/512,batch1/4/32,decode32tokens 등을 sweep 한다.모델 context 상한과메모리용량에맞춰조정한다.
9. CPUreference,softwarequantized,RTLfunctional,cyclemodel 실행을분리해보고한다.

보고항목:prefilllatency/TTFT,decodeinter-tokenlatency,tokens/s,end-to-endlatency,operator 별 cycle/usefulTOPS,DRAMbytes/BW/MOoccupancy,SRAMconflict,CPUfallback 비중,quantization 품질저하,peakmemory. Verilatorwalltime 을실제 1GHzlatency 로보고하지않는다.

### 9.5 추후 LLM runtime 구조

Python exporter/quantizer → packedweights/scale/descriptor manifest → C RoCC runtime → DMA/NPUlinear → CPUfallback → tokenloop. 임베디드 Linux 또는 bare-metal 중실행환경을고정한다.모델의대형 DRAM 버퍼·물리주소/IOMMU·uncachedownership 을런타임에서관리한다.

## 10. 환경·명령·현재 GitHub 상태

독립 clone 위치: `/workspace/TINY-NPU`,원본 `/workspace/chipyard`는보존한다.기존 sourcehistory/license/gitlinks 를유지하고 TINY NPU 작업은`tiny-npu/`아래에둔다.

```bash
cd /workspace/TINY-NPU/tiny-npu
source scripts/env.sh
make model       # P0 후보모델, RTL 성능검증아님
make generate    # x1/x2/x4 SVwrapper,profile manifest
make lint        # profileelaboration
make sram        # 독립 1R1WSRAMtemplate
make test        # 1/5/10arraysK32 기능테스트
```

같은 cloudinstance 의설치된 toolchain 을재사용한다.새 machine 에서는`toolchain.yaml`로 conda 환경을만들고 Verilator5.022/Python/GNUmake/C++compiler 를준비한다.Chipyardfull-SoC 작업에는별도로 pinnedsubmodules 및공식 toolchainsetup 이필요하다.

개발 원격은 기존 `jhroh13/chipyard`, 브랜치는 `tiny-npu`로 통일한다. 로컬 `/workspace/TINY-NPU`의 기존 커밋을 그대로 유지하고 origin을 기존 Chipyard로 연결했다. 원본 `/workspace/chipyard`의 `work` 브랜치와 미커밋 변경은 보존한다. `tiny-npu/scripts/publish.sh`는 이 브랜치만 non-force push하며 `main`은 변경하지 않는다. 새 저장소 생성 권한은 필요하지 않다.

## 11. 남은 공동 결정 / 실행 필요사항

- P0 설계 예산 20.48TOPSpeak/8MiB/유효 20GB/s 의실제공정·메모리자원확정.기존 2MiB/10GB/s 유지시별도아키텍처탐색이필요하다.
- P0 대표 GEMM  외 추가 실사용 shape 와 batch/LLMprefill/decode 서비스목표확정.
- SRAMcompiler/FP32IP/공정 PPA 예산,DRAMcontroller·QoS·포트수확정.
- 원격 개발 위치: https://github.com/jhroh13/chipyard/tree/tiny-npu . 별도 저장소 생성은 하지 않는다.
- R2→R5 구현전까지지속 10TOPS 실증완료라고표기하지않는다.

## 12. 현재 결과와 재현 산출물

- [RTL 시뮬레이션 보고서](results/RTL_SIMULATION.md):1/5/10 배열,12 case씩,총196,608 FP32 결과 bit-exact PASS.
- Backpressure input116/output220cycles를각구성에서실제로발생시켜검사했다.처음4개의연속tile-group은입력/출력II32를확인했다.
- 독립 SRAM template128comparison PASS. P0 x1/x2/x4 10/20/40-array RTL wrapper generation/lint PASS.
- [P0 파라미터 표](../configs/p0_parameters.csv), [P0 profile JSON](../configs/p0_profiles.json), [모델 결과](../model/p0_results.csv).
- [환경 재현 및 GitHub 게시 절차](BUILD_AND_PUBLISH.md).
- 생성된compute-only RTL은`tiny-npu/generated/`에보존한다.컴파일출력과벡터는`build/`에서재생성가능하다.

## 13. 다음 구현 단계 진행 기록

[R2 stream GEMM·FP32 누산](R2_K_ACCUMULATION.md)과[R2 시뮬레이션 결과](results/R2_SIMULATION.md)를 추가했다. 4단계FP32가산pipeline, lane별C SRAM, rowscoreboard, K블록job제어, DMA burstplanner/bytecredit가 포함된다. 기존R1 tile테스트와R2통합테스트를구분한다. 실제AXI데이터전송과전체8MiB메모리구성,RoCC/LLM/P0실증은후속단계이다.
