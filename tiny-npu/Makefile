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
