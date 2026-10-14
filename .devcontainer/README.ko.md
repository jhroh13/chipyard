# Chipyard를 GitHub Codespaces에서 실행하기

1. 저장소에서 **Code → Codespaces → Create codespace on main**을 선택합니다.
2. 컨테이너 준비와 자동 설치가 끝날 때까지 기다립니다. 처음에는 Conda 패키지,
   서브모듈 다운로드 및 Scala 컴파일 때문에 시간이 걸립니다.
3. 설치 로그의 `Chipyard RTL development environment is ready.`가 성공 표시입니다.

이 설정은 x86_64 Linux에서 공식 `build-setup.sh --use-lean-conda`를 사용합니다.
RISC-V 컴파일러, Spike, Verilator, Scala/sbt, CIRCT를 준비합니다.
FireSim과 FireMarshal은 기본 설치에 포함되지 않습니다.

4 CPU, 메모리 16 GB, 저장 공간 64 GB 이상을 요청합니다. GitHub 계정에서
해당 사양을 사용할 수 있어야 합니다. Codespaces의 사용 시간과 저장 공간은
계정의 무료 제공량 또는 요금에 포함됩니다.

## RTL 시뮬레이터 빌드

저장소 루트의 터미널에서:

```bash
source env.sh
cd sims/verilator
make -j2 CONFIG=RocketConfig
```

자동 설치는 개발 도구와 Scala 소스를 준비합니다.
위 명령은 실제 RocketConfig RTL 시뮬레이터를 빌드하는 별도 단계입니다.

## 설치 실패 및 다시 시도

먼저 저장소 루트의 `build-setup.log`에서 실패한 단계를 확인합니다.
Conda 환경 설치가 완료된 뒤 다운로드나 컴파일에 실패했다면 다음으로 재시도합니다:

```bash
bash .devcontainer/setup.sh
```

Conda 설치 자체가 중단되었거나 Chipyard 버전을 바꾸었다면 새 Codespace를
생성합니다. 기존 Codespace에 저장하지 않은 작업은 먼저 커밋하거나 내려받습니다.

## 검증 범위

저장소에 추가한 JSON과 셸 스크립트는 정적 검사를 거쳤습니다.
Codespaces 생성, 패키지 설치 및 RTL 빌드는 실제 Codespace에서 실행해야 검증됩니다.
