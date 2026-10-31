> 이전 검토 기록입니다. 현재 P0 지속10TOPS 후보와 구현 상태는 [통합 HDD](TINY_NPU_HDD_AND_ROADMAP.md)를 우선 참고하십시오.

# 작은 모델 추론 검증 계획

상태: 계획. 아직 matmul RTL과 모델 추론은 구현·실행하지 않았다. 기존 Rocket/RoCC accumulator 테스트와 구분한다.

## 첫 모델

MNIST MLP: 784 → 128 → 64 → 10. Bias 제외109,184 weights, FP4 payload53.3125KiB. K=32 padding 및 scale·bias 공간을 별도 계산해도2MiB SRAM에 충분히 수용할 수 있다.

- A = MXFP4 weight, B = MXINT8 activation, C = FP32.
- CPU는 입력 quantization/packing, bias, ReLU, layer 사이 requantization, 최종argmax 담당.
- NPU는 전용DMA → SRAM → matmul → 결과DMA 담당. Host L1/L2는 matmul data path에서 제외.
- DMA buffer는 uncached이며 cacheable alias를 금지. 실행 중 ownership·fence 규약 적용.
- MX 그룹은 K축32개. Activation도 선택한 연산 방향에 맞게 packing한다.
- 첫 단계는 layer별DMA와 CPU후처리. Weight 상주는 다음 단계 최적화로 구현·검증한다.

## 실험

| 단계 | 목적 |
|---|---|
| FP32 소프트웨어 | 기준 정확도 |
| MX 양자화 소프트웨어 | FP4 정확도 저하·scale·rounding 검증 |
| 단일 layer RTL | bit-exact 수치·DMA 검증 |
| 전체 MLP, batch1 | end-to-end latency·정확도 |
| 전체 MLP, batch32 이상 | 배열 활용률·처리량·중첩 |

측정: 정확도/기준 대비 저하, images/s, layer별 및 전체latency, packing시간, DMA bytes/BW, MAC utilization, SRAM conflict·후단stall, 전력 추정. Batch1은 N방향 활용률이 낮으므로10TOPS에 가까운 성능을 요구하지 않는다. Tail padding 비용도 집계한다.

작은 C runtime과 RoCC driver로 시작할 수 있으며 전체 AI compiler는 초기 필수조건이 아니다.
