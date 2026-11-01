# Bank hashing / VOQ / bubble RTL report

8 ingress,8 physical single-port banks,256-bit words,4096 rows/bank,VOQ depth2. Hashing and monitoring are enabled at reset. This is a one-region fixture, not the full392-subbank/Rocket/MAC/AXI system. The selected SRAM capacity is1MiB.

요약: Hashing/SFR/VOQ/중재기를 실제1RW SRAM에 연결해8개 조건을 검증했다. 기본 hashing/monitor enable이며, bank 충돌은 해당 stride에서 제거되었다. Consumer stall 시 반환 credit 정체는 남는다. 실제 Rocket/MAC는 연결 전이므로 코어 주파수·cache 변경 효과나 지속10 TOPS는 이 결과로 판단하지 않는다.

## Measured results

Each phase contains512 commands (64/ingress): phase0 write, phase1 read, phase2 four read/four write streams concurrently. All1536 commands/case are accepted and issued exactly once;768 read results/case match the written data. Requests target linear bank0, row=4*(sequence*8+ingress). The known stride tests concentration deliberately. Hashing distributes this stream across eight banks.

| Hash | SRAM latency | Consumer | Write cycles | Read cycles | Mixed R/W cycles | Bank contention samples | VOQ no-credit samples | SRAM command blocked | Response blocked |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| off | 16 | ready | 518 | 534 | 533 | 1533 | 10332 | 0 | 0 |
| on | 16 | ready | 70 | 86 | 86 | 0 | 0 | 0 | 0 |
| off | 32 | ready | 518 | 550 | 549 | 1533 | 10332 | 0 | 0 |
| on | 32 | ready | 70 | 102 | 102 | 0 | 0 | 0 | 0 |
| off | 32 | all banks:13/23 ready | 518 | 950 | 877 | 2213 | 15537 | 680 | 728 |
| on | 32 | all banks:13/23 ready | 70 | 143 | 152 | 0 | 248 | 248 | 528 |
| off | 32 | bank0:13/23 ready; others ready | 518 | 950 | 877 | 2213 | 15537 | 680 | 728 |
| on | 32 | bank0:13/23 ready; others ready | 70 | 143 | 152 | 0 | 41 | 41 | 91 |

Phase duration runs from the first upstream request acceptance through command/response drain, including the four hash stages, two VOQ/output stages, SRAM latency and any stalls. The test clock period is1ns; it is a simulation timebase, not a measured1GHz physical clock. Event sample counts are summed per port/bank observation, may overlap and must not be added into elapsed cycles.

## Bubble interpretation and improvements

- L=16, ready: hashing improves write completion 518/70=7.40x, read 6.21x and mixed R/W 6.20x for this deliberately strided stream.
- L=32, ready: hashing improves write completion 518/70=7.40x, read 5.39x and mixed R/W 5.38x for this deliberately strided stream.
- L=32, all banks:13/23 ready: hashing improves write completion 518/70=7.40x, read 6.64x and mixed R/W 5.77x for this deliberately strided stream.
- L=32, bank0:13/23 ready; others ready: hashing improves write completion 518/70=7.40x, read 6.64x and mixed R/W 5.77x for this deliberately strided stream.

- Linear mode concentrates all commands in one bank; round-robin progresses fairly but other banks cannot help that address pattern. Increasing queue depth alone does not raise its single-bank service ceiling.
- Hash mode removes this stream’s bank contention. Its no-stall write phase retains six cycles of initial pipeline fill; read/mixed phases also retain response drain. These bounded fill/drain costs are not steady-state MAC bubbles.
- With stalled response consumers, hashing still leaves read-return backpressure and VOQ credit exhaustion. Prioritize return FIFO/credit sizing, consumer service BW and arbitration before adding banks or Rocket frequency. The primitive conservatively gates all new commands when its read-response pipeline is blocked, including writes; decoupling write issue from return buffering is a later optimization with dependency checks.
- Bank0-only response stall allows unrelated banks to keep progressing. The positive independent_progress_samples count in the JSON is observed handshakes at other banks while bank0 is blocked, rather than an assumption about HOL removal. Upstream single-FIFO HOL remains possible before commands reach their per-bank VOQs.
- Same-address RAW/WAR/WAW ownership is not solved by hashing. The mixed test uses preinitialized independent addresses; producer/consumer scoreboard and OIC/epoch integration are still needed for real dependencies.

