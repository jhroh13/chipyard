#!/usr/bin/env python3
"""Source-backed workload waveform, bubble intervals, JSON diagnosis and HTML viewer."""
import argparse,collections,html,json,math
from pathlib import Path
from trace import records,CAUSES

def correlate_axi(samples):
 reads=collections.defaultdict(collections.deque);aw=collections.defaultdict(collections.deque);bwait=collections.defaultdict(collections.deque);address_present={}
 rows=[];issues=[]
 for r in sorted(samples,key=lambda x:(x['time_ps'],{'AR':0,'AW':0,'R':1,'W':1,'B':2}.get(x['channel'].split('.')[-1],0))):
  parts=r['channel'].split('.')
  if len(parts)!=3 or parts[0]!='axi':continue
  port=parts[1];kind=parts[2];t=r['time_ps'];fire=r['valid'] and r['ready'];key=(port,r.get('id',0))
  if kind in ('AR','AW') and r['valid']:
   addrkey=(port,kind,r.get('id',0))
   if addrkey not in address_present:
    row=dict(port=port,id=r.get('id',0),kind=kind,address_valid_ps=t,request_ps=None,beats_expected=r.get('beats'),beats_accepted=0)
    address_present[addrkey]=row
    if kind=='AW':aw[port].append(row);rows.append(row)
   row=address_present[addrkey]
   if fire:
    row['request_ps']=t;address_present.pop(addrkey)
    if kind=='AR':reads[key].append(row);rows.append(row)
    elif 'first_wvalid_ps' in row:row['AW_accept_to_WVALID_ns']=(row['first_wvalid_ps']-t)/1000
  elif kind=='R' and r['valid']:
   if not reads[key]:issues.append(dict(time_ps=t,issue='R_without_observed_AR',port=port,id=key[1]));continue
   row=reads[key][0]
   if r.get('last') and 'last_present_ps' not in row:row['last_present_ps']=t;row['AR_to_RLAST_ns']=(t-row['request_ps'])/1000
   if fire:
    row['beats_accepted']+=1
    if r.get('last'):
     row['last_accept_ps']=t;row['AR_to_RLAST_accept_ns']=(t-row['request_ps'])/1000;reads[key].popleft()
     if row['beats_expected'] and row['beats_accepted']!=row['beats_expected']:issues.append(dict(time_ps=t,issue='R_beat_count_mismatch',port=port,id=key[1]))
  elif kind=='W' and r['valid']:
   if not aw[port]:issues.append(dict(time_ps=t,issue='W_before_any_observed_AWVALID; cannot correlate without earlier capture',port=port));continue
   row=aw[port][0]
   if 'first_wvalid_ps' not in row:
    row['first_wvalid_ps']=t;row['AW_to_WVALID_ns']=(t-row['address_valid_ps'])/1000
    if row['request_ps'] is not None:row['AW_accept_to_WVALID_ns']=(t-row['request_ps'])/1000
   if fire:
    row['beats_accepted']+=1
    if r.get('last'):
     row['last_accept_ps']=t;aw[port].popleft();bwait[port,row['id']].append(row)
     if row['beats_expected'] and row['beats_accepted']!=row['beats_expected']:issues.append(dict(time_ps=t,issue='W_beat_count_mismatch',port=port,id=row['id']))
  elif kind=='B' and fire:
   if bwait[key]:row=bwait[key].popleft();row['B_accept_ps']=t
   else:issues.append(dict(time_ps=t,issue='B_without_completed_W',port=port,id=key[1]))
 def dist(name):
  values=sorted(r[name] for r in rows if name in r)
  return dict(count=len(values),min_ns=min(values) if values else None,p50_ns=values[(len(values)-1)//2] if values else None,p95_ns=values[math.ceil(.95*len(values))-1] if values else None,max_ns=max(values) if values else None)
 return dict(AR_to_RLAST=dist('AR_to_RLAST_ns'),AR_to_RLAST_accept=dist('AR_to_RLAST_accept_ns'),AW_to_WVALID=dist('AW_to_WVALID_ns'),AW_accept_to_WVALID=dist('AW_accept_to_WVALID_ns'),issues=issues,incomplete=sum(r['request_ps'] is None or 'last_accept_ps' not in r or (r['kind']=='AW' and 'B_accept_ps' not in r) for r in rows),scope='AR accepted request; AW first VALID and accepted-AW both recorded; WVALID independent of AWREADY'),rows

def analyze(path,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 meta={};stats={};samples=[];events=[];last_time={};bubble=[];run={}
 for r in records(path):
  if r['type']=='meta':meta=r;continue
  if r['type']=='event':events.append(r);continue
  if r['type']!='sample':raise ValueError('unknown trace record')
  ch=r['channel'];t=r['time_ps'];dt=r['period_ps']
  if t<=last_time.get(ch,-1):raise ValueError(f'nonmonotonic/duplicate sample {ch} {t}')
  last_time[ch]=t
  if r['valid'] not in (0,1) or r['ready'] not in (0,1) or dt<=0:raise ValueError('invalid handshake/period')
  s=stats.setdefault(ch,dict(samples=0,observed_ps=0,active_ps=0,valid_ps=0,handshakes=0,blocked_ps=0,bubble_ps=0,cache_miss_ps=0,bytes=0,ops=0,capacity_ops=0,raw_causes_ps=collections.Counter(),primary_causes_ps=collections.Counter()))
  s['cache_miss_ps']+=dt*int(bool(r.get('cache_miss',r.get('dcache_miss',0))));s['samples']+=1;s['observed_ps']+=dt;s['active_ps']+=dt*r.get('active',1);s['valid_ps']+=dt*r['valid']
  fire=r['valid'] and r['ready'];s['handshakes']+=int(fire);s['blocked_ps']+=dt*int(r['valid'] and not r['ready'])
  if fire:s['bytes']+=r.get('bytes',0);s['ops']+=r.get('ops',0);s['capacity_ops']+=r.get('capacity_ops',0)
  is_bubble=bool(r.get('active',1) and not fire);mask=r.get('stall_mask',0)
  if is_bubble:
   s['bubble_ps']+=dt;names=[name for bit,name in CAUSES.items() if mask&bit]
   for name in names:s['raw_causes_ps'][name]+=dt
   primary=names[0] if names else 'unclassified';s['primary_causes_ps'][primary]+=dt
   key=(mask,primary)
   if ch in run and run[ch]['end_ps']==t and run[ch]['key']==key:run[ch]['end_ps']=t+dt
   else:
    if ch in run:bubble.append(run.pop(ch))
    run[ch]=dict(channel=ch,start_ps=t,end_ps=t+dt,key=key,cause=primary)
  elif ch in run:bubble.append(run.pop(ch))
  samples.append(r)
 bubble.extend(run.values())
 for s in stats.values():
  s['utilization']=s['handshakes']/s['samples'];s['payload_GBs']=s['bytes']/s['observed_ps']*1000;s['useful_TOPS']=s['ops']/s['observed_ps'];s['scheduler_capacity_TOPS']=s['capacity_ops']/s['observed_ps']
 diagnoses=[]
 mac=stats.get('mac.issue')
 if mac:
  causes=mac['primary_causes_ps'];total=mac['active_ps'] or 1
  actions={'wait-data':'Trace upstream load completion and path latency; check request-ahead/slot reservation before increasing MAC count.',
   'no-credit':'Compare slot occupancy/credit RTT with configured register slots; sweep register size while holding BW fixed.',
   'bank-conflict':'Inspect physical subbank aliases and read/write arbitration; sweep mapping/subbanks, keeping capacity separate.',
   'OIC-conflict':'Inspect atomic multi-acquire, counter-bank aliases and event FIFO; sweep OIC ports/banking.',
   'consumer-stall':'Inspect TARGETR drain/vector/AXI consumer backpressure before adding producer resources.',
   'control-starved':'Check real per-hart command throughput and clock crossing; Rocket frequency is a candidate only if the measured control path limits issue.',
   'cache-miss':'Check real I/D-cache miss counters and control instruction footprint; cache size benefit requires Rocket trace/cache sweep.',
   'memory-wait':'Correlate AR-to-RLAST, AW-to-WVALID, MO occupancy, burst sizes and shared service.'}
  for cause,ps in sorted(causes.items(),key=lambda x:-x[1]):
   diagnoses.append(dict(cause=cause,fraction_of_active=ps/total,evidence_channel='mac.issue',evidence_ps=ps,recommendation=actions.get(cause,'Unclassified bubble: add upstream completion/credit probes before attribution.'),status='candidate_requires_counterfactual_or_RTL_confirmation'))
 axi=correlate_axi(samples)
 available=meta.get('provenance',{})
 summary=dict(schema_version=1,source=str(path),meta=meta,channels=stats,diagnoses=diagnoses,axi_latency=axi[0],
  caveats=['Traffic-agent traces do not establish Rocket IPC/cache performance.','Bubble causes may overlap; primary uses documented bit priority, raw counts must not be summed.','Per-channel rates use that channel observation interval; no cross-domain cycle summation.','useful_TOPS applies only to explicitly tagged useful ops, not fabricated matmul output correctness.'])
 (out/'axi_transactions.json').write_text(json.dumps(axi[1],indent=2)+'\n')
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 clean=[{k:v for k,v in r.items() if k!='key'} for r in sorted(bubble,key=lambda x:-(x['end_ps']-x['start_ps']))]
 (out/'bubbles.json').write_text(json.dumps(clean,indent=2)+'\n')
 chrome=[]
 for r in clean[:10000]:chrome.append(dict(name=r['cause'],cat='bubble',ph='X',ts=r['start_ps']/1e6,dur=(r['end_ps']-r['start_ps'])/1e6,pid=1,tid=r['channel'],args={'start_ps':r['start_ps'],'end_ps':r['end_ps']}))
 for e in events:chrome.append(dict(name=e['name'],ph='i',s='t',ts=e['time_ps']/1e6,pid=1,tid='events',args=e))
 (out/'chrome_trace.json').write_text(json.dumps({'traceEvents':chrome,'displayTimeUnit':'ns'}))
 # Preserve full handshake samples for an offline, zoomable waveform; no CDN/network.
 compressed=[];last={}
 for r in samples:
  ch=r['channel'];key=json.dumps({k:v for k,v in r.items() if k not in ('time_ps','period_ps')},sort_keys=True)
  prev=last.get(ch)
  if prev and prev[0]==key and prev[1]['time_ps']+prev[1]['duration_ps']==r['time_ps'] and prev[1]['period_ps']==r['period_ps']:
   prev[1]['duration_ps']+=r['period_ps'];prev[1]['repeat_count']+=1
  else:
   merged=dict(r,duration_ps=r['period_ps'],repeat_count=1);compressed.append(merged);last[ch]=(key,merged)
 payload=json.dumps(dict(summary=summary,samples=compressed,bubbles=clean[:500],events=events),separators=(',',':')).replace('<','\\u003c')
 template=Path(__file__).with_name('viewer.html').read_text()
 (out/'workload.html').write_text(template.replace('__TRACE_DATA__',payload))
 lines=['# Workload analysis', '',f'Source: `{path}`',f'Provenance: `{json.dumps(available)}`','', '| Channel | Samples | Handshakes | Blocked ns | Payload GB/s | Useful TOPS |','|---|---:|---:|---:|---:|---:|']
 for ch,s in stats.items():lines.append(f'| {ch} | {s["samples"]} | {s["handshakes"]} | {s["blocked_ps"]/1000:.3f} | {s["payload_GBs"]:.3f} | {s["useful_TOPS"]:.3f} |')
 lines+=['','## Bubble candidates','']+[f'- {d["cause"]}: {d["fraction_of_active"]:.1%} of active window. {d["recommendation"]}' for d in diagnoses]
 lines+=['','Interpretation limits:']+['- '+x for x in summary['caveats']]
 (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
 return summary

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('trace',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();s=analyze(a.trace,a.out);print('Analyzed',len(s['channels']),'channels ->',a.out)
