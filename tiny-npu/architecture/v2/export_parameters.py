#!/usr/bin/env python3
"""Refresh current default/x2/x4 values without retaining stale profile keys."""
import csv,json
from pathlib import Path
from analyze import profile
D=Path(__file__).parent
old={r['parameter']:r for r in csv.DictReader((D/'parameters.csv').open())}
ps=[profile(s) for s in (1,2,4)]
special={
 'SRAM_PORT':'1RW',
 'AXI_DATA_BITS':'128,256,512; default 256',
 'AXI_PORTS':'1,2,4,8; bandwidth/QoS constrained',
 'PATH_LATENCIES_CYCLES':'per-path nonnegative integers; independent clocks',
 'SUBBANK_ISSUE_II_CYCLES':'1,2,4,8,16; PDK constrained',
 'L0_REG_PATH_LATENCY_CYCLES':'10,16,32,64,128,256; arbitrary supported integer',
 'SRCC_SLOTS':'8,16,32; credit RTT sizing',
 'L0_CONFLICT_EFFICIENCY':'0 < eta <= 1; trace calibration required',
 'SLOT_SIZING_POLICY':'AUTO,FIXED8',
 'JOB_DISPATCH_CYCLES':'nonnegative integer',
}
# Parameter descriptions are Korean, including newly introduced fields.
kr={
 'SRAM_PORT':'물리 sub-bank당 read 또는 write 하나를 수락하는 single port. R/W 합산 BW로 계산.',
 'AXI_DATA_BITS':'AXI4 RDATA/WDATA 폭. 기본256bit이며 port 수·clock과 함께 방향별 BW 계산.',
 'AXI_PORTS':'독립 AXI port 수. DRAM 공유 BW는 별도 제약.',
 'PATH_LATENCIES_CYCLES':'경로별 독립 latency. L0/MAC/vector/AXI domain을 구분해 ns로 환산.',
 'SUBBANK_ISSUE_II_CYCLES':'Single-port macro 요청 간격. 응답 latency와 독립.',
 'L0_REG_PATH_LATENCY_CYCLES':'L0↔register 명목 지연. slot/credit은 최대 설계 지연으로 sizing.',
 'SRCC_SLOTS':'C 입력 슬롯 수. multicycle 왕복과 4-context 완료 burst 흡수.',
 'L0_CONFLICT_EFFICIENCY':'Sub-bank 충돌·중재 실효율. 기본0.8은 trace 검증 전의 계획 가정.',
 'SLOT_SIZING_POLICY':'Credit RTT로 슬롯 재계산. FIXED8은 슬롯 부족에 따른 stall 검토.',
 'JOB_DISPATCH_CYCLES':'명령 수락·dispatch 고정 비용. MAC clock domain.'}
def enc(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(dict,list,bool)) else str(v)
rows=[]
for k,v in ps[0].items():
 r=dict(old.get(k,{}));r.update(parameter=k,default=enc(v),x2=enc(ps[1][k]),x4=enc(ps[2][k]))
 r.setdefault('group',next((a for a in ('AXI','DMA','OIC','TC','L0','VECTOR','MAC') if k.startswith(a)),'System / derived'))
 r.setdefault('allowed_or_rule','기본값·파생 관계 참조; 구현 지원 범위와 연관 제약 검증')
 r.setdefault('description','RevB 구성 또는 파생값. 연관 제약·모델/RTL 검증을 적용.')
 if 'CYCLES' in k:r['description']='경로 또는 기능 지연(cycles). clock domain·II·credit을 구분하고 변경 시 성능 재계산.'
 if k in special:r['allowed_or_rule']=special[k];r['description']=kr[k]
 rows.append(r)
with (D/'parameters.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['parameter','group','default','x2','x4','allowed_or_rule','description'],lineterminator='\n');w.writeheader();w.writerows(rows)
print('Current parameters:',len(rows))
