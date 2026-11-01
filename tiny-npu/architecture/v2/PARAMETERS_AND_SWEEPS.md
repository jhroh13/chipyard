# Parameter와single-port/multicycle sensitivity 가이드

현재기본은8 Rocket /10MiBL0 /single-port384subbanks /LQ16FMA /TF32TARGETR이다. [필수수식](SINGLE_PORT_LATENCY_BW.md)과[TC/OIC/addressing](COUNTERS_ADDRESSING.md)을먼저적용한다. 이전1R1W/짧은고정지연표는새구조의성능근거로사용하지않는다.

## 분리해야 하는 축

| Group | 변경 변수 | 계산·검증 |
|---|---|---|
| Workload |M/N/K,batch,tail,Cinitial,format,activation|usefulops,재사용,정확도|
| Capacity |L0total,region비율,depth,allocationgranularity|실제bytes,macro,spill/reload|
| SingleportBW |logicalbanks,subbanks,width,clock,portII,conflict효율|R+W합산service,hotbank|
| 각 경로 latency |A/B/C/TARGETR,DMA-L0,L0-AXI,vector,TC/OIC,FMA,LUT/format,CDC|fill/drain,creditRTT,queuebound|
| Near registers |elements,width,contexts,slots,distributedports|burstcompletion,source/destinationcredit|
| Counter / semaphore |dims,stride/unitbits,issueII,banks/ports,atomic조건,epoch,eventFIFO|주소/동기화stall·deadlock|
| Externalmemory |AXI256ports,clock,효율,MO,burst,FIFO,DRAMservice,QoS|R/Wratio,가능BW와latencyhide|
| Vector |lanes,LUTports/replicas,II,기능별latency,striprows/slots|최종FP32store속도|
| Physical |PDK,SRAMmacro,wire,clockdomains,ECC,power|실제1GHz/PPA;현재미검증|

**Latency와II는독립parameter이다.** L=16,II=1은여러요청을동시에보유하면pipeline발행이가능하지만L=16,II=16인nonpipelinedmemory는동일BW가아니다. 어떤경로도암묵적으로1cycle로두지않는다. 모델에서II1은명시적목표값이고타이밍검증결과가아니다.

## 실행

```bash
cd /workspace/TINY-NPU/tiny-npu
python3 architecture/v2/analyze.py
python3 architecture/v2/local_paths.py
python3 architecture/v2/sweep_l0.py \
  --l0-mib 2 4 6 8 10 12 16 --bank-factor 0.25 0.5 1 2 \
  --path-cycles 10 16 32 64 128 --axi-ports 1 2 \
  --slots-policy AUTO FIXED8 --bw-gbs 20
```

560개설정을실행했다. 용량은physicalmacro단위로depth를내림정렬하고C group-padding을포함한다. Auto macro선택은DRAM중복전송을줄이는heuristic이며전역최적schedule은아니다.

독립경로지연과clock은PythonAPI로입력할수있다:

```python
from sweep_l0 import evaluate
r = evaluate(10, latency=16, axi_ports=2,
    per_path={'SRCA':24,'SRCB':32,'SRCC':64,'TARGETR':48,
              'TC':3,'OIC':4,'FMA':6,'DMA_L0_COMMIT':20,
              'L0_AXI_READ':24,'VECTOR_READ':32,'VECTOR_WRITE':48,
              'LUT':8,'FORMAT':2,'AXI_CDC':6},
    mac_hz=1e9,l0_hz=1e9,axi_hz=625e6,vector_hz=1e9)
```

`evaluate(...,config=...)`은`profiles.json`의기본profile객체를받을수있다. 명시적으로전달한sweep인수가해당profile항목을override한다. TC/OIC구현세부나PDK/DDRtiming같은변수는아직RTL/trace기반service로구현되지않았으며별도검증대상으로표기한다.

## 기본10MiB의latency/credit sensitivity

2×256bit@625MHz,유효20GB/s목표,각localpath지연을동시에변경했다. SRAMsingleportII1,conflict효율0.8을가정했다. 모든stagefill/drain과최종vector직렬pass를포함한보수적예상치이며실제통합RTL값은아니다.

| Local latency cycles | Slot policy | Slots | MAC group II cycles | Vector 포함 예상 TOPS |
|---:|---|---:|---:|---:|
| 10 | AUTO | 8 | 32.00 | 12.337 |
| 10 | FIXED8 | 8 | 32.00 | 12.337 |
| 16 | AUTO | 8 | 32.00 | 12.309 |
| 16 | FIXED8 | 8 | 32.00 | 12.309 |
| 32 | AUTO | 8 | 32.00 | 12.236 |
| 32 | FIXED8 | 8 | 32.00 | 12.236 |
| 64 | AUTO | 16 | 32.00 | 12.094 |
| 64 | FIXED8 | 8 | 32.50 | 11.981 |
| 128 | AUTO | 16 | 32.00 | 11.818 |
| 128 | FIXED8 | 8 | 64.50 | 7.408 |

지연128cycles에서고정8slots는credit반환이늦어groupII가64.5cycles로증가한다. AUTO16slots는credit병목을숨길수있지만물리BW·counterarbitration은여전히검증해야한다.

## 용량 sensitivity: multicycle default16cycles

| 요청L0MiB | 실제bytes | Macro | Vector포함예상TOPS |
|---:|---:|---|---:|
| 2 | 2088960 | 608×416 | 7.532 |
| 4 | 4187136 | 1024×480 | 9.846 |
| 6 | 6287360 | 1024×736 | 11.001 |
| 8 | 8385536 | 1024×992 | 10.722 |
| 10 | 10485760 | 1024×1024 | 12.309 |
| 12 | 12574720 | 1024×1024 | 12.309 |
| 16 | 16773120 | 1024×1024 | 12.309 |

Capacity-only는banks/subbanks/width를고정하고depth만바꾼다. 용량이증가해도작업이이미수용되거나다른병목이있으면성능이증가하지않는다. 작은비단조결과는선택된macro와contextpadding의heuristic영향이며일반법칙이아니다.

## 모델의한계와수용기준

단순service효율·latency항목으로per-subbankqueue분포와atomicOIC중재를완전히대체하지않는다. 실제주소trace,read/write VOQ,TC/OIC,가변returnlatency와새LQ16FMA를RTL로연결해교정한다. Counter/semaphore는성능검증의핵심블록이며모델상BW가충분하다는이유로bubbleless를선언하지않는다.

최종수용은결과정확도와RoCC수락→최종DRAMwriteB까지지속10TOPS를동시에통과해야한다. 기존FP32R2기능회귀나과거1cycle SRAMtest는이요건을대체하지않는다.

현재 표는 새 AR→RLAST/AWVALID→WVALID DRAM 계약의 event 근사 모델이다. 실제 workload trace 검증·합성 결과는 [선행 검증](WORKLOAD_VERIFICATION.md)을 참조한다.
