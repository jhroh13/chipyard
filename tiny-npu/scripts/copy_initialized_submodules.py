#!/usr/bin/env python3
"""Populate independent pinned submodule clones from an existing local Chipyard.
Copies Git history and tracked source, not ignored build outputs or credentials.
"""
import argparse,subprocess
from pathlib import Path

def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def populate(source,target):
    count=0
    for entry in git(target,'ls-tree','-r','HEAD').splitlines():
        mode,kind,tail=entry.split(' ',2)
        if mode!='160000':continue
        commit,path=tail.split('\t',1);src=source/path;dst=target/path
        if not (src/'.git').exists():continue
        if not (dst/'.git').exists():
            subprocess.run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(src),str(dst)],check=True)
            subprocess.run(['git','-C',str(dst),'checkout','--quiet','--detach',commit],check=True)
            remote=git(src,'remote','get-url','origin')
            # Copy only standard public GitHub remotes; never credential-bearing URLs.
            if remote.startswith('https://github.com/') and '@' not in remote:
                subprocess.run(['git','-C',str(dst),'remote','set-url','origin',remote],check=True)
            else:raise RuntimeError('Unexpected source remote; configure manually: '+path)
        count+=1+populate(src,dst)
        print('Populated',dst.relative_to(target.parents[0]),flush=True)
    return count
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=Path('/workspace/chipyard'));ap.add_argument('--target',type=Path,default=Path('/workspace/TINY-NPU'));a=ap.parse_args()
    print('Initialized submodule clones:',populate(a.source,a.target))
