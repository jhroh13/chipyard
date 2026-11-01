# Single-port L0 / multicycle paths / AXI比率 — 필수 수식 계약

[최신 DRAM 지연 정의와 trace 검증](WORKLOAD_VERIFICATION.md)을 함께 적용한다.

이 문서가이전1R1W·짧은고정지연가정보다우선한다. 모든성능값에는clock,latency,II,credit,bank효율가정을명시한다. 현재통합RTL측정은아니며,변경에따른계획모델이다.

## 1. Bank → sub-bank → single-port macro

```
8개 RoCC role의 경로별 request queues
      ↓ TC주소 + slot/epoch + byte/vector credit
logical-bank router → sub-bank별 VOQ / arbitration
      ↓                   ↓                    ↓
   subbank0            subbank1             subbankN
   1RW SRAM            1RW SRAM             1RW SRAM
   R 또는 W            R 또는 W             R 또는 W
      └──────── variable-latency return / reorder ───────┘
                            ↓
              vector bitmap / register-slot commit
                            ↓
                    OIC ready / credit return
```

각physicalsub-bank는한cycle에**read또는write하나**만수락한다. 같은sub-bank의R/W를동시처리한다고계산하지않는다. 서로다른sub-bank에동시R/W를보내는것은가능하다.

| Region | Logical banks | Sub-banks/bank | Physical macros | Width | Depth/macro | 용량 | 합산R+Wraw@1GHz |
|---|---:|---:|---:|---:|---:|---:|---:|
|A|16|2|32|256bit|1024|1MiB|1024GB/s|
|B|32|2|64|256bit|1024|2MiB|2048GB/s|
|C|40|4|160|256bit|1024|5MiB|5120GB/s|
|scratch|32|2|64|256bit|512|1MiB|2048GB/s|
|scale/meta|32|2|64|128bit|1024|1MiB|1024GB/s|
|**합계**|**152**|—|**384**|—|—|**10MiB**|**11264GB/s**|

상한의R+W를다시read/write각각으로더하면2배과대계산이다. 실제BW는macroII,conflict효율,router/return/TC issue폭에의해감소한다.

```
Capacity = Nlogical × Nsub × Depth × Width/8
Bshared = Nlogical × Nsub × Width/8 × fL0 / II_subbank × eta_conflict
B_read + B_write <= Bshared
rho = (B_read_required + B_write_required)/Bshared < 1
```

`eta_conflict=0.8`은현재sweep의여유가정이며실측값이아니다. 실제banktrace로보정한다. `READ_LATENCY=16,II=1`인pipeline과`READ_LATENCY=16,II=16`인비pipelinemacro는구분한다.

## 2. 현재 MAC의read/write 요구

MAC10arrays×32×32,1GHz,1MAC=2ops이면20.48TOPSpeak이다. 내부LQ16FMA4cycle/4contextinterleave의II1을달성한다는설계가정이다.

```
u_compute_for_10TOPS = 10 / 20.48 = 0.48828125
Aread_peak = 10×16 B/clock =160GB/s
Bread_peak =10×32 B/clock =320GB/s
scale_peak=20GB/s
Cread_peak=10×1024×4B/32clock=1280GB/s
Cwrite_peak=1280GB/s
```

C경로의read/write비율은1:1이다. 지속10TOPS에서각625GB/s,합계1250GB/s가필요하다. 기존40개의256-bit single-port macro만쓰면합산1280GB/sraw의97.656%가되어여유가없다.0.8conflict효율이면1024GB/s로요구량보다작다.

C를40logical×4subbank로분할하면raw5120GB/s,0.8효율에서4096GB/s이다. 지속10TOPS의평균점유율은1250/4096=30.52%,computepeak에서도2560/4096=62.5%이다. 이는충돌이없거나중재로분산할수있을때의계획값이다.

## 3. Sub-bank 주소와경합

C layout의bank-group은40개의256-bit word이다.

```
word = floor((C_address-C_base)/32)
logical_bank = word % 40
sub_bank = floor(word/40) % 4
physical_row = floor(word/(40*4))
```

따라서group,row,각array의column으로정의된C주소에서sub_bank=row%4이다. readrow r과writerow r+delta가동시발행될때delta%4!=0이면각logicalbank내에서서로다른sub-bank를사용한다.