## Monitor and trace evidence

SFR index1 bit0 defaults to1 and gates passive simulation probes/counters. Actual DUT ingress/command/response valid/ready, bank contention and VOQ no-credit are written to JSONL; compressed VCD and the existing offline workload viewer are generated. Counter accumulation and JSONL writing in this fixture are simulation monitor logic; only monitor enable/status is presently exposed through the RTL SFR, not a complete hardware counter register file. No Rocket IPC, cache misses or MAC useful-valid signals are fabricated.

| Trace group | Interpretation |
|---|---|
| fabric.portN | actual request valid/ready; blocked ingress |
| fabric.bankN.command | actual single-port SRAM command valid/ready, byte throughput |
| fabric.bankN.response | SRAM read-return valid/ready; consumer-stall cause |
| fabric.bankN.arbiter | contention status; not a payload transaction rate |

Files: `build/bank-fabric-h{0,1}-l{16,32}-s{0,1,2}/fabric_trace.jsonl`, `fabric_trace.vcd.gz`, `analysis/workload.html`. These files preserve the selected fixture and cause provenance.

## Correctness and40-gate checks

- Hash unit: **344,064** tuple/metadata comparisons PASS across8/160 banks, hash on/off, every1024 rows and output stalls. An independent integer golden computes the inverse-compatible mapping.
- Audited32-bit8x8 netlist: **256** command comparisons PASS with mixed read/write metadata, random command stalls, exact tag/data routing and SFR linear selection. This is regression, not formal equivalence.
- Generic synthesis uses AND2/OR2/NOT only with XOR/MUX and synchronous register-control logic expanded, matching the strict FMA stage policy. SV array-port conversion uses sv2v v0.0.12; the installation script verifies the release archive checksum.
- mapper160: maximum **19/40** basic gates, **PASS**; parameters `{'BANKS': 160, 'ROW_BITS': 10, 'PAYLOAD_BITS': 305}`.
- fabric8: maximum **30/40** basic gates, **PASS**; parameters `{'PORTS': 8, 'BANKS': 8, 'DATA_BITS': 32, 'ROW_BITS': 10, 'TAG_BITS': 16}`.
- fabric8_full256: maximum **31/40** basic gates, **PASS**; parameters `{'PORTS': 8, 'BANKS': 8, 'DATA_BITS': 256, 'ROW_BITS': 12, 'TAG_BITS': 16}`.

Full256-bit8-bank fabric gate depth is audited; the complete160-bank and x2/x4 multi-region fabric, physical SRAM timing, area and clock closure remain separate. This report establishes neither sustained10 TOPS nor external DRAM bandwidth. The old10.772 TOPS planning model has not been calibrated to the new six-cycle command path.

## Ordered next step

1. Add tagged read-return routing, bounded response credits and write-commit acknowledgments, then test variable request latency, reordering and mixed hazards across the shared consumer buses.
2. Connect per-region decoders, fixed boot bank isolation and shared hash settings to the real TL/AXI/RoCC fabric. Attach TC/OIC and producer/consumer ownership before MAC integration.
3. Sweep VOQ depth, hash shift, bank geometry, SRAM latency/II and consumer BW with the same workload and trace provenance. Calibrate aggregate path-latency/credit sizing and then measure useful MAC bubbles.

Reproduce from `tiny-npu/` after sourcing `scripts/env.sh`:

```
make test-bank-hash
make test-bank-fabric
python tools/install_sv2v.py
make check-bank-depth
make test-bank-netlist
python verification/report_bank_fabric.py
```

[HDD: conflicts and SFR contract](HDD.md#20-현재-bank-공유-구조-충돌과-구현-범위) · [RTL results](bank_fabric_tests.json) · [Hash unit](bank_hash_tests.json) · [Gate-depth evidence](bank_fabric_gate_depth.json) · [Post-synthesis regression](bank_netlist_tests.json)
