#!/usr/bin/env python3
"""Compile canonical L0-resident stage1 and run multi-hart Spike ISA qualification."""
import argparse,hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from configuration import load_profile

def run(scale=1):
 p=load_profile(scale);generated=ROOT/f'generated-revb/x{scale}';out=ROOT/f'build/l0-boot-firmware-x{scale}';out.mkdir(parents=True,exist_ok=True)
 gcc=shutil.which('riscv64-unknown-elf-gcc');objcopy=shutil.which('riscv64-unknown-elf-objcopy');spike=shutil.which('spike')
 if not all((gcc,objcopy,spike)):raise SystemExit('Source scripts/env.sh; RISC-V gcc/objcopy/Spike are required')
 elf=out/'l0_boot.elf';raw=out/'l0_boot.bin'
 cmd=[gcc,'-march=rv64imac_zicsr_zifencei','-mabi=lp64','-mcmodel=medany','-nostdlib','-nostartfiles','-static','-Wl,--no-relax','-T',str(generated/'boot.ld'),'-Wa,-I,'+str(generated),str(ROOT/'firmware/l0_boot.S'),'-o',str(elf)]
 subprocess.run(cmd,check=True,capture_output=True,text=True)
 subprocess.run([objcopy,'-O','binary','-j','.text','-j','.rodata',str(elf),str(raw)],check=True)
 code=raw.read_bytes();assert code and len(code)<=p['L0_BOOT_CODE_BYTES']
 padded=code+bytes(p['L0_BOOT_CODE_BYTES']-len(code));(out/'boot_code_padded.bin').write_bytes(padded)
 (out/'boot_words.hex').write_text(''.join(f'{int.from_bytes(padded[i:i+32],"little"):064x}\n' for i in range(0,len(padded),32)))
 command=[spike,'-l',f'-p{p["ROCKET_CORES"]}','--isa=rv64imac_zicsr_zifencei',f'-m0x{p["L0_CPU_BASE_ADDR"]:x}:0x{p["L0_BYTES"]:x}',f'--pc=0x{p["L0_BOOT_ENTRY_ADDR"]:x}',str(elf)]
 with (out/'spike.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=30)
 text=(out/'spike.log').read_text();assert result.returncode==0,(result.returncode,text[-3000:])
 instructions=[];starts=set();counts={}
 for line in text.splitlines():
  match=re.search(r'core\s+(\d+):\s+0x([0-9a-f]+)\s+\(0x([0-9a-f]+)\)',line,re.I)
  if match:
   hart=int(match[1]);pc=int(match[2],16);counts[str(hart)]=counts.get(str(hart),0)+1
   if pc==p['L0_BOOT_ENTRY_ADDR']:starts.add(hart)
   instructions.append(dict(step=len(instructions),hart=hart,pc=hex(pc),instruction='0x'+match[3]))
 assert starts==set(range(p['ROCKET_CORES'])),starts
 (out/'isa_trace.json').write_text(json.dumps(dict(unit='ISA instruction order; not cycles/time',instructions=instructions),separators=(',',':'))+'\n')
 result=dict(status='PASS',scale=scale,harts=p['ROCKET_CORES'],entry=hex(p['L0_BOOT_ENTRY_ADDR']),cpu_window=[hex(p['L0_CPU_BASE_ADDR']),hex(p['L0_CPU_LIMIT_ADDR'])],code_bytes=len(code),code_reserved_bytes=p['L0_BOOT_CODE_BYTES'],elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),configuration_sha256=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest(),entered_harts=sorted(starts),instruction_counts=counts,scope='Spike ISA-only preload test; firmware verifies every hart ID/private stack; not Rocket RTL, cache, TL manager, loader timing, or SRAM permission proof')
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--scales',type=int,nargs='+',default=[1]);a=ap.parse_args();r=[run(s) for s in a.scales];(ROOT/'architecture/v2/l0_boot_firmware_tests.json').write_text(json.dumps(r,indent=2)+'\n')
