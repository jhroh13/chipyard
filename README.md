# TINY NPU

개발 위치: [jhroh13/chipyard의 tiny-npu 브랜치](https://github.com/jhroh13/chipyard/tree/tiny-npu).

Chipyard 기반 **MXFP4 × OCP MXINT8** matmul accelerator 연구·개발 환경입니다.

**필수 설계 목표(P0): 지속 10 useful TOPS 이상.** 최신 RevB 계획은 8 Rocket / 10 MiB single-port L0 / 20.48 TOPS peak / 유효 20 GB/s DMA입니다. 내부 LQ16·선택 TF32, TF32 TARGETR를 사용합니다. 경로별 가변 multicycle latency와 II·credit을 구분합니다. 기존 4-core/FP32 R2 RTL 및 8 MiB 모델은 이전 구현으로 보존합니다.

- [L0 boot: 8-hart firmware·접근 보호·다중 사이클 검증](tiny-npu/architecture/v2/L0_BOOT_REPORT.md)
- [최신 FMA pipeline·40-gate 검증](tiny-npu/architecture/v2/FMA_PIPELINE_REPORT.md)
- [Workload waveform·bubble·DRAM·합성 검증](tiny-npu/architecture/v2/WORKLOAD_VERIFICATION.md) · [실행 결과와 판단](tiny-npu/architecture/v2/WORKLOAD_REPORT.md)
- [순서별 Job List](tiny-npu/architecture/v2/JOB_LIST.md) · [Job 1 설정 생성 체계](tiny-npu/architecture/v2/CONFIGURATION_GENERATION.md)
- [최신 RevB HDD와 구조도](tiny-npu/architecture/v2/HDD.md)
- [Single-port subbank·경로 지연·BW 수식](tiny-npu/architecture/v2/SINGLE_PORT_LATENCY_BW.md)
- [파라미터와 지연·용량 성능 sweep](tiny-npu/architecture/v2/PARAMETERS_AND_SWEEPS.md)
- [전체 parameter CSV](tiny-npu/architecture/v2/parameters.csv)

- [Overview·통합 HDD·RTL 및 LLM 실행 계획](tiny-npu/docs/TINY_NPU_HDD_AND_ROADMAP.md)
- [Data Pipelining 설계](tiny-npu/docs/DATA_PIPELINING.md)
- [RTL/시뮬레이션 결과](tiny-npu/docs/results/RTL_SIMULATION.md)
- [파라미터와 P0 모델](tiny-npu/model/p0_model.py)
- [RTL](tiny-npu/rtl) · [Testbench 와 독립 golden model](tiny-npu/sim)
- [기존 Rocket/RoCC 테스트](tests/quad-rocc.md)
- [원본 Chipyard README](tiny-npu/docs/CHIPYARD_README.md)

## 현재 구현 범위

추가한 검증 기반은 passive performance monitor·offline workload 분석기, SRAM stall fixture, AXI traffic-agent model, LQ16 exact FMA 및 scalar feedback test입니다. 실제8-core/새 MAC array 통합과 PDK timing은 남아 있습니다.

K=32 tile compute에 더해 **K=32/64/128/4096의 FP32 K-block 누산**, 실제4단계 FP32 가산 pipeline, C SRAM slice와 row scoreboard를 구현했습니다. DMA burst planner와 byte-credit/ID 예약 전단도 추가했습니다. 실제 AXI DMA·RoCC 연결, 전체8MiB SRAM banking, LLM 추론, STA와 지속10TOPS 실증은 남아 있습니다.

- [R2 stream GEMM 설계·인터페이스](tiny-npu/docs/R2_K_ACCUMULATION.md)
- [브랜치 이관 후 회귀 결과](tiny-npu/docs/results/BRANCH_MIGRATION_REGRESSION.md)
- [R2 검증 결과](tiny-npu/docs/results/R2_SIMULATION.md)

```bash
cd tiny-npu
source scripts/env.sh                 # 현재 cloudtoolchain 재사용
make model
make extended                        # K>32 / FP32 pipeline / DMA frontend
make generate-gemm
make generate
make lint
make sram
make test                            # 1/5/10 arrays, bit-exact
```

`model/p0_model.py --scale 1/2/4`와`tools/generate_rtl.py --scale 1/2/4`로확장할수있습니다.전체 memory/AXI 프로파일이현재 compute-onlyRTL 에연결됐다는뜻은아닙니다.

기반 sourcehistory/license 는원본 Chipyard 그대로보존합니다.새`tiny-npu/`코드는 Apache-2.0 입니다.기존 submodulelicense 는각프로젝트를따릅니다. 개발은 기존 `jhroh13/chipyard`의 `tiny-npu` 브랜치에서 진행하며, 원본 작업과 Git 이력을 보존합니다.
