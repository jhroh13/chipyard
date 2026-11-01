# RevB generated configuration x1

Config SHA256: `7bf4302ebcbe7c4c11750645dcf5290f43309de9778de016ea6a0648edb478d2`

| Item | Resolved |
|---|---:|
| Rocket cores | 8 |
| L0 bytes / physical subbanks | 10485760 / 384 |
| MAC arrays / peak TOPS | 10 / 20.480 |
| AXI ports x data bits | 2 x 256 |
| Requested effective GB/s | 20 |
| A/B/C/TARGETR slots | 8/8/8/8 |
| Planning TOPS, serialized vector | 12.309145 |

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU MMIO and system AXI mappings await integration. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` builds only the configuration package and isolated single-port SRAM wrapper.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
