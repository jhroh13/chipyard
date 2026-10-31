# tiny-npu 브랜치 이관 후 Matmul 회귀 결과

- 저장소: https://github.com/jhroh13/chipyard
- 브랜치: `tiny-npu`
- 실제 테스트 커밋: `92fc2df05e5ae3632fe1d05ff074c9ad0e01d35c`
- 로컬 개발 경로: `/workspace/TINY-NPU`
- 기존 `/workspace/chipyard`의 `work` 브랜치와 미커밋 변경은 그대로 보존했다.
- RTL 소스 변경 없이 기존 빌드 캐시를 재사용하고 벡터를 재생성하여 시뮬레이터를 다시 실행했다. 이전 결과를 그대로 복사한 회귀 판정이 아니다.

| 테스트 | 구성 | 비교 수 | 결과 |
|---|---|---:|---|
| R1 K=32 matmul | 1/5/10 arrays, 각12cases | 196,608 FP32 | PASS |
| R2 K=32/64/128/4096 GEMM | 1/2/10 arrays, 각8jobs | 106,496 FP32 | PASS |
| 4-stage FP32 add | RNE·특수값·stall | 20,000 pairs | PASS |
| C SRAM row hazard | 동일주소 누산·의존성 stall | 3 outputs | PASS |
| SRAM template | 256-bit 1R1W·byte mask | 128 comparisons | PASS |
| DMA 전단 | 4KiB split·byte credit·ID recycle·stall | directed checks | PASS |

총303,104개matmul FP32결과가독립소프트웨어기준값과bit-exact일치했다. K블록마다scale적용/FP32rounding을수행하고K순서로누산한다. ID/row/last와출력stall안정성도검사했다.

## 실행 명령

```bash
cd /workspace/TINY-NPU/tiny-npu
source scripts/env.sh
make test
make extended EXT_ARRAYS="1 2 10"
make sram
```

실행결과JSON·RTL SHA256은`branch_regression.json`,raw출력은`branch-*-regression.txt`에보존한다.

## 성능 범위

이는실제Verilator기능회귀결과다. 아직전체8MiBSRAM·실제AXI DMA·RoCC경로가연결되지않았으므로**지속10TOPS달성은미검증**이다. 이벤트모델의13.4775TOPS예측을이테스트의실측TOPS로보고하지않는다. 다음작업은전체메모리경로를통합하고RoCC수락→최종DMAwrite-response완료구간을측정하는것이다.
