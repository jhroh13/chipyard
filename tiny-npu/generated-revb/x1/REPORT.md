# RevB generated configuration x1

Config SHA256: `7b73db6d91ab82473c5205d8120725a1f652c15f0b0278c32479eedb9ffe2e98`

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

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU address is a planned TL window; actual Chipyard integration remains pending. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` includes the configuration package, isolated SRAM, boot access guard, boot linker/constants and, in LQ16 mode, a native staged FMA wrapper. TF32 arithmetic is not emitted.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
