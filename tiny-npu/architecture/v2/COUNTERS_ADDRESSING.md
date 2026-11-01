# Bubbleless 실행을 위한 TC / OIC / 32×32 Addressing

이 문서는RevB의핵심계약이다. CPU polling loop로생산자/소비자를동기화하지않는다. TC/OIC/credit/slot/epoch가각엔진의하드웨어issue를제어한다. Bubbleless는준비된steady-state의목표이며초기fill·실제BW부족·오류·dependency가있을때무조건stall이없다는뜻이아니다.

## 1. 32×32 canonical tensor layout

`MT=ceil(M/32),NT=ceil(N/32),KT=ceil(K/32)`이고각tail은validmask/zero-padding으로구분한다. usefulTOPS에는padding연산을포함하지않는다. 데이터와scale plane의base는각각명시한다.

### A: MXFP4, K-panel-major

```
nibble = (((kt * MT + mt) * 32 + row) * 32 + k)
byte_address = A_base + floor(nibble/2)
nibble_select = nibble % 2               # LOW_FIRST
A_scale_address = AS_base + ((kt*MT+mt)*32+row)
```

Kpanel의A데이터가연속배치되어DMA가4KiB burst를만들수있다. Tile한개는512B+scale32B이다.

### B: MXINT8, K-panel-major / column-K blocked

```
B_address = B_base + (((kt*NT+nt)*32+column)*32+k)
B_scale_address = BS_base + ((kt*NT+nt)*32+column)
```

각B출력column의K32개가한MXscale그룹이다. 일반row-major B를그대로사용하는것이아니므로exporter/packing이필요하다.

### C: GROUP_ROW_ARRAY_COL

```
tile_id = mt*NT + nt
group = floor(tile_id/ARRAY_COUNT)
array_lane = tile_id % ARRAY_COUNT
C_byte = C_base + (((group*32+row)*ARRAY_COUNT+array_lane)*32+column)*4
```

10arrays에서한rowchunk는320개TF32container=1280B이다. 256bitbankword당8개원소이므로40word를40bank에각각하나씩보낼수있다.

```
word = floor((C_byte-C_base)/32)
bank = word % C_BANKS
bank_row = floor(word/C_BANKS)
word_element = column % 8
```

기본40 logical banks에서`bank=array_lane*4+floor(column/8)`, `bank_row=group*32+row`이다. Base는rowchunk/bankgroup정렬을권장한다. C_BANKS가20이면동일rowchunk에bank당2개요청이생기므로최소2issuecycles가필요하다. 주소가유효하다는것과한cycle에충돌없이처리된다는것을구분한다.

1024×1024 출력은1024tile이며마지막array-group에padding이필요하다. 전체group을할당하면`ceil(1024/10)*10*4096=4,218,880B`로단순4MiB보다크다. L0capacity탐색에서이padding을반드시포함한다.

Sub-bank 매핑은 `sub_bank=(word//40)%4`, `physical_row=word//160`이다. 같은 물리 sub-bank는 R 또는 W 하나만 수락한다. 서로 다른 row의 R/W도 같은 sub-bank로 매핑되면 중재해야 한다. 가변 latency에 맞춘 VOQ·return bitmap·commit credit 설계와 수식은 [single-port 계약](SINGLE_PORT_LATENCY_BW.md)을 따른다.

## 2. Near-register banking

| Register | MAC가보는bank | bank 내부주소 | 값 |
|---|---|---|---|
| SRCA |row(0..31)|slot*32+k|FP4 nibble|
| SRCB |column(0..31)|slot*32+k|INT8 byte|
| SRCC |column,또는PE-local배치|slot*32+row|TF32 container32|
| TARGETR |column,또는PE-local배치|slot*32+row|TF32 container32|

L0의row-K contiguous tile을SRCA에전체tile단위로넣고MAC는column vector를읽는다. L0에서매MACcycle마다stridedscalar를gather하면불필요한bank트래픽이폭증하므로그방식을피한다. A512B/B1024B tile을coalescedload해near-register에서전치방향read를제공한다.

LQ16 FMA4cycles는4contexts를round-robin으로발행한다. InputTC loop의빠른축은context,그다음K이다. Context마다K0..31순서를유지한다. Context가부족한tailbatch에는invalidbubble을발행하거나일정cycle을비우며유효MAC수로성능을계산한다.

각PE는초기C를해당SRCC의localentry에서읽고결과를자신의TARGETRentry에쓴다. 완성tile전체를한번에snapshot하는분산경로는L0↔register의1280B/clockdrain경로와구분한다. 이localfanout/port/PPA도구현시검증해야한다.

## 3. FP32 최종 출력의 row-major staging

기본Core6은TARGETR를L0C에TF32로저장한다. 최종K가완료된Ctile들은Core8의TC로gather하여activation후FP32row-major strip으로scratch에저장한다.

