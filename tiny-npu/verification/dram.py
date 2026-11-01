"""AXI traffic-agent model: AR handshake->first RLAST presentation >=700ns;
AW first VALID->first WVALID >=700ns (DMA launch policy independent of AWREADY).
One shared 256-bit payload service per AXI clock; turnaround and backpressure
reduce observed BW. Responses may reorder across IDs; W follows AW per port.
"""
import collections,copy,math,random


def run_axi(trace,cfg,p,seed=1):
 rng=random.Random(seed);period=round(1e12/p['AXI_CLOCK_HZ']);beat=p['AXI_DATA_BITS']//8;ports=cfg['ports']
 mode=cfg['bandwidth_mode']
 if mode=='effective':bw=cfg['effective_shared_GBs']
 elif mode=='raw':bw=cfg['raw_shared_GBs']*cfg['efficiency']
 else:raise ValueError('bandwidth_mode must be effective or raw')
 if not 0<bw<=beat/period*1000:raise ValueError('This conservative shared service model supports at most one payload beat per AXI clock')
 if cfg['read_mo']<=0 or cfg['write_mo']<=0:raise ValueError('MO must be positive')
 tx=[];queues={};issued={};completed={};bqueues={};bheld={};channel_last_payload={};master_w={}
 count=cfg['transactions_per_direction'];directions=cfg.get('directions',['R','W'])
 for port in range(ports):
  for kind in directions:
   q=[]
   number=cfg.get('read_transactions' if kind=='R' else 'write_transactions',count)
   for seq,i in enumerate(range(port,number,ports)):
    size=cfg['burst_bytes'][i%len(cfg['burst_bytes'])]
    if size<=0 or size>4096 or size%beat:raise ValueError('burst must be beat-aligned and <=4KiB')
    q.append(dict(port=port,kind=kind,id=seq+(0 if kind=='R' else 32),size=size,beats=size//beat,remaining=size//beat,arrival=2*seq,seq=seq))
   if kind=='W':master_w[port]=q[:]
   queues[port,kind]=collections.deque(q);issued[port,kind]=[];completed[port,kind]=0
  bqueues[port]=[];bheld[port]=None
 active=None;last_kind=None;turn_until=0;tokens=0.;read_order=[];bank_switches=0;max_mo={'R':0,'W':0};transfers=0
 def sample(t,ch,v,r,**kw):trace.sample(t,ch,v,r,period_ps=period,**kw)
 def active_count(port,kind):return sum(not x.get('retired') for x in issued.get((port,kind),[]))
 for cycle in range(100000):
  t=cycle*period
  # Independent AR/AW admissions. ID pools are distinct R/W ranges in this fixture.
  for port in range(ports):
   for kind in ('R','W'):
    q=queues.get((port,kind),collections.deque());candidate=q[0] if q and q[0]['arrival']<=cycle else None
    limit=cfg['read_mo' if kind=='R' else 'write_mo'];ready=active_count(port,kind)<limit
    if kind=='W':ready=ready and cycle>=cfg.get('aw_ready_holdoff_cycles',0)
    if candidate and kind=='W' and 'aw_valid_ps' not in candidate:
     candidate['aw_valid_ps']=t;candidate['eligible_ps']=t+cfg['aw_to_first_wvalid_ns']*1000
    if candidate and candidate['id']>=2**p['AXI_ID_BITS']:raise ValueError('fixture ID pool exceeds configured AXI width')
    sample(t,f'axi.p{port}.{"AR" if kind=="R" else "AW"}',bool(candidate),ready,id=candidate['id'] if candidate else 0,beats=candidate['beats'] if candidate else 0,beat_bytes=beat,address=(candidate['seq']*4096) if candidate else 0,active=int(bool(q)),stall_mask=2 if candidate and not ready else 0)
    if candidate and ready:
     q.popleft();candidate['request_ps']=t;candidate['issue_cycle']=cycle
     jitter=rng.randrange(cfg['read_jitter_ns']+1)*1000 if kind=='R' else 0
     if kind=='R':candidate['eligible_ps']=max(t,t+cfg['ar_to_rlast_ns']*1000+jitter-(candidate['beats']-1)*period)
     else:pass # W preparation began at AWVALID, independent of AWREADY
     issued[port,kind].append(candidate);tx.append(candidate)
     trace.event(t,'AR_ACCEPT' if kind=='R' else 'AW_ACCEPT',port=port,id=candidate['id'],bytes=candidate['size'],beats=candidate['beats'])
    max_mo[kind]=max(max_mo[kind],active_count(port,kind))
  eligible=[];writes={}
  for port in range(ports):
   for x in issued.get((port,'R'),[]):
    if not x.get('data_done') and t>=x['eligible_ps']:eligible.append(x)
   ws=[x for x in master_w.get(port,[]) if not x.get('data_done')]
   if ws:
    x=ws[0]
    if 'eligible_ps' in x and t>=x['eligible_ps']:
     writes[port]=x
     if 'request_ps' in x:eligible.append(x)
     if 'first_wvalid_ps' not in x:x['first_wvalid_ps']=t;trace.event(t,'WVALID_FIRST',port=port,id=x['id'])
  if active is None and eligible and cycle>=turn_until:
   if cfg['response_reorder']:
    # Cross-ID overtaking is legal; once a burst starts it is not interleaved.
    candidates=sorted(eligible,key=lambda x:(x['kind']=='R',x['seq']),reverse=True)
    chosen=candidates[0] if rng.random()<.7 else rng.choice(candidates)
   else:chosen=min(eligible,key=lambda x:x['request_ps'])
   if last_kind is not None and chosen['kind']!=last_kind:
    turn_until=cycle+cfg['turnaround_cycles'];bank_switches+=1;last_kind=chosen['kind']
   else:active=chosen;last_kind=chosen['kind']
  tokens=min(beat,tokens+bw*period/1000)
  r_ready={port:rng.random()>=cfg['consumer_stall_probability'] for port in range(ports)}
  for port in range(ports):
   read=active if active and active['port']==port and active['kind']=='R' else None
   w=writes.get(port);selected_w=active is w and w is not None
   credit=tokens+1e-9>=beat
   # RVALID is independent of RREADY and remains asserted with stable payload.
   rv=read is not None
   if rv and read['remaining']==1 and 'rlast_present_ps' not in read:read['rlast_present_ps']=t;trace.event(t,'RLAST_PRESENT',port=port,id=read['id'])
   rr=r_ready[port] and credit
   sample(t,f'axi.p{port}.R',rv,rr,id=read['id'] if read else 0,last=int(bool(read and read['remaining']==1)),bytes=beat,active=int(bool([x for x in issued.get((port,'R'),[]) if not x.get('retired')])),stall_mask=16 if rv and not rr else 128 if not rv else 0)
   wr=bool(selected_w and credit)
   sample(t,f'axi.p{port}.W',w is not None,wr,id=w['id'] if w else 0,last=int(bool(w and w['remaining']==1)),bytes=beat,active=int(bool(w)),stall_mask=16 if w and not wr else 0)
   x=read if rv and rr else w if wr else None
   if x:
    tokens-=beat;transfers+=beat;x['remaining']-=1
    if x['remaining']==0:
     x['data_done']=True;x['data_end_ps']=t;active=None
     if x['kind']=='R':
      x['retired']=True;read_order.append((port,x['seq']));trace.event(t,'RLAST_ACCEPT',port=port,id=x['id'])
     else:x['b_eligible_ps']=t+cfg['b_response_ns']*1000;bqueues[port].append(x);trace.event(t,'WLAST_ACCEPT',port=port,id=x['id'])
   if bheld[port] is None:
    bs=[x for x in bqueues[port] if t>=x['b_eligible_ps']]
    if bs:bheld[port]=max(bs,key=lambda x:x['seq']) if cfg['response_reorder'] else bs[0]
   b=bheld[port];br=rng.random()>=cfg['consumer_stall_probability']
   sample(t,f'axi.p{port}.B',b is not None,br,id=b['id'] if b else 0,active=int(bool(bqueues[port])))
   if b and br:
    b['retired']=True;b['b_accept_ps']=t;bqueues[port].remove(b);bheld[port]=None;trace.event(t,'B_ACCEPT',port=port,id=b['id'])
  if all(not q for q in queues.values()) and all(x.get('retired') for x in tx):break
 else:raise AssertionError('AXI fixture timeout/deadlock')
 reads=[x for x in tx if x['kind']=='R'];ws=[x for x in tx if x['kind']=='W']
 for x in reads:
  assert x['rlast_present_ps']-x['request_ps']>=cfg['ar_to_rlast_ns']*1000
 for x in ws:
  assert x['first_wvalid_ps']-x['aw_valid_ps']>=cfg['aw_to_first_wvalid_ns']*1000
 reorder=sum(1 for i,(port,seq) in enumerate(read_order) if any(p0==port and s0>seq for p0,s0 in read_order[:i]))
 elapsed=(cycle+1)*period
 return dict(scope='behavioral AXI agents, no real DMA/Rocket RTL',cycles=cycle+1,period_ps=period,elapsed_ps=elapsed,transactions=len(tx),bytes=transfers,
  effective_service_GBs=bw,achieved_shared_GBs=transfers/elapsed*1000,efficiency_applications=int(mode=='raw'),bandwidth_mode=mode,
  turnaround_switches=bank_switches,max_outstanding_per_port=max_mo,cross_ID_read_overtakes=reorder,
  read_latencies_ns=[(x['rlast_present_ps']-x['request_ps'])/1000 for x in reads],
  write_launch_latencies_ns=[(x['first_wvalid_ps']-x['aw_valid_ps'])/1000 for x in ws],
  AW_accept_to_WVALID_ns=[(x['first_wvalid_ps']-x['request_ps'])/1000 for x in ws],
  request_results=[{k:v for k,v in x.items() if k in ('kind','port','id','bytes','size','beats','request_ps','aw_valid_ps','rlast_present_ps','data_end_ps','first_wvalid_ps','b_accept_ps')} for x in tx])
