# Dure

**여러 GPU 노드에서 로컬 LLM의 배포와 실행 상태를 관리하는 CLI 기반 플랫폼**

KAIST 몰입캠프 2026년 여름 과정의 3주 차에 약 일주일 동안 개발한 프로젝트입니다.
Python으로 CLI와 Agent를 만들고, FastAPI와 PostgreSQL로 노드·작업·배포 상태를 관리합니다.
모델 실행 환경은 Docker, Ray, vLLM을 기반으로 구성했습니다.

[설치와 사용법](dure/README.md) · [아키텍처](dure/docs/architecture.md) · [전체 문서](dure/docs/README.md)

## 프로젝트 배경

한 대의 GPU 메모리에 담기 어려운 LLM을 여러 GPU 노드에 나누어 실행하는 방법에서 출발했습니다.
여러 노드를 함께 사용하려면 GPU 용량뿐 아니라 각 노드의 환경, 자원 사용 여부, 모델 준비 상태를
확인해야 합니다. 실행 도중 일부 작업이 실패했을 때 어디서부터 다시 처리할지도 정해야 합니다.

Dure는 이 과정을 CLI, 관리 서버, 노드별 Agent로 연결합니다. 노드의 자원을 조사하고 배포 계획을
만든 뒤, 작업을 전달하고 결과를 수집하는 관리 기능을 구현하는 데 집중했습니다.

## 담당한 작업

백엔드 개발을 맡아 관리 API와 데이터 모델을 구현하고, GPU 자원 예약과 작업 상태를 관리했습니다.

- FastAPI 기반 관리 API와 PostgreSQL의 노드·작업 상태 저장
- 같은 GPU가 중복 예약되지 않도록 트랜잭션 잠금과 데이터베이스 제약조건 적용
- 작업의 만료·재시도 처리와 배포 상태 관리
- API 요청·응답, 오류 처리와 운영 절차 문서화

캠프에서는 로컬 LLM이 필요했던 취약점 분석팀에 API 키를 발급하고 연동을 지원했습니다.

## 구현에서 집중한 점

| 문제 | 구현한 방식 | 관련 코드 |
| --- | --- | --- |
| 여러 요청이 같은 GPU를 예약하는 상황 | PostgreSQL 트랜잭션 잠금으로 자원 예약을 직렬화하고, 활성 예약에 고유 제약조건 적용 | [자원 예약](dure/src/dure/control/resource_reservation.py), [DB 모델](dure/src/dure/control/models.py) |
| 작업 중단과 늦게 도착한 응답 | 작업에 임대 시간과 시도 번호를 두고, 배포 작업의 이전 시도 결과가 현재 상태를 덮어쓰지 않도록 처리 | [작업 관리](dure/src/dure/control/service.py), [배포 상태 처리](dure/src/dure/control/rollout.py) |
| 일부 노드만 배포에 성공한 상황 | 준비·적용·검증 단계를 나누고 노드별 결과를 기록하며, 배포 세대별 재시도와 명시적 롤백 처리 | [배포 관리](dure/src/dure/control/rollout.py), [관련 테스트](dure/tests/test_deployment_rollout.py) |

## 동작 구조

1. **CLI**에서 GPU 자원을 조사하고 배포 계획을 확인합니다. 관리자는 노드를 승인하고 작업을 요청합니다.
2. **관리 서버**는 FastAPI로 요청을 받고 PostgreSQL에 노드, 자원 예약, 작업과 배포 상태를 저장합니다.
3. **Agent**는 노드에서 관리 서버로 접속해 작업을 가져옵니다. Docker 기반 실행 환경에서 작업을 수행하고 상태와 결과를 보고합니다.

단일 GPU 실행은 vLLM을 사용하고, 다중 노드 실행 경로는 Ray와 vLLM을 함께 사용합니다.
현재 구현은 신뢰된 사설망을 전제로 하며, 지원 모델과 런타임 제약은
[지원 매트릭스](dure/docs/support-matrix.md)에 정리했습니다.

## 검증 범위와 남은 과제

자동화된 검증은 단위 테스트, API 흐름, SQLite 기반 상태 처리·마이그레이션, 패키지 빌드를 다룹니다.
테스트 코드와 실행 명령은 [테스트 디렉터리](dure/tests)와 [개발 안내](dure/docs/development.md)에서
확인할 수 있습니다.

현재 소스 버전 `0.4.22`의 실제 GPU 검증 기록은 **`NOT_RUN`**입니다. 해당 버전의 GPU 메모리 측정,
노드 간 통신, 분산 모델 로딩·추론, 관리 서버를 통한 배포 검증 결과는 아직 기록되지 않았습니다.
구체적인 상태는 [버전별 검증 기록](dure/docs/release-evidence/v0.4.22.md)에 남겼습니다.

후속 과제는 실제 GPU 환경에서 배포부터 추론까지의 결과를 남기고, PostgreSQL에서 동시 예약과
작업 처리를 검증하는 것입니다. 실제 장비 검증 절차는 [릴리스 검증 안내](dure/docs/release-validation.md)를
따릅니다.

## 코드와 문서 안내

| 확인할 내용 | 위치 |
| --- | --- |
| 설치, CLI 사용법, 현재 지원 범위 | [Dure 사용 안내](dure/README.md) |
| 관리 API, DB 모델, 작업·배포 관리 | [백엔드 코드](dure/src/dure/control) |
| CLI와 노드 Agent | [CLI](dure/src/dure/cli.py), [Agent](dure/src/dure/agent.py) |
| 관리자와 Agent의 API 요청·응답 및 재시도 규칙 | [API 문서](dure/docs/api-contract.md) |
| 서버·노드 운영, 배포와 장애 대응 | [운영 절차](dure/docs/operations.md) |
| PostgreSQL 백업·복구 절차 | [백업·복구 문서](dure/docs/disaster-recovery.md) |
| 변경 이력과 후속 계획 | [변경 이력](dure/CHANGELOG.md), [로드맵](dure/docs/roadmap.md) |

## 라이선스와 기여

[Apache License 2.0](LICENSE)을 따릅니다.
[기여 안내](CONTRIBUTING.md), [보안 정책](SECURITY.md), [행동강령](CODE_OF_CONDUCT.md),
[지원 정책](SUPPORT.md), [거버넌스](GOVERNANCE.md)를 참고해 주세요.
