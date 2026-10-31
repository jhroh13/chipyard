# 환경 재현과 GitHub 게시

## 현재 cloud 환경

```bash
cd /workspace/TINY-NPU/tiny-npu
source scripts/env.sh
make model
make sram
make test
make lint
```

원본 Chipyard 는 `/workspace/chipyard`에 보존되어 있습니다. 새 체크아웃은 독립 Git 저장소이며, 기존에 초기화된 서브모듈 48 개를 pinned commit 으로 복사했습니다. Conda/RISC-V 도구는 기존 환경을 재사용합니다. 새 NPU standalone 테스트에는 Chipyard Scala 재빌드가 필요하지 않습니다. 새 clone 의 전체 Rocket SoC 시뮬레이션은 이번에 다시 실행하지 않았습니다.

## 다른 machine

```bash
# GitHub 게시 이후
# git clone https://github.com/jhroh13/TINY-NPU.git
cd TINY-NPU/tiny-npu
conda env create -f toolchain.yaml
conda activate tiny-npu
make model
make sram
make test
```

현재 GitHub 생성은 연결 권한으로 거부됐으므로 위 원격 clone 은 아직 성공을 보장하지 않습니다. 아래 bundle 을 사용하면 원격 생성 전에도 소스를 복원할 수 있습니다.

```bash
git clone --branch main TINY-NPU.bundle TINY-NPU
cd TINY-NPU/tiny-npu
# conda environment 준비 후 위 명령 실행
```

Chipyard 전체 작업이 필요하면 root 의 `.gitmodules`에 고정된 의존성을 초기화하고 Chipyard 공식 setup 을 수행하십시오. TINY NPU standalone 환경의 성공이 모든 FPGA/VLSI/FireSim 도구 설치를 의미하지는 않습니다.

## GitHub 게시

요청된 경로는 `jhroh13/TINY-NPU`, 기본 visibility 는 private 입니다. 현재 GitHub 인증은 계정 조회/기존 repo read 는 가능하지만 `createRepository`에서 `Resource not accessible by integration` 오류가 발생했습니다. 권한 있는 GitHub 연결을 사용하거나 해당 경로에 빈 저장소를 만든 뒤:

```bash
cd /workspace/TINY-NPU
bash tiny-npu/scripts/publish.sh
```

이 스크립트는 non-force push 만 사용합니다. 기존 원격 이력이 다르면 push 가 실패하도록 두며 임의 덮어쓰기를 하지 않습니다. Token 이 필요하면 환경의 보안 설정에서 제공하고 채팅·Git·스크립트에 값을 기록하지 마십시오. `TINY_NPU_PUBLISH_TOKEN`이 설정되어 있으면 해당 명령 실행에만 GH_TOKEN 으로 사용합니다.

## 검증 증거

`tiny-npu/docs/results/`에 기능 결과와 소프트웨어 버전, 테스트 범위가 기록됩니다. 생성된 C++/binary/hex vectors 는 `tiny-npu/build/`의 ignored 출력입니다. `make test`로 다시 생성할 수 있습니다. `make generate`의 profile wrapper 는 compute engine 만 포함하며, AXI/SRAM 사양 값이 이미 구현됐다는 뜻이 아닙니다.
