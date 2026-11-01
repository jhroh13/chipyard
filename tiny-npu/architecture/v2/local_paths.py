#!/usr/bin/env python3
"""Single-port subbank, variable latency and AXI channel budget equations."""
from pathlib import Path
import math,json,csv
OUT=Path(__file__).resolve().parent

def pow2ceil(n):return 1<<(max(1,int(n))-1).bit_length()
def path_budget(latency,contexts=None,group_ii=32,oic_latency=None):
 if contexts is None or oic_latency is None:
  from configuration import load_profile
  p=load_profile()
  if contexts is None:contexts=p['MAC_ACC_CONTEXTS']
  if oic_latency is None:oic_latency=p['OIC_RESPONSE_LATENCY_CYCLES']
 rtt=2*latency+oic_latency
 minimum_slots=contexts+math.ceil(rtt/group_ii)
 slots=pow2ceil(max(2*contexts,minimum_slots))
 rates={'SRCA':160,'SRCB':320,'SRCC':1280,'TARGETR':1280}
 group_bytes={'SRCA':5440,'SRCB':10560,'SRCC':40960,'TARGETR':40960}
 buffers={n:pow2ceil(rate*latency+contexts*group_bytes[n]) for n,rate in rates.items()}
 return dict(path_latency_cycles=latency,credit_RTT_cycles=rtt,minimum_slots=minimum_slots,
             configured_slots=slots,reserved_buffer_bytes=buffers,
             vector_inflight_min=latency,scope='latency-hiding lower-bound sizing, not guaranteed conflict-free RTL')
def axi_budget(ports,clock_hz=625e6,width=256,eff=.60):
 per_direction=width/8*clock_hz*eff/1e9
 ai=799.219512195122;read_fraction=25/41;write_fraction=16/41
 # Shared-service is the conservative selected DRAM arbitration contract.
 shared=ports*per_direction
 duplex=min(ports*per_direction/read_fraction,ports*per_direction/write_fraction)
 return dict(ports=ports,data_bits=width,clock_MHz=clock_hz/1e6,
  raw_per_direction_GBs=ports*width/8*clock_hz/1e9,
  payload_per_direction_GBs=ports*per_direction,
  conservative_shared_service_GBs=shared,duplex_channel_bound_GBs=duplex,
  P0_10TOPS_required_read_GBs=7.62939453125,P0_10TOPS_required_write_GBs=4.8828125,
  conservative_roofline_TOPS=min(20.48,ai*shared/1000),
  duplex_roofline_TOPS=min(20.48,ai*duplex/1000),
  caveat='Duplex sum requires concurrent R/W across jobs/strips and sufficient shared DRAM bandwidth; ports alone do not create DRAM bandwidth')
def main():
 paths=[path_budget(n) for n in (1,10,16,32,64,128,256)]
 axi=[axi_budget(p) for p in (1,2,4)]
 (OUT/'local_path_results.json').write_text(json.dumps(dict(paths=paths,AXI=axi),indent=2))
 with (OUT/'local_latency.csv').open('w',newline='') as f:
  w=csv.writer(f,lineterminator='\n');w.writerow(['path_cycles','credit_RTT','min_slots','configured_slots','SRCA_reserved_B','SRCB_reserved_B','SRCC_reserved_B','TARGETR_reserved_B'])
  for r in paths:w.writerow([r['path_latency_cycles'],r['credit_RTT_cycles'],r['minimum_slots'],r['configured_slots']]+[r['reserved_buffer_bytes'][k] for k in ('SRCA','SRCB','SRCC','TARGETR')])
 for r in paths:print(r['path_latency_cycles'],'cycles -> slots',r['configured_slots'],'RTT',r['credit_RTT_cycles'])
 for r in axi:print('AXI',r)
if __name__=='__main__':main()
