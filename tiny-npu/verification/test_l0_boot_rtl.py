#!/usr/bin/env python3
import argparse,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sim'))
from run_extended import compile_run
from analyze_trace import analyze
from trace import to_vcd
ap=argparse.ArgumentParser();ap.add_argument('--synthetic-image',action='store_true',help='deterministic pattern for SRAM/reset CI; no firmware/ISA claim');args=ap.parse_args()
rows=[]
for guard,read,release,half_period in [(5,16,2,700),(7,32,4,2100)]:
 d=ROOT/f'build/l0-boot-rtl-g{guard}-r{read}';d.mkdir(parents=True,exist_ok=True)
 if args.synthetic_image:
  (d/'boot_words.hex').write_text(''.join(f'{int.from_bytes(bytes((i+j)%256 for j in range(32)), "little"):064x}\n' for i in range(4096)))
 else:
  image=ROOT/'build/l0-boot-firmware-x1/boot_words.hex'
  if not image.exists():raise SystemExit('Run make test-boot-firmware first, or use --synthetic-image for SRAM/reset-only CI')
  shutil.copyfile(image,d/'boot_words.hex')
 log=compile_run(d,'tb_l0_boot',['rtl/tiny_npu_sram_1rw_subbank.sv','rtl/tiny_npu_l0_boot_guard.sv','rtl/tiny_npu_sram_boot_control.sv','rtl/tiny_npu_preloaded_boot.sv','sim/tb_l0_boot.sv'],{'GUARD_LATENCY':guard,'READ_LATENCY':read,'RELEASE_STAGES':release,'HART_HALF_PERIOD':half_period},shutil.which('verilator'))
 assert 'L0_BOOT_RTL_PASS' in log and 'PRELOADED_SRAM_RESET_PASS' in log;to_vcd(d/'boot_trace.jsonl',d/'boot_trace.vcd.gz');analyze(d/'boot_trace.jsonl',d/'analysis')
 rows.append(dict(status='PASS',guard_latency=guard,sram_latency=read,image_kind='deterministic_pattern_no_ISA' if args.synthetic_image else 'compiled_RV64_firmware',release_stages=release,hart_period_ps=2*half_period,harts=8,log=log.strip(),scope='external SRAM preload during hart reset; direct SRAM reset PC, retention on CPU reset, CDC release +real single-port SRAM; synthetic fetches, not TL/Rocket RTL integration'))
(ROOT/'architecture/v2/l0_boot_rtl_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
