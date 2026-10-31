# RTL 및 성능 모델 검증 결과

기준일:2026-11-01(KST). Simulator:Verilator5.022. Matmul RTL 은 K=32 tile engine 이며 DMA/RoCC/전체 LLM 은포함하지 않는다.

## 기능 시뮬레이션

| Arrays | Cases | FP32 비교 수 | 실행 cycles | 입력/출력 II | 입력/출력 stall cycles | 결과 |
|---|---:|---:|---:|---|---|---|
| 1 | 12 | 12,288 | 638 | 32/32 | 116/220 | PASS |
| 5 | 12 | 61,440 | 638 | 32/32 | 116/220 | PASS |
| 10 | 12 | 122,880 | 638 | 32/32 | 116/220 | PASS |

총 36 개 case,196,608 개 FP32 결과를독립 Python 정수 dot+IEEEFP32packing 기준값과 bit-exact 비교했다. Zero,identity,maxproduct,16 종 FP4encoding,randomnormal,inactivearray,signedcancellation,invalidscaleNaN,gradualunderflow,overflow,randomscale,mixedextreme 를포함한다.

처음 4 개 tilegroup 은연속입력/출력 ready 조건에서 II32 를확인하고나머지는 seed20261101 의결정적 stall 패턴으로검증했다.입력 validhold,출력 valid/data/id/chunk 의 stall 중안정성,각 case 의전체결과수와 timeout 도검사했다.

10 배열의 II32 는 compute 구조상 10240MAC/cycle 에대응한다.1GHz 로환산한 20.48TOPS 는이론적 computepeak 이며 TB 의 1nsclock 이물리타이밍이나지속 systemTOPS 를검증하지는않는다.

SRAM 독립 template 는 128 개 byte-mask/read-write 비교를통과했다.1-cycle 동기 read/write-first 정책이며목표 2-cyclemacro/전체 8MiBSRAM 은연결전이다.

## P0 후보의 이벤트 모델

| Profile | 기준 M×N×K | 예상 TOPS | 예상 µs | 목표 TOPS |
|---|---|---:|---:|---:|
| ×1 | 1024×1024×4096 | 13.4775 | 637.355 | 10 |
| ×2 | 1536×1536×4096 | 26.9868 | 716.178 | 20 |
| ×4 | 2048×2048×4096 | 54.0184 | 636.075 | 40 |

이는 P0 설계후보가모델에서목표를넘는다는결과이다.기본 profile 은 20.48TOPSpeak/8MiB/유효 20GB/s 이며기존 2MiB/10GB/s 예산보다증가했다.기본 1024×1024×4096 의 P0 한도 858.993µs 에대해예상 637.355µs 이다.DMA·SRAMconflict·FP32K 누산·CPU/RoCC 비용이포함된 RTL 측정으로확인해야한다.

## 재현

```bash
cd /workspace/TINY-NPU/tiny-npu
source scripts/env.sh
make test
make sram
make model
make lint
```

각 raw 시뮬레이션출력과 summaryJSON,RTL SHA256 을이폴더에보존했다.Compilationwalltime 은성능지표가아니다.테스트는 PPA·FPGA·ASIC 합성·LLM 정확도·지속 10TOPS 실증을대체하지않는다.

## Parameter RTL generation / lint

P0 ×1/×2/×4 wrappers의10/20/40배열을Verilator로각각elaborate/lint하여모두exit0을확인했다.생성RTL,parameters.json,sourceSHA256manifest는`tiny-npu/generated/x1,x2,x4`에보존한다.이는40배열의전체기능시뮬레이션이나DMA/SRAM통합검증이아니다.기능테스트범위는위1/5/10배열이다.

## 설계 목표·파이프라이닝 갱신

P0를필수지속10 useful TOPS로명시했다.후속pipeline의stage/elastic/credit/C hazard요건을DATA_PIPELINING.md에추가하고모델에K-panel당14cycles를더했다.이변경은설계메타데이터·성능모델변경이며기존RTL source SHA256은그대로다.따라서기존bit-exactRTL기능결과는유지하되새물리pipeline·DMA통합이검증됐다고주장하지않는다.
