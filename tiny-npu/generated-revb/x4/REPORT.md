# RevB generated configuration x4

Config SHA256: `68947bb6363ace60dc23a05b385d4faa8813d5fa2c53d7257c0f86051cbe8346`

| Item | Resolved |
|---|---:|
| Rocket cores | 8 |
| L0 bytes / physical subbanks | 41943040 / 1536 |
| MAC arrays / peak TOPS | 40 / 81.920 |
| AXI ports x data bits | 8 x 256 |
| Requested effective GB/s | 80 |
| A/B/C/TARGETR slots | 8/8/8/8 |
| Planning TOPS, serialized vector | 49.314824 |

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU MMIO and system AXI mappings await integration. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` builds only the configuration package and isolated single-port SRAM wrapper.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
