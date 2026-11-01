# RevB generated configuration x2

Config SHA256: `6cb88e93056eec0218b364a812db5c01e796874176e7c5c6b02e5661180e3440`

| Item | Resolved |
|---|---:|
| Rocket cores | 8 |
| L0 bytes / physical subbanks | 20971520 / 768 |
| MAC arrays / peak TOPS | 20 / 40.960 |
| AXI ports x data bits | 4 x 256 |
| Requested effective GB/s | 40 |
| A/B/C/TARGETR slots | 8/8/8/8 |
| Planning TOPS, serialized vector | 24.881546 |

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU MMIO and system AXI mappings await integration. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` builds only the configuration package and isolated single-port SRAM wrapper.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
