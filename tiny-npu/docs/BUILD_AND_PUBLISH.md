# 환경 재현과 GitHub 브랜치

개발 저장소는 **기존 `jhroh13/chipyard`**, 브랜치는 **`tiny-npu`**이다. 별도 TINY-NPU GitHub 저장소를 만들지 않는다.

## 현재 cloud 환경

```bash
cd /workspace/TINY-NPU/tiny-npu
source scripts/env.sh
make model
make sram
make extended EXT_ARRAYS="1 2"    # 빠른 회귀
make extended                   # 1/2/10배열 전체 통합 테스트
```

`/workspace/TINY-NPU`는 기존 Chipyard 이력을 보존한 독립 로컬 체크아웃이며, origin은 `https://github.com/jhroh13/chipyard.git`, 현재 개발 브랜치는 `tiny-npu`이다. 경로 이름이 별도 GitHub 저장소를 의미하지 않는다.

원본 `/workspace/chipyard`의 `work` 브랜치와 미커밋 변경은 보존했다. 초기화된 서브모듈48개는 개발 체크아웃에 별도 복사했고, Conda/RISC-V 도구는 기존 환경을 재사용한다. Standalone NPU 테스트에 Chipyard Scala 재빌드는 필요하지 않다.

## 다른 machine에서 복원

```bash
git clone --branch tiny-npu https://github.com/jhroh13/chipyard.git TINY-NPU
cd TINY-NPU/tiny-npu
conda env create -f toolchain.yaml
conda activate tiny-npu
make model
make extended EXT_ARRAYS="1 2"
```

오프라인 bundle에는 변경 이력이 포함된다.

```bash
git clone --branch tiny-npu TINY-NPU.bundle TINY-NPU
```

전체 Chipyard/Rocket 작업에는 root `.gitmodules`의 고정 의존성과 공식 toolchain setup이 추가로 필요하다. NPU standalone 테스트 성공이 모든 FireSim/FPGA/VLSI 도구 설치를 뜻하지는 않는다.

## 변경 게시

```bash
cd /workspace/TINY-NPU
bash tiny-npu/scripts/publish.sh
```

스크립트는 저장소와 브랜치를 검사하고 `origin tiny-npu`로 non-force push한다. `main`은 변경하지 않는다. GitHub URL:

- 브랜치: https://github.com/jhroh13/chipyard/tree/tiny-npu
- 통합 HDD: https://github.com/jhroh13/chipyard/blob/tiny-npu/tiny-npu/docs/TINY_NPU_HDD_AND_ROADMAP.md
- R2 결과: https://github.com/jhroh13/chipyard/blob/tiny-npu/tiny-npu/docs/results/R2_SIMULATION.md

기존 `createRepository` 권한 오류는 별도 저장소 생성 시도의 기록이다. 현재 방식은 기존 Chipyard에 브랜치를 push하므로 새 저장소 생성 권한이 필요하지 않다.

## 검증 증거

`tiny-npu/docs/results/`에 실제 RTL 테스트 로그와 비교 수가 기록되어 있다. `build/`는 재생성 가능한 ignored 출력이다. 지속10TOPS는 필수 목표지만 실제 AXI·RoCC·전체 SRAM의 통합 성능 실증은 아직이다.