고정phase만믿지않는다. Multicyclelatency가바뀌면완료phase도달라지므로,경로별·sub-bank별VOQ와eligible-row중재로경합을흡수한다. 동일row RMW는read-before-write 및K버전scoreboard가보장한다. 일부bankword만완료된vector는returnbitmap으로합치고전체slotcommit전에OICready를발생시키지않는다.

L0↔register각경로,Core6resultstore,Core8vectorread/write,DMAin/out에독립queue/credit을둔다. Starvationbound,compute예약과DMA/vector최소서비스량을지정한다. Read/write같은주소순서는job/epoch/K태그로검사한다.

## 4. 지연은1cycle로고정하지않는다

기본L0↔registerforwardpath는16 L0-clockcycles목표다. 예시분해:

| Stage | 기본cycles | 변경가능성 |
|---|---:|---|
|Requestqueue target|2|부하에따라증가,최악bound별도|
|Sub-bankarbiterpipeline|2|포트/중재기구현에따라변경|
|SRAMmacroread|2|PDKmacro에따라변경|
|ECC|0|ECC선택시추가|
|Xbar/physicaltransport|4|floorplan/retiming에따라변경|
|Registeringress/alignment|4|vectorpacking에따라변경|
|Commitackpipeline|2|returnfabric에따라변경|
|**합계**|**16**|명시적parameter들의합|

SRCA,SRCB,SRCC,TARGETR,DMA→L0,L0→AXI,vectorL0read/write,TC,OIC,FMA,LUT/format,CDC를각각독립latency로둔다. 공통16cycles는bulk-sweep편의값일뿐한경로의변경이모든경로를바꾸어야한다는뜻이아니다.

```
Lpath = Lqueue + Larb + Lmacro + Lecc + Ltransport + Lalign + Lack
Tpath_ns = Σ(stage_cycles / stage_clock_Hz × 1e9)
```

Clockdomain이다르면cycle수를직접더하지않는다. AXICDC4cycles@625MHz는6.4ns이며1GHzL0의4ns가아니다. MAC/L0/AXI/vectorclock은성능함수에서독립입력이다.

기본nominal16,지연sizingbound32를제안하고10/16/32/64/128/256cycles를검토한다. Bound를초과해도credit/backpressure로데이터정확성을유지하며,성능stall과timeout정책은별도보고한다.

## 5. Latency hide: buffer·slot·ID 수식

```
Ninflight_vectors >= ceil(Lpath / II_issue) + skid_margin
Breserved >= Rpayload_bytes_per_cycle × Lpath + Bburst_margin
Lcredit_RTT = Lforward + Lreturn + LOIC
Smin >= Bcompletion_groups + ceil(Lcredit_RTT / Igroup)
Sconfigured = next_power_of_2(max(2*contexts,Smin))
```

기본contexts=4,평균Igroup=32cycles,완료burst4groups이다. OIC응답2cycles를포함한보수적RTT는`2L+2`이다. 슬롯은명목지연이아닌설계bound로잡는다.

| 검토pathcycles | creditRTT | 권장slots |
|---:|---:|---:|
|10|22|8|
|16|34|8|
|32|66|8|
|64|130|16|
|128|258|16|
|256|514|32|

SRCC도4slots가아닌기본8slots로변경한다. Cread32cycles/group이compute평균주기와같으므로추가multicycle왕복지연을4slots만으로숨길수없기때문이다. SRCA/B/C/TARGETR각각의지연으로개별sizing을할수있다.

위reservedbytes는반드시독립FIFO메모리를추가하라는뜻은아니다. 이미예약된RRFdestination이나L0slot을재조립buffer로사용하면같은데이터를중복예산하지않는다. 실제FIFO를별도구현하면L010MiB외부면적에추가한다. VectorID/slot-generation/epoch/row/word-completionmask도해당in-flight수에맞춰늘린다.

고정8slots에서L128이면credit만으로도`Igroup>=258/(8−4)=64.5cycles`가되어32cycle목표를유지할수없다.16slots이면`258/(16−4)=21.5cycles`라credit제약은32cyclecompute주기뒤로숨길수있다. 실제BW/충돌제약은여전히별도이다.

## 6. 256-bit AXI / DRAM read-write ratio

기준GEMM1024×1024×4096,C=0의외부payload:

```
Read A+B+scales =6,553,600B =6.25MiB
Write final FP32 C=4,194,304B =4MiB
Read:Write =25:16
AI=799.219512 ops/B
10TOPS에필요한R=7.629394531GB/s, W=4.8828125GB/s
합계최소12.512207031GB/s (latency/기타비용제외)
```

