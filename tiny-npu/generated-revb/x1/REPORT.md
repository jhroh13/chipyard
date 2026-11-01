# RevB generated configuration x1

Config SHA256: `48b0002d97a1b554aafbde1b2430cb7079168fe27c29f5def401b59cbb1c2776`

| Item | Resolved |
|---|---:|
| Rocket cores | 8 |
| L0 bytes / physical subbanks | 10485760 / 384 |
| MAC arrays / peak TOPS | 10 / 20.480 |
| AXI ports x data bits | 2 x 256 |
| Requested effective GB/s | 20 |
| A/B/C/TARGETR slots | 8/8/8/8 |
| Planning TOPS, serialized vector | 12.306098 |

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU MMIO and system AXI mappings await integration. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` builds only the configuration package and isolated single-port SRAM wrapper.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
