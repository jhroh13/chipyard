"""Shared JSONL trace contract. One sample per domain clock, explicit period_ps.
No inference of unobserved Rocket/cache activity is permitted.
"""
import gzip,json
from pathlib import Path
CAUSES={1:'wait-data',2:'no-credit',4:'bank-conflict',8:'OIC-conflict',16:'consumer-stall',32:'control-starved',64:'cache-miss',128:'memory-wait'}

def open_text(path,mode='rt'):
 return gzip.open(path,mode,encoding='utf-8') if str(path).endswith('.gz') else open(path,mode,encoding='utf-8')

class Trace:
 def __init__(self,path,meta):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.file=open_text(path,'wt')
  self.file.write(json.dumps(dict(type='meta',schema_version=1,**meta))+'\n')
 def sample(self,time_ps,channel,valid,ready,period_ps=1000,**kw):
  row=dict(type='sample',time_ps=int(time_ps),period_ps=int(period_ps),channel=channel,valid=int(bool(valid)),ready=int(bool(ready)),**{'active':1,'bytes':0,'ops':0,'stall_mask':0,**kw})
  self.file.write(json.dumps(row,separators=(',',':'))+'\n')
 def event(self,time_ps,name,**kw):self.file.write(json.dumps(dict(type='event',time_ps=int(time_ps),name=name,**kw),separators=(',',':'))+'\n')
 def close(self):self.file.close()

def records(path):
 with open_text(path) as f:
  for line in f:
   if line.strip():yield json.loads(line)

def to_vcd(path,out):
 """Lossless handshake/stall waveform; transaction details remain in JSONL."""
 rows=list(records(path));channels=sorted({r['channel'] for r in rows if r['type']=='sample'})
 with open_text(out,'wt') as f:
  f.write('$timescale 1ps $end\n$scope module workload $end\n')
  for i,ch in enumerate(channels):
   name=ch.replace('.','_').replace('-','_')
   for suffix,width in [('valid',1),('ready',1),('stall',8),('active',1)]:f.write(f'$var wire {width} c{i}{suffix[0]} {name}_{suffix} $end\n')
  f.write('$upscope $end\n$enddefinitions $end\n')
  old={};now=-1
  for r in sorted((x for x in rows if x['type']=='sample'),key=lambda x:x['time_ps']):
   i=channels.index(r['channel'])
   if r['time_ps']!=now:now=r['time_ps'];f.write(f'#{now}\n')
   for suffix,value in [('v',r['valid']),('r',r['ready']),('s',r.get('stall_mask',0)),('a',r.get('active',1))]:
    key=f'c{i}{suffix}'
    if old.get(key)!=value:
     f.write((f'b{value:08b} {key}\n' if suffix=='s' else f'{value}{key}\n'));old[key]=value