256bit@625MHz는각R또는W채널raw20GB/s,60%효율후각12GB/s이다. AXI에는독립R/W채널이있으므로이를무시하고“oneport는항상합계12GB/s만가능”이라고단정하면안된다.

| 256-bitports | 방향별raw | 방향별60%후 | 보수적공유DRAMservice예산 | 25:16 R/W완전중첩시채널상한 |
|---:|---:|---:|---:|---:|
|1|20GB/s|12GB/s|12GB/s|19.68GB/s|
|2|40GB/s|24GB/s|24GB/s|39.36GB/s|
|4|80GB/s|48GB/s|48GB/s|78.72GB/s|

우측은DRAM컨트롤러가그합산BW를제공하고서로다른job/strip의R/W를실제로중첩할때만가능하다. 현재단일macro의input계산후최종output저장schedule은독립채널을항상동시에채우지못한다.

기본은**2×256bit@625MHz**,공유payload20GB/s예약을선택한다. 1port의보수적12GB/sservice에서는roofline9.5906TOPS로10TOPS아래다. 반면이상적인duplex중첩상한은더높으므로1port의절대불가능을뜻하지는않는다. 20GB/s를25:16비율로동시달성하려면R12.1951/W7.8049GB/s가필요하여oneport의R12GB/s도소폭초과한다.

AXIport증설만으로DRAMBW가늘지않는다.

```
Bsystem_payload <= min(BAXI_service_raw, BDRAM_shared_raw) × eta_system
BDRAM_shared_raw_required >=20GB/s /0.60 =33.333GB/s
```

DRAMDQ폭/transfer-rate/channel수로이조건을검사하고controller/QoS/refresh/turnaround를포함해측정한다. Read/writeMO64/32는기본전체값이며2ports에분산한다. 4KiBburst는256bit포트에서128beats이므로AXI_MAX_BURST_BEATS도128로변경한다.

## 7. 전체 성능 방정식과 모델 범위

```
Tjob >= max(Tcompute_service, Texternal_bytes, Tlocal_singleport_service)
Tpipeline = Tfill + (N−1)*max(IIstage) + Tdrain
Igroup >= max(32*local_BW_slowdown,
              Lcredit_RTT/(slots−contexts),
              OICops_per_group/OICservice_ops_per_cycle)
TOPS_useful =2*M*N*K / Tjob /1e12
```

Latency가증가해도충분한credit/slot과II1이면steady-state처리량이즉시1/L로감소하지는않는다. 대신fill/drain·부족한credit·job전환비용이증가한다. II자체가늘거나sub-bank가경합하면service성능도감소한다.

현재모델은경로별multicyclefill/drain,4-context잔여group,sharedsingle-portBW,credit고정/자동sizing,AXIportservice를반영한다. 추가queue/DDR세부스케줄은근사이다. 과거1-cycleRAMRTL테스트나FP32R2core의실행결과를새RevB성능으로대체하지않는다.

Single-subbank prototype는10/16/32/64cycle read-response와backpressure에서검사했다. 전체384sub-bank fabric·TC/OIC·새LQ16MAC·8core·실제AXI통합은아직미구현이며지속10TOPS실증도아직아니다.


## 8. 재현 검증과 남은 통합 검증

`test_path_sensitivity.py`에서 14개 경로 latency를 각각 64cycle 늘리고, MAC/L0/AXI/vector clock을 각각 절반으로 낮추고, subbank II를 2/4/8로 변경하는 21개 경우와 latency 감소 경우를 검사했다. 모든 경우가 의도한 성능 방향을 보였다. [결과 JSON](path_sensitivity.json).

`test_singleport.py`는 10/16/32/64cycle의 read return pipeline과 backpressure를 검증한다. 이 primitive의 write는 command 수락 시 SRAM에 기록된다. 전체 write transport·commit 지연과 per-subbank VOQ/중재기는 향후 fabric 통합 검증 대상이다. 이 테스트를 전체 경로 latency 실증으로 해석하지 않는다.

향후 RTL에서는 고정 설정별 latency sweep에 더해 요청별 랜덤 latency, reorder, R/W bank alias, OIC atomic 경합, consumer stall을 동시에 주입한다. 모든 in-flight request는 epoch·slot-generation·completion mask로 추적하고, 슬롯 전체 commit 전 ready publish를 금지한다. 실제 지연이 sizing bound를 넘으면 backpressure로 정확성을 유지하고 성능 하락을 기록한다.
