#!/usr/bin/env python3
"""Architecture RevB planning model; no new RTL/core-count validation implied."""
from pathlib import Path
import csv,json,math,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'model'))
from p0_model import profile as previous_profile
from spec_model import simulate
OUT=Path(__file__).resolve().parent

def profile(scale=1,cores=8):
 assert scale in (1,2,4) and cores in (6,8)
 p=previous_profile(scale);s=scale;a=10*s
 p.update(ARCHITECTURE_REV='B2_SINGLE_PORT',ROCKET_CORES=cores,ROLE_COUNT=8,
  CORE_COUNT_STATUS='8 confirmed by user; six-core mapping is optional',
  L0_BYTES=10*1024**2*s,SRAM_TOTAL_BYTES=10*1024**2*s,
  OPERAND_BYTES=3*1024**2*s,C_BYTES=5*1024**2*s,
  PARTIAL_BYTES=1024**2*s,META_BYTES=1024**2*s,
  MAC_FMA_PIPE_CYCLES=4,MAC_ACC_CONTEXTS=4,
  SRCA_SLOTS=8,SRCB_SLOTS=8,SRCC_SLOTS=8,TARGETR_SLOTS=8,
  L0_REG_PATH_LATENCY_CYCLES=16,L0_REG_LATENCY_ENUM=[10,16,32,64,128,256],
  L0_REG_LATENCY_MAX_CYCLES=32,L0_REG_CREDIT_RTT_CYCLES=34,LOCAL_VECTOR_ID_BITS=7,LOCAL_MAX_INFLIGHT_VECTORS=128,
  SRCA_DATA_BITS=4,SRCB_DATA_BITS=8,SRCC_DATA_BITS=32,TARGETR_DATA_BITS=32,SRCC_FORMAT='TF32_CONTAINER32',TARGETR_FORMAT='TF32_CONTAINER32',
  FINAL_L0_FORMAT='FP32',FLOAT_VECTOR_OWNER_HART=7,
  INTERNAL_ACC_FORMAT='LQ16_S1_E7_M8',INTERNAL_MODE_ENUM=['LQ16_S1_E7_M8','TF32_S1_E8_M10'],
  INTERNAL_EXP_BIAS=63,INTERNAL_MANTISSA_BITS=8,INTERNAL_EXP_BITS=7,
  MAC_ARITHMETIC='FMA_RNE_PER_MAC',FP32_INTERNAL_ACC_ALLOWED=False,
  TF32_STORE_ROUNDING='RNE',TF32_MANTISSA_BITS=10,TF32_CONTAINER_BITS=32,
  TC_CONTEXTS_PER_ENGINE=8,TC_DIMENSIONS=6,TC_ADDRESS_BITS=64,TC_INDEX_BITS=32,
  OIC_COUNT=256,OIC_BITS=64,COMMAND_QUEUE_DEPTH=16,
  VECTOR_LANES=32*s,VECTOR_CLOCK_HZ=1_000_000_000,VECTOR_ISSUE_II_CYCLES=1,VECTOR_MODE='FP32_AND_TF32_ROUNDED_FP32',
  C_RESIDENCY_MODE='L0_KBLOCK_TF32_SPILL',COMMAND_DISPATCH='PERSISTENT_HARDWARE_LOOPS')
 # L0 allocation, depth fixed while bank counts scale.
 regions=[dict(name='A',banks=16*s,subbanks=2,width=256,depth=1024,bytes=1*1024**2*s),
          dict(name='B',banks=32*s,subbanks=2,width=256,depth=1024,bytes=2*1024**2*s),
          dict(name='C',banks=40*s,subbanks=4,width=256,depth=1024,bytes=5*1024**2*s),
          dict(name='scratch',banks=32*s,subbanks=2,width=256,depth=512,bytes=1*1024**2*s),
          dict(name='scale_metadata',banks=32*s,subbanks=2,width=128,depth=1024,bytes=1*1024**2*s)]
 for r in regions:
  assert r['banks']*r['subbanks']*r['width']//8*r['depth']==r['bytes']
  r['physical_macros']=r['banks']*r['subbanks']
  r['combined_RW_GBs_at_1GHz']=r['physical_macros']*r['width']/8
 assert sum(r['bytes'] for r in regions)==p['L0_BYTES']
 regs=dict(SRCA=a*p['SRCA_SLOTS']*(512+32),SRCB=a*p['SRCB_SLOTS']*(1024+32),SRCC=a*p['SRCC_SLOTS']*4096,TARGETR=a*p['TARGETR_SLOTS']*4096)
 p['NEAR_MAC_REGFILE_BYTES']=regs;p['NEAR_MAC_REGFILE_TOTAL_BYTES']=sum(regs.values())
 p['PE_ACC_CONTEXT_BYTES']=a*1024*p['MAC_ACC_CONTEXTS']*2
 p['SINGLE_CONTEXT_K32_LATENCY_CYCLES']=32*p['MAC_ACC_CONTEXTS']+p['MAC_FMA_PIPE_CYCLES']
 # Conservative interleaved-FMA result-drain tail; not measured RTL latency.
 p['PANEL_PIPELINE_OVERHEAD_CYCLES']=p['MAC_ACC_CONTEXTS']*32+8
 p['L0_REGIONS']=regions
 p.update(OPERAND_BANKS=48*s,OPERAND_BANK_DEPTH=1024,PARTIAL_BANKS=32*s,PARTIAL_BANK_DEPTH=512,META_BANK_DEPTH=1024,
  C_BANK_DEPTH=1024,C_SUBBANKS=4,A_SUBBANKS=2,B_SUBBANKS=2,SCRATCH_SUBBANKS=2,META_SUBBANKS=2,
  L0_TOTAL_SUBBANKS=sum(r['physical_macros'] for r in regions),SRAM_PORT='1RW',
  AXI_DATA_BITS=256,AXI_PORTS=2*s,AXI_ID_BITS=6,AXI_MAX_BURST_BEATS=128,
  L0_ADDRESS_BITS=math.ceil(math.log2(p['L0_BYTES'])),L0_TOTAL_BANKS=sum(r['banks'] for r in regions),
  L0_BANK_MAPPING='WORD_INTERLEAVED',C_LAYOUT='GROUP_ROW_ARRAY_COL',
  AB_LAYOUT='K_PANEL_MAJOR',REG_A_BANKS=32,REG_B_BANKS=32,REG_C_BANKS=32,
  VECTOR_LUT_ENTRIES=1024,VECTOR_LUT_PORTS=32*s,VECTOR_LUT_REPLICAS=32*s,
  OIC_BANKS=16,OIC_REQUEST_PORTS=16,OIC_RESPONSE_LATENCY_CYCLES=2,OIC_EVENT_FIFO_DEPTH=32,
  OIC_MAX_WAIT_CONDITIONS=4,OIC_MAX_CREDIT_CONDITIONS=4,OIC_MAX_SIGNALS=4,
  OIC_OPERATION_BUDGET_PER_GROUP=32,TC_ISSUE_II_CYCLES=1,
  FINAL_FP32_STRIP_ROWS=32,FINAL_FP32_STRIP_SLOTS=2,FINAL_TARGETR_ROUTE='FINAL_VIA_L0',
  ROW_MAJOR_DDR_OUTPUT=True,STATUS='architecture_reference_not_integrated_RTL')
 p['PEAK_GROUP_RATE_PER_SECOND']=1e9/32
 p['L0_OPERAND_GBs_PEAK']=a*50
 p['L0_C_READ_GBs_PEAK']=a*128
 p['L0_C_WRITE_GBs_PEAK']=a*128
 p['VECTOR_PEAK_ELEMENTS_PER_SECOND']=p['VECTOR_LANES']*1e9
 for old_key in list(p):
  if old_key.startswith('FP32_'):p.pop(old_key)
 p.update(PROFILE_NAME='P0_REVB_8CTRL_LQ16',PROFILE_STATUS='architecture_not_integrated_RTL',
  INTERNAL_ACC_LANES=a*32,RESULT_ELASTIC_FIFO_BYTES=16384*s,
  AXI_PROTOCOL='AXI4',AXI_BURST='INCR',AXI_4K_SPLIT=True,AXI_STRB_BITS=32,
  AXI_ARCACHE=2,AXI_AWCACHE=2,AXI_ARPROT=0,AXI_AWPROT=0,AXI_QOS=0,AXI_USER_BITS=0,
  DMA_READ_CHANNELS=2,DMA_WRITE_CHANNELS=1,DMA_RESPONSE_REORDER=True,
  TC_STRIDE_BITS=64,TC_UNIT_BITS_ENUM=[4,8,16,32,64],TC_COMMIT_TRACKING=True,
  OIC_EPOCH_BITS=64,OIC_ATOMIC_MULTI_ACQUIRE=True,OIC_READY_COMPARE='GE',
  OIC_STALE_EPOCH_POLICY='REJECT',JOB_ID_BITS=64,DESCRIPTOR_BYTES=256,
  DESCRIPTOR_ALIGNMENT_BYTES=64,CPU_COMMAND_MODE='ASYNC_TICKET',
  REGISTER_STORAGE_IMPLEMENTATION='DISTRIBUTED_BANKED_REGFILE',
  JOB_DISPATCH_CYCLES=64,L0_CLOCK_HZ=1_000_000_000,L0_CONFLICT_EFFICIENCY=0.8,SLOT_SIZING_POLICY='AUTO',
  L0_PORTS_PER_SUBBANK=1,L0_SIMULTANEOUS_RW_SAME_SUBBANK=False,L0_ECC='OFF',
  L0_ARBITRATION='PER_SUBBANK_VOQ_CREDIT',L0_RETURN_REORDER=True,
  L0_REQUEST_QUEUE_DEPTH_PER_SUBBANK=8,L0_STARVATION_BOUND_CYCLES=32,
  L0_C_READ_WRITE_PHASE_OFFSET=1,L0_SRAM_MACRO_READ_CYCLES=2,
  L0_XBAR_PIPE_CYCLES=4,L0_REGISTER_INGRESS_PIPE_CYCLES=4,
  PATH_LATENCIES_CYCLES={'SRCA':16,'SRCB':16,'SRCC':16,'TARGETR':16,'DMA_L0_COMMIT':16,'L0_AXI_READ':16,'VECTOR_READ':16,'VECTOR_WRITE':16,'TC':2,'OIC':2,'FMA':4,'LUT':4,'FORMAT':1,'AXI_CDC':4},
  SUBBANK_ISSUE_II_CYCLES=1,PATH_LATENCY_DOMAIN='L0:SRCA/SRCB/SRCC/TARGETR/DMA/VECTOR_READ_WRITE/TC/OIC;MAC:FMA;VECTOR:LUT/FORMAT;AXI:CDC',
  LOCAL_BOUNDS_LATENCY_POLICY='CREDIT_BACKPRESSURE_NO_DATA_LOSS',
  L0_ARBITER_PIPE_CYCLES=2,L0_REQUEST_QUEUE_TARGET_CYCLES=2,L0_ACK_PIPE_CYCLES=2,
  NUMERIC_FAULT_POLICY='REPORT_AND_PROPAGATE',LQ16_SUBNORMAL='GRADUAL',
  ROUND_MODE='RNE',TARGETR_PACKED19_SUPPORTED=False,
  ROLE_TO_HART={str(i):i-1 for i in range(1,9)})
 p['VECTOR_LUT_STEADY_GATHER_LIMIT']='one element/lane/cycle only if LUT has sufficient ports/replicas'
 return p