기본strip은32rows×1024columns×4B=128KiB,2slots=256KiB이다. L0scratch1MiB안에수용한다. Core2는strip의연속4KiB burst를DRAM에전송한다. Ctile당각row128B를독립AXItransaction으로보내MO와latency를낭비하는구조는피한다.

L0가작아지면striprows를16/8등으로줄이되두slot을유지한다. Core8은SCRATCH_FREE를acquire하고FP32writecommit후FP32_STRIP_READY를publish한다. Core2는해당strip의마지막B응답후free를반환한다. TF32C와FP32scratch를별도영역으로관리하므로in-placepermutationoverwrite가없다.

## 4. TC issue / commit 분리

- TCcontext마다base,6Dindex/extent/step/stride,unitbits4/8/16/32/64,window,job/epoch를가진다.
- 주소는acceptedissue시예약하고commit은별도추적한다. Stall에서index가진행되면안된다.
- 한acceptedvector의lane주소는base+lane offset으로생성하고패킹형식에맞게coalesce한다.
- Registerslot은ringindex뿐아니라generation을포함한다. L0bank주소와register주소의bounds를각각검사한다.
- Descriptor가가리키는loop는CPU개입없이실행하고TCterminal조건이completion-event를발생시킨다.

## 5. OIC / semaphore는 최우선 설계 블록

기본256×64bitcounter,16banks/16logicalrequestports,2cycle응답목표,32entryeventFIFO를제안한다. 4wait+4credit+4signal/descriptor를지원한다. 물리port와cross-bankatomicarbiter가이조건을처리하는지는RTL로검증해야한다.

### 원자적 conditional issue

```
if epoch_matches
   and all(SEQ_EVENT[id] >= expected)
   and all(CREDIT[id] >= amount)
   and destination_slot_reserved
   and engine_queue_has_space:
       atomically reserve ALL credits / slot / transaction ID
       accept operation; advance TC issue cursor
else:
       reserve NOTHING; keep descriptor/counters stable
```

Signal은엔진의payloadcommit후발생한다. Partialacquire,CPU중간notify,slot할당후다른slot을영원히기다리는순환경로를금지한다. Cross-bankatomic검사는centralissuearbiter또는owner-localreservationprotocol로일관된commit을제공해야한다.

### Sequence와credit 구분

- SEQ_EVENT:non-consuming `WAIT_GE`,여러reader가동일사실을관찰할수있음.
- CREDIT:원자적decrement/increment,값은0..capacity범위.
- job/epoch가다르면ready값이커도작업발행금지.
- counterwrap/underflow/overflow/미허용owneraccess는error.
- multi-readerpanel은referencecount가0이어야L0_INPUT_FREE를반환.
- error/abort는정상completionevent를발생시키지않고전용fault/epoch경로로전파.

### 기본 resources

| Resource | Capacity / 조건 | 반환 기준 |
|---|---|---|
| L0inputwindows |2|A/B/scale최종reader종료|
| SRCA/SRCB slots |8each|해당context의마지막operandread|
| SRCC slots |8|MAC가초기C를localstate로수락|
| TARGETR slots |8|Core6의L0TF32commit 또는선택directroute의Core8commit|
| FinalFP32strips |2|Core2의해당strip모든writeB완료|
| DMAIDs/bytes |64read/32write+예약bytes|전체response배출/최종B|

상태는`FREE → RESERVED → FILLING → READY → CONSUMING → COMMITTED → FREE`로관리한다. Generation은FREE재진입시증가시켜ABA를막는다.

## 6. Bubble budget와 관측

10배열은평균32cycle/group,즉31.25Mgroup/s이다. OIC예산을모든엔진합계32primitiveops/group으로두면평균1Gcounter-ops/s가필요하다. 단일1op/cycle공유counter포트는여유가없고burst에서막힌다. 분산owner counter와banking,ready-sequencecache,eventFIFO를함께설계한다.

완성4contexts의연속burst,bankalias,vectorstripstall,AXIresponseout-of-order를주입한다. `wait_A/B/C`, `no_target_credit`, `TC_address_stall`, `OIC_bank_conflict`, `OIC_atomic_retry`, `event_fifo_full`, `DMA_byte_credit`, `C_dependency`, `vector_LUT_conflict`를각각cyclecounter로분리한다.

필수검증:creditconservation,exactly-oncesignal,noearlypublish,noindexadvanceonstall,nolost/duplicatedtile,staleepochrejection,boundedqueue,deadlockwatchdog. Bubbleless는이검증과BW·dependency조건을만족하는steady-state에대해서만주장한다.

## 7. 실행 가능한 reference

`protocol_reference.py`는1,086,720개주소검사,기본C40banks의row당무충돌,all-or-nothingcredit/staleepoch/overflow/두reader소유권을검사했다. 소프트웨어계약검증이며TC/OIC RTL성능검증은아니다.
