#!/usr/bin/env python3
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sim'))
from run_extended import compile_run
from analyze_trace import analyze
from trace import to_vcd
rows=[]
for guard,read in [(5,16),(7,32)]:
 d=ROOT/f'build/l0-boot-rtl-g{guard}-r{read}';d.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(ROOT/'build/l0-boot-firmware-x1/boot_words.hex',d/'boot_words.hex')
 log=compile_run(d,'tb_l0_boot',['rtl/tiny_npu_sram_1rw_subbank.sv','rtl/tiny_npu_l0_boot_guard.sv','sim/tb_l0_boot.sv'],{'GUARD_LATENCY':guard,'READ_LATENCY':read},shutil.which('verilator'))
 assert 'L0_BOOT_RTL_PASS' in log;to_vcd(d/'boot_trace.jsonl',d/'boot_trace.vcd.gz');analyze(d/'boot_trace.jsonl',d/'analysis')
 rows.append(dict(status='PASS',guard_latency=guard,sram_latency=read,harts=8,log=log.strip(),scope='real guard +single-port SRAM; firmware fetched by synthetic CPU agents; not TL/Rocket RTL integration'))
(ROOT/'architecture/v2/l0_boot_rtl_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
