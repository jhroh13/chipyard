#!/usr/bin/env python3
"""AXI contract/ordering/efficiency and trace accounting regression."""
import collections,copy,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from configuration import load_profile
from verify_config import resolve
from dram import run_axi
from local_stress import run_local
from trace import Trace,records,to_vcd
from analyze_trace import analyze,correlate_axi

class MemoryTrace:
 def __init__(self):self.rows=[]
 def sample(self,t,ch,v,r,period_ps=1000,**kw):self.rows.append(dict(type='sample',time_ps=t,channel=ch,valid=int(v),ready=int(r),period_ps=period_ps,**kw))
 def event(self,t,name,**kw):self.rows.append(dict(type='event',time_ps=t,name=name,**kw))

def check_axi(rows):
 held={};reads={};writes={};wqueue=collections.defaultdict(list);read_beats=write_beats=0
 for r in rows:
  if r['type']=='event':
   if r['name'] in ('AR_ACCEPT','AW_ACCEPT'):
    key=(r['port'],r['id']);d=reads if r['name']=='AR_ACCEPT' else writes
    assert key not in d;d[key]=dict(remaining=r['beats'],complete=False)
    if r['name']=='AW_ACCEPT':wqueue[r['port']].append(r['id'])
   continue
  ch=r['channel'];v=r['valid'];ready=r['ready'];payload=tuple(r.get(k,0) for k in ('id','last','bytes'))
  if ch in held:assert v and payload==held[ch],('unstable valid/payload under backpressure',ch,r)
  if v and not ready:held[ch]=payload
  else:held.pop(ch,None)
  if not(v and ready):continue
  _,port_s,kind=ch.split('.');port=int(port_s[1:]);key=(port,r.get('id',0))
  if kind=='R':
   assert key in reads;reads[key]['remaining']-=1;read_beats+=1
   assert bool(r['last'])==(reads[key]['remaining']==0)
   if r['last']:reads[key]['complete']=True
  elif kind=='W':
   assert wqueue[port] and key[1]==wqueue[port][0],'AXI4 W must follow AW order (no WID)'
   writes[key]['remaining']-=1;write_beats+=1;assert bool(r['last'])==(writes[key]['remaining']==0)
   if r['last']:writes[key]['complete']=True;wqueue[port].pop(0)
  elif kind=='B':assert key in writes and writes[key]['complete'];writes[key]['retired']=True
 assert all(r['complete'] for r in reads.values()) and all(r.get('retired') for r in writes.values())
 assert not held
 return dict(read_beats=read_beats,write_beats=write_beats,stable_handshakes=True,per_port_W_order=True)

