# RevB generated configuration x4

Config SHA256: `8181a3ab681e1b5fe4d18cd64cbb54f9ec6ab76e1d41adbfa4f456f337fc9df3`

| Item | Resolved |
|---|---:|
| Rocket cores | 8 |
| L0 bytes / physical subbanks | 41943040 / 1544 |
| MAC arrays / peak TOPS | 40 / 81.920 |
| AXI ports x data bits | 8 x 256 |
| Requested effective GB/s | 80 |
| A/B/C/TARGETR slots | 32/32/32/32 |
| Native FMA latency / contexts | 11 / 12 |
| FMA max basic-gate depth / limit | 39 / 40 |
| Planning TOPS, serialized vector | 43.148837 |

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU address is a planned TL window; actual Chipyard integration remains pending. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` includes the configuration package, isolated SRAM, boot access guard, boot linker/constants and, in LQ16 mode, a native staged FMA wrapper. TF32 arithmetic is not emitted.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
