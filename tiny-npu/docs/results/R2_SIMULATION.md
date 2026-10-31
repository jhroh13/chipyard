# R2 / SRAM slice / DMA 전단 검증 결과

Verilator5.022 의실제 RTL 시뮬레이션이다. CPU 소프트웨어모델만실행한결과가아니다. 다만 stream-fed32×32 출력 tile 구조이며전체 AXI/RoCC/8MiBSRAM/LLM 및지속 10TOPS 는검증하지않았다.

## Matmul 결과

| Arrays | Jobs | K | 최종 FP32 비교 | 전체 회귀 cycles | 결과 |
|---|---:|---|---:|---:|---|
| 1 | 8 | 32/64/128/4096 포함 | 8,192 | 6614 | PASS |
| 2 | 8 | 32/64/128/4096 포함 | 16,384 | 6614 | PASS |
| 10 | 8 | 32/64/128/4096 포함 | 81,920 | 6614 | PASS |

총 24 개 job,106,496 개의최종 FP32 값이독립 Python 기준값과 bit-exact 일치했다. 기준모델은각 K=32dot 에개별 E8M0scale 을적용하고 FP32 로 round 한후, K 순서대로매 add 마다 RNE 를적용한다. 서로다른 blockscale, cancellation,NaN,Inf−Inf,subnormal 을포함한다. 모든테스트에서입력·출력 stall 을발생시키고 ID/row/last 및출력안정성을검사했다.

회귀 cycles 는 8 개서로다른 job 과결정적 randomstall 을포함한총시간이다. 별도 P0benchmark 의 latency 나 1GHz 물리타이밍/TOPS 실증으로환산하지않는다.

## FP32 pipeline

20,000 개입력쌍을비교했다. 모든 edgepair(±0,subnormal 경계,최소 normal,±1,maxfinite,±Inf,NaN,half-ULP)와 seed20261102 의 random32-bit 패턴을포함한다. 처음 128 개는무 stall 조건에서 4cyclelatency 와 II1 을 assert 하고,이후 randombackpressure 에서 tag/data 보존을검사했다. PASS. IEEE exception flags 는없고 RNE 만지원한다.

## C SRAM / scoreboard

lane 별 32×32-bit1R1WSRAM 과 4 단계 adder 를연결했다. 같은 row 의 1+2−3=0,최소 subnormal 두개합,Inf−Inf 를검사했다. scoreboard 가 20cycles 의의존성 stall 을발생시키고올바른 3 개결과를반환했다. SRAMread 는현재 1cycle 이며목표 256-bit 전체 banking 은후속작업이다.

## DMA frontend

5000B@0xFC0 를 64B/4096B/840B 의세 request 로분할하고 4KiB 경계·tailbeat 수를검사했다. Unaligned command 거부와 zero-lengthno-op 도검사했다. 8192Bcredit 에서 4096B 두개예약후추가발행차단,retire+issue 동시 ID 재사용,전체 credit 반환,미할당 ID 반환 fault 를검사했다. Requeststall 중주소/길이유지도검사했다. PASS. 실제 AXI 채널과 700ns 메모리모델은아직연결하지않았다.

## 생성과 재현

기본 10 배열 R2wrapper 를 elaborate/lint 하여 exit0 을확인했다. x2/x4wrapper 는생성했으나 R2 전체기능시뮬레이션은하지않았다. 생성 RTL/manifest 는`generated-gemm/`에보존한다.

```bash
cd /workspace/TINY-NPU/tiny-npu
source scripts/env.sh
make extended EXT_ARRAYS="1 2 10"
make generate-gemm
make lint-gemm
```

다음: 전체 SRAM·스케줄러 → 실제 AXI DMA → RoCC → 기준 GEMM 의지속 10TOPS 검증 → MLP/LLM 연결. 현재모델의 13.4775TOPS 예측을실제통합 RTL 결과와혼동하지않는다.
