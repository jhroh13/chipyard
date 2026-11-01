#!/usr/bin/env python3
"""Counterfactual fixture sweeps; never turns cache capacity into invented miss rate."""
import collections,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from configuration import load_profile
from verify_config import resolve
from local_stress import run_local
from trace import CAUSES
class CounterTrace:
 def __init__(self):self.counts=collections.Counter();self.mac_fires=0;self.samples=0
 def sample(self,t,ch,v,r,**kw):
  if ch=='mac.issue':
   self.samples+=1;self.mac_fires+=int(bool(v and r))
   if not(v and r):
    for bit,name in CAUSES.items():
     if kw.get('stall_mask',0)&bit:self.counts[name]+=1
 def event(self,*a,**kw):pass
p=load_profile();cfg=resolve(json.loads((ROOT/'configs/revb/verification.json').read_text()),p)['local'];rows=[]
cases=[('baseline',{},{}),('latency64_slots2',{'path_latency_cycles':64,'register_slots':2},{}),('latency64_slots8',{'path_latency_cycles':64,'register_slots':8},{}),('latency128_slots8',{'path_latency_cycles':128,'register_slots':8},{}),('latency128_slots16',{'path_latency_cycles':128,'register_slots':16},{}),('bank_skew',{'bank_mapping':'skew'},{}),('subbanks8_linear',{'subbanks':8},{}),('rocket_half_clock',{}, {'ROCKET_CLOCK_HZ':500000000}),('rocket_double_clock',{}, {'ROCKET_CLOCK_HZ':2000000000}),('icache16KiB_same_miss_trace',{}, {'ROCKET_ICACHE_BYTES':16384}),('ideal_no_cache_miss',{'icache_miss_probability':0},{}),('ideal_no_consumer_stall',{'consumer_stall_probability':0},{})]
for name,changes,profile_changes in cases:
 c=dict(cfg,**changes)
 if 'path_latency_cycles' in changes:c.pop('per_path_latency',None)
 pp=dict(p,**profile_changes);trace=CounterTrace();result=run_local(trace,c,pp,27012)
 rows.append(dict(case=name,stimulus_overrides=changes,profile_overrides=profile_changes,retired_tokens=result['retired'],MAC_scheduling_utilization=trace.mac_fires/trace.samples,raw_MAC_causes=dict(trace.counts),source_bank_conflicts=result['bank_conflicts'],scope='reduced traffic fixture; not chip performance prediction'))
base=rows[0];cache=next(r for r in rows if r['case']=='icache16KiB_same_miss_trace');assert base['retired_tokens']==cache['retired_tokens'] and base['MAC_scheduling_utilization']==cache['MAC_scheduling_utilization']
result=dict(status='PASS',cases=rows,caveats=['Frequency is control-agent service opportunity, not Rocket IPC.','Cache capacity has no invented miss-rate model; real Rocket trace is required.','Changing subbank count alone may preserve stride aliases.','More registers cannot cure a service bandwidth or consumer bottleneck.'])
(ROOT/'architecture/v2/workload_sweeps.json').write_text(json.dumps(result,indent=2)+'\n')
for r in rows:print(r['case'],r['retired_tokens'],round(r['MAC_scheduling_utilization'],4),'bank_conflicts',r['source_bank_conflicts'])
