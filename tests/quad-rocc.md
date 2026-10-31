# Four-core Rocket with RoCC

`chipyard.QuadRocketRoCCConfig` provides four RV64 Rocket cores with:

| Resource | Configuration |
| --- | --- |
| L1 instruction cache, per core | 8 KiB, 64 sets, 2 ways |
| L1 data cache, per core | 8 KiB, 64 sets, 2 ways |
| Shared inclusive L2 | 64 KiB, 1 bank, 256 sets, 4 ways |
| Cache line | 64 bytes |
| RoCC, per core | AccumulatorExample, 4 registers, custom0 |

The L2 capacity is shared across the four cores. Backing DRAM uses the normal
Chipyard AbstractConfig defaults. This is an example RoCC accelerator; replace
the accumulator fragment when integrating a specific accelerator.

In this cloud environment:

```bash
source /workspace/setup/activate.sh
export PATH=/workspace/setup/host-tools/bin:$PATH
cd /workspace/chipyard
cmake -S tests -B tests/build -D CMAKE_BUILD_TYPE=Debug
cmake --build tests/build --target quad-rocc accum mt-hello -j4
cd sims/verilator
make -j4 CONFIG=QuadRocketRoCCConfig
make CONFIG=QuadRocketRoCCConfig run-binary LOADMEM=1 BINARY=../../tests/build/quad-rocc.riscv
make CONFIG=QuadRocketRoCCConfig run-binary LOADMEM=1 BINARY=../../tests/build/accum.riscv
make CONFIG=QuadRocketRoCCConfig run-binary LOADMEM=1 BINARY=../../tests/build/mt-hello.riscv
```

`quad-rocc` starts all four harts, publishes distinct inputs in coherent memory,
and uses each hart's private RoCC to load the next hart's input, add a value,
and read the result. Hart zero checks all four results and prints one PASS per
hart. `accum` additionally exercises register writes; `mt-hello` checks that all
four cores run. Require successful simulator exit and `*** PASSED ***` in the
corresponding `.out` file under
`sims/verilator/output/chipyard.harness.TestHarness.QuadRocketRoCCConfig/`.
