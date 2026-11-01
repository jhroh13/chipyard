# RevB generated configuration x1

Config SHA256: `b14c2088e467db1fdc5fee72db7a086070a5f1efd15d03017f6f35994252dc54`

| Item | Resolved |
|---|---:|
| Rocket cores | 8 |
| L0 bytes / physical subbanks | 10485760 / 392 |
| MAC arrays / peak TOPS | 10 / 20.480 |
| AXI ports x data bits | 2 x 256 |
| Requested effective GB/s | 20 |
| A/B/C/TARGETR slots | 32/32/32/32 |
| Native FMA latency / contexts | 11 / 12 |
| FMA max basic-gate depth / limit | 39 / 40 |
| Planning TOPS, serialized vector | 10.771972 |

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU address is a planned TL window; actual Chipyard integration remains pending. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` includes the configuration package, isolated SRAM, boot access guard, external-preload/reset control, boot linker/constants and, in LQ16 mode, a native staged FMA wrapper. Hash/VOQ/fabric primitives are included; instantiate per-region geometry with canonical hash/queue/monitor settings. No full multi-region fabric wrapper is emitted. TF32 arithmetic is not emitted.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
