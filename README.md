# TINY NPU

Chipyard 기반 **MXFP4 × OCP MXINT8** matmul accelerator 연구·개발 환경입니다.

**P0: 지속 10 TOPS**, 기본 후보는 20.48 TOPS peak / 8 MiB local SRAM / 유효 20 GB/s DMA 입니다. 이전 2MiB·10GB/s 구성은 이 P0 를 충족하지 못해 보존용으로 구분했습니다.

- [Overview·통합 HDD·RTL 및 LLM 실행 계획](tiny-npu/docs/TINY_NPU_HDD_AND_ROADMAP.md)
- [RTL/시뮬레이션 결과](tiny-npu/docs/results/RTL_SIMULATION.md)
- [파라미터와 P0 모델](tiny-npu/model/p0_model.py)
- [RTL](tiny-npu/rtl) · [Testbench 와 독립 golden model](tiny-npu/sim)
- [기존 Rocket/RoCC 테스트](tests/quad-rocc.md)
- [원본 Chipyard README](tiny-npu/docs/CHIPYARD_README.md)

## 현재 구현 범위

K=32,32×32 MXFP4×MXINT8 tile compute, E8M0 scale, FP32 output,RNE/subnormal/Inf/NaN,dual result buffer,stream backpressure 를구현했습니다. DMA/RoCC matmul 연결,전체 bankedSRAM,K>32FP32 누산,LLM 추론,1GHzSTA 및지속 10TOPS 실증은아직아닙니다.

```bash
cd tiny-npu
source scripts/env.sh                 # 현재 cloudtoolchain 재사용
make model
make generate
make lint
make sram
make test                            # 1/5/10 arrays, bit-exact
```

`model/p0_model.py --scale 1/2/4`와`tools/generate_rtl.py --scale 1/2/4`로확장할수있습니다.전체 memory/AXI 프로파일이현재 compute-onlyRTL 에연결됐다는뜻은아닙니다.

기반 sourcehistory/license 는원본 Chipyard 그대로보존합니다.새`tiny-npu/`코드는 Apache-2.0 입니다.기존 submodulelicense 는각프로젝트를따릅니다. GitHub 원격생성은현재연결의권한오류로미완료이며로컬작업·bundle 을보존합니다.