def main():
 p=load_profile();cfg=resolve(json.loads((ROOT/'configs/revb/verification.json').read_text()),p);base=cfg['axi'];results=[]
 for direction in ('R','W'):
  c=dict(base,directions=[direction],ports=1,transactions_per_direction=1,burst_bytes=[128],read_jitter_ns=0,consumer_stall_probability=0,response_reorder=False)
  tr=MemoryTrace();r=run_axi(tr,c,p,1);check_axi(tr.rows)
  latency=r['read_latencies_ns' if direction=='R' else 'write_launch_latencies_ns'][0]
  assert 700<=latency<701.6
  results.append(dict(test='isolated_'+direction,measured_ns=latency,status='PASS'))
 for seed in (1,9,27011):
  tr=MemoryTrace();r=run_axi(tr,base,p,seed);check=check_axi(tr.rows)
  latency,transactions=correlate_axi([x for x in tr.rows if x['type']=='sample']);assert latency['incomplete']==0 and not latency['issues'];assert latency['AR_to_RLAST']['count']==base['transactions_per_direction']
  assert r['achieved_shared_GBs']<=r['effective_service_GBs']*(1+1e-10)
  assert r['max_outstanding_per_port']['R']<=base['read_mo'] and r['max_outstanding_per_port']['W']<=base['write_mo']
  assert r['cross_ID_read_overtakes']>0
  results.append(dict(test='stress',seed=seed,status='PASS',achieved_GBs=r['achieved_shared_GBs'],cross_ID_overtakes=r['cross_ID_read_overtakes'],**check))
 c=dict(base,directions=['W'],ports=1,transactions_per_direction=1,burst_bytes=[128],aw_ready_holdoff_cycles=1000,consumer_stall_probability=0)
 tr=MemoryTrace();r=run_axi(tr,c,p,1);check_axi(tr.rows)
 latency,transactions=correlate_axi([x for x in tr.rows if x['type']=='sample'])
 assert not latency['issues'] and transactions[0]['first_wvalid_ps']<transactions[0]['request_ps']
 assert 700<=transactions[0]['AW_to_WVALID_ns']<701.6
 results.append(dict(test='WVALID_independent_of_AWREADY',AW_to_WVALID_ns=transactions[0]['AW_to_WVALID_ns'],accepted_AW_to_WVALID_ns=transactions[0]['AW_accept_to_WVALID_ns'],status='PASS'))
 a=MemoryTrace();r1=run_axi(a,base,p,3);raw=dict(base,bandwidth_mode='raw');b=MemoryTrace();r2=run_axi(b,raw,p,3)
 assert r1['cycles']==r2['cycles'] and abs(r1['effective_service_GBs']-r2['effective_service_GBs'])<1e-10
 assert r1['efficiency_applications']==0 and r2['efficiency_applications']==1
 results.append(dict(test='raw_vs_effective_no_double_efficiency',status='PASS'))
 for mo in (1,4,32):
  c=dict(base,read_mo=mo,write_mo=max(1,mo//2));tr=MemoryTrace();r=run_axi(tr,c,p,7);check_axi(tr.rows);results.append(dict(test='MO_sweep',read_mo=mo,achieved_GBs=r['achieved_shared_GBs'],status='PASS'))
 with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
  d=Path(temp);trace=Trace(d/'trace.jsonl',dict(provenance={'test':'accounting_oracle'}))
  trace.sample(0,'mac.issue',1,1,ops=20)
  trace.sample(1000,'mac.issue',0,1,stall_mask=1|4)
  trace.sample(2000,'mac.issue',1,0,stall_mask=2)
  trace.sample(3000,'mac.issue',0,0,active=0)
  trace.close();s=analyze(d/'trace.jsonl',d/'analysis')['channels']['mac.issue'];to_vcd(d/'trace.jsonl',d/'wave.vcd')
  assert s['handshakes']==1 and s['ops']==20 and s['bubble_ps']==2000 and s['active_ps']==3000
  assert sum(s['primary_causes_ps'].values())==s['bubble_ps'] and sum(s['raw_causes_ps'].values())>s['bubble_ps']
  results.append(dict(test='trace_exclusive_vs_overlapping_causes',status='PASS'))
 # Fixed >10cycle, per-request jitter, OIC, consumer, bank aliases, long credit RTT.
 for latency,jitter,slots,mapping in [(10,0,8,'linear'),(16,16,8,'linear'),(64,32,8,'skew'),(128,32,8,'linear'),(128,32,16,'skew')]:
  tr=MemoryTrace();c=dict(cfg['local']);c.pop('per_path_latency',None);c.update(path_latency_cycles=latency,request_jitter_cycles=jitter,register_slots=slots,bank_mapping=mapping,cycles=2048)
  r=run_local(tr,c,p,4);assert r['exactly_once_return_tags'];assert r['bank_conflicts']>0 or mapping=='skew'
  results.append(dict(test='local_latency_credit',latency=latency,jitter=jitter,slots=slots,mapping=mapping,retired=r['retired'],status='PASS'))
 summary=dict(status='PASS',tests=results,scope='protocol/trace qualification; no system NPU performance proof')
 (ROOT/'architecture/v2/environment_tests.json').write_text(json.dumps(summary,indent=2)+'\n');print('Environment tests PASS:',len(results))
if __name__=='__main__':
 (ROOT/'build').mkdir(exist_ok=True);main()
