# 실제 RTL probe 연결 계약

`tiny_npu_trace_monitor`는 passive observer다. 신호를 만들어 DUT에 넣는 드라이버로 사용하지 않는다.

| Probe | 연결 대상 / 주의 |
|---|---|
| ctrl_valid/ready[h] | role별 RoCC command acceptance. response는 별도 channel로 확장. 코어 polling을 MAC issue로 세지 않는다. |
| mem_valid/ready[h], source/opcode/address | 선택한 Rocket tile의 TileLink A 또는 CPU cache request. 어느 interface인지 provenance에 명시. |
| mem_resp_valid/ready[h], source/opcode | 같은 경계의 TileLink D 또는 cache response. ready가 없는 valid-only interface는 ready=1. |
| ic_valid/ready, ic_miss, dc_miss | 실제 frontend/cache performance event. capacity만으로 miss를 생성하지 않는다. |
| retire_valid[h] | 실제 architectural instruction retire. 필요시 retire width를 확장. |
| hart_clk/period_ps[h] | 실제 hart clock와 period. 비활성 hart는 hart_active=0. |
| AXI AR/R/AW/W/B | DUT와 controller 사이 같은 관찰 경계. ID 폭·LEN·주소·LAST·WSTRB를 실제 wire에서 연결. |
| mac_valid/ready/useful_ops | padding/tail/inactive PE를 제외한 실제 accepted MAC 연산. 1MAC=2ops. |
| stall mask | 실제 source bitmap/credit/bank arbiter/OIC/consumer 상태에서 생성. 추측으로 encoding하지 않는다. |

현재 SRAM fixture는 4 synthetic requester가 실제 SRAM에 접근한다. memory response probe·AXI는 연결하지 않았고 나머지 hart도 inactive다. Behavioral workload의8개 Rocket/control/cache는 traffic agent다. 실제8-core Chipyard integration이나 cache 성능을 측정했다고 보고하지 않는다.

Trace header의 provenance와 canonical configuration SHA256를 결과와 함께 보관한다. 실제 DUT parameter override와 verification seed/jitter/latency/credit 설정도 별도 run manifest로 보존한다. trace를 다른 설정의 리포트와 합치지 않는다.

향후 RTL에서 FIFO enqueue/dequeue, slot occupancy/high-water, request/commit pointer, epoch·slot-generation·TC coordinates, OIC wait/acquire/publish를 event로 추가한다. analyzer는 임의 channel을 지원하므로 새로운 경로도 같은 형식으로 표시할 수 있다. RoCC 수락과 최종 write B 완료를 job ID로 연결한 뒤에만 end-to-end useful TOPS를 판정한다.

`HART_PERF_AVAILABLE`와 `HART_RESPONSE_AVAILABLE` mask는 실제 cache/retire·memory-response probe를 연결한 hart만1로 둔다. 기본0이므로 미연결 채널을 실제 cache miss/IPC 자료로 오해하지 않도록 비활성 표시한다.
