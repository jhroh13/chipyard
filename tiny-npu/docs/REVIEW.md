> 이전 검토 기록입니다. 현재 P0 지속10TOPS 후보와 구현 상태는 [통합 HDD](TINY_NPU_HDD_AND_ROADMAP.md)를 우선 참고하십시오.

# 구현 전 추가 검토 사항

현재 단계는 HDD와 실행 가능한 성능 모델이다. Matmul RTL·전체 모델 추론·ASIC PPA 검증은 아직 없다.

| 우선순위 | 항목 | 확정 또는 검증할 내용 |
|---|---|---|
| P0 | 성능 목표 | 10.24 TOPS 피크와 workload별 지속 처리량을 구분 |
| P0 | 대표 workload | M/N/K, batch, 재사용, 출력 포맷과 latency 목표 |
| P0 | 수치 명세 | OCP MXINT8, E8M0, 그룹 스케일, rounding/overflow/subnormal, bit-exact 모델 |
| P0 | DRAM | 60% 효율 이후 유효10GB/s, CPU 경쟁·refresh·read/write 전환·QoS 검증 |
| P0 | SRAM | 실제 1R1W 매크로와 1GHz, banking·배선·shallow partial bank 효율 |
| P0 | FP32 후단 | 160 results/cycle, 결과 burst, C RMW hazard와 forwarding |
| P1 | Packing | B 패킹과 activation quantization의 CPU 시간·추가 트래픽 |
| P1 | DMA | 실제 burst 분포, 작은 scale 요청, reorder, MO/FIFO, 4KiB 경계 |
| P1 | 재사용 | 공통 A/B broadcast, C 유지, partial bypass, macro 스케줄 |
| P1 | 보호·복구 | 주소 범위 검사, ownership, abort/reset, 오류 응답 |
| P1 | 확장 | ×2/×4의 포트 폭, 배선·전력·타이밍을 별도로 검증 |
| P1 | PPA | 공정·SRAM compiler·면적·전력 한도와 TOPS/W |

메모리 효율60%는 sustained payload 손실의 정의로 사용하며 700ns 초기 latency/MO 부족과 중복 계산되지 않도록 실측 정의를 맞춘다. Write B tail700ns는 임시 가정이다. 현재 모델은 SRAM conflict, pipeline fill/drain, CPU packing·RoCC 비용을 직접 모델링하지 않는다.

권장 순서: 대표 workload·수치 명세 확정 → PE/SRAM/FP32 후단 합성 → 단일 타일 RTL → DMA·다중 배열 → 전체 모델 추론.