def main():
 ps={str(s):profile(s) for s in (1,2,4)};results=[]
 for s,p in ps.items():
  for bw in (10*int(s),20*int(s)):
   pp=dict(p,DMA_PAYLOAD_TARGET_GBS=bw)
   for c_mode in ('ZERO','LOAD_EXISTING'):
    # Base engine supports C=0 traffic only; LOAD_EXISTING is a lower-bound roofline.
    m=p['REFERENCE_M'];n=p['REFERENCE_N'];k=p['REFERENCE_K']
    ops=2*m*n*k;ab=(17*m+33*n)*k/32;c=4*m*n
    traffic=ab+c+(c if c_mode=='LOAD_EXISTING' else 0)
    row=dict(scale=int(s),M=m,N=n,K=k,C_init=c_mode,payload_target_GBs=bw,
      peak_TOPS=p['PEAK_TOPS'],external_bytes=int(traffic),AI_ops_byte=ops/traffic,
      roofline_TOPS=min(p['PEAK_TOPS'],ops/traffic*bw/1000),
      bandwidth_only_time_us=traffic/(bw*1e9)*1e6)
    row.update(event_model_TOPS=None,event_model_us=None,timing_model='Use sweep_l0.py for multicycle single-port timing; this table is roofline only')
    results.append(row)
 # Same default workload, aggregate DDR20GB/s, final FP32 result vector pass.
 p=ps['1'];m=n=1024;k=4096;ops=2*m*n*k
 vector_pass_ns=math.ceil(m*n/p['VECTOR_LANES'])*p['VECTOR_ISSUE_II_CYCLES']+p['PATH_LATENCIES_CYCLES']['VECTOR_READ']+p['PATH_LATENCIES_CYCLES']['VECTOR_WRITE']+p['PATH_LATENCIES_CYCLES']['LUT']+p['PATH_LATENCIES_CYCLES']['FORMAT']
 rate_at_10T=10e12/(2*k)
 aux=dict(default_vector_pass_ns=vector_pass_ns,
   vector_required_elements_per_second_at_10TOPS=rate_at_10T,
   vector_peak_elements_per_second=p['VECTOR_PEAK_ELEMENTS_PER_SECOND'],
   peak_MAC_input_vector_bytes_per_clock=10*(16+32+2),
   peak_C_bytes_per_clock_each_direction=10*128,
   target_10TOPS_min_AI_at_10GBs=1000,target_10TOPS_min_AI_at_20GBs=500,
   minimal_full_burst_MO_at_20GBs_700ns=math.ceil(1+20e9*700e-9/4096))
 (OUT/'profiles.json').write_text(json.dumps(ps,indent=2));(OUT/'analysis.json').write_text(json.dumps(dict(results=results,auxiliary=aux),indent=2))
 with (OUT/'performance.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=results[0].keys(),lineterminator='\n');w.writeheader();w.writerows(results)
 print('Base L0:',p['L0_BYTES'],'near-register bytes:',p['NEAR_MAC_REGFILE_TOTAL_BYTES'],'PE accumulator contexts:',p['PE_ACC_CONTEXT_BYTES'])
 for r in results:
  if r['scale']==1:print(r)
 print('Vector:',aux)
 print('L0 capacity/profile accounting: PASS; new architecture RTL not implemented')
if __name__=='__main__':main()
