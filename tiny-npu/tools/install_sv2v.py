#!/usr/bin/env python3
"""Pinned optional SV array-port frontend for generic synthesis (Linux x86_64)."""
import hashlib,platform,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if platform.machine() not in ('x86_64','amd64'):raise SystemExit('Use an installed sv2v on this platform; pinned binary is Linux x86_64')
archive=ROOT/'build/sv2v-v0.0.12.zip';archive.parent.mkdir(exist_ok=True)
if not archive.exists():subprocess.run(['curl','-fsSL','--retry','2','https://github.com/zachjs/sv2v/releases/download/v0.0.12/sv2v-Linux.zip','-o',str(archive)],check=True)
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='ff8c9eea5bc029b372fb4953427625cddb7cf7e58c1240623ac9f260818d5a00','sv2v archive checksum mismatch'
with zipfile.ZipFile(archive) as z:
 binary=ROOT/'build/synth-tools/bin/sv2v';binary.parent.mkdir(parents=True,exist_ok=True);binary.write_bytes(z.read('sv2v-Linux/sv2v'));binary.chmod(0o755)
print('sv2v v0.0.12 installed with verified archive SHA256')
