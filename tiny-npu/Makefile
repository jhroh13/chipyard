PYTHON ?= python3
ARRAYS ?= 1 5 10
VERILATOR ?= verilator
.PHONY: test model lint sram generate

test:
	$(PYTHON) sim/run_sim.py --arrays $(ARRAYS) --verilator $(VERILATOR)

model:
	$(PYTHON) model/p0_model.py

generate:
	$(PYTHON) tools/generate_rtl.py

lint:
	$(PYTHON) tools/generate_rtl.py --lint --verilator $(VERILATOR)

sram:
	mkdir -p build/sram
	$(VERILATOR) --binary --timing -j 4 --top-module tb_sram --Mdir $(CURDIR)/build/sram/obj -o Vtb_sram rtl/tiny_npu_sram_bank.sv sim/tb_sram.sv > build/sram/compile.log 2>&1
	build/sram/obj/Vtb_sram > build/sram/simulation.log 2>&1
	cat build/sram/simulation.log

EXT_ARRAYS ?= 1 2 10
.PHONY: extended generate-gemm lint-gemm
extended:
	$(PYTHON) sim/run_extended.py --arrays $(EXT_ARRAYS)

generate-gemm:
	$(PYTHON) tools/generate_gemm_rtl.py

lint-gemm:
	$(PYTHON) tools/generate_gemm_rtl.py --scale 1 --lint --verilator $(VERILATOR)

.PHONY: dma-frontend
dma-frontend:
	$(PYTHON) -c "import sys,shutil;sys.path.insert(0,'sim');from run_extended import dma_frontend;dma_frontend(shutil.which('verilator'))"

.PHONY: generate-revb check-revb
generate-revb:
	$(PYTHON) tools/generate_revb.py --lint

check-revb:
	$(PYTHON) tools/generate_revb.py --check
	$(PYTHON) sim/test_revb_config.py
	$(PYTHON) architecture/v2/test_path_sensitivity.py

.PHONY: verify-environment workload trace-rtl numeric-prototype synth-initial
verify-environment:
	$(PYTHON) verification/test_environment.py
	$(PYTHON) verification/sweep_workload.py

workload:
	$(PYTHON) verification/run_workload.py

trace-rtl:
	$(PYTHON) verification/run_rtl_trace.py

numeric-prototype:
	$(PYTHON) verification/test_lq16_fma.py
	$(PYTHON) verification/test_lq16_tile.py

synth-initial:
	$(PYTHON) synthesis/run_synthesis.py

.PHONY: check-fma-depth test-fma-pipe
check-fma-depth:
	$(PYTHON) synthesis/test_gate_depth.py
	$(PYTHON) synthesis/check_fma_depth.py

test-fma-pipe:
	$(PYTHON) verification/test_lq16_pipe.py
	$(PYTHON) verification/test_lq16_pipe_tile.py

.PHONY: test-boot-firmware test-boot-rtl check-boot-depth test-fma-netlist
test-boot-firmware:
	$(PYTHON) verification/test_l0_boot_firmware.py --scales 1 2 4

test-boot-rtl:
	$(PYTHON) verification/test_l0_boot_rtl.py

check-boot-depth:
	$(PYTHON) synthesis/check_boot_depth.py

test-fma-netlist:
	$(PYTHON) synthesis/test_fma_netlist.py

.PHONY: test-bank-fabric test-bank-hash check-bank-depth
test-bank-fabric:
	$(PYTHON) verification/test_bank_fabric.py

test-bank-hash:
	$(PYTHON) verification/test_bank_hash.py

check-bank-depth:
	$(PYTHON) synthesis/check_bank_fabric_depth.py

.PHONY: test-bank-netlist
test-bank-netlist:
	$(PYTHON) synthesis/test_bank_netlist.py
