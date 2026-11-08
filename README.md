# Dure

**여러 GPU 노드의 LLM 배포·관리 자동화를 시도한 CLI 프로토타입**

KAIST 몰입캠프 2026년 여름 과정의 3주 차에 약 일주일 동안 개발한 프로토타입입니다.
Python으로 CLI와 Agent를 만들고, FastAPI와 PostgreSQL로 노드·작업·배포 상태를 관리합니다.
Docker, Ray, vLLM을 이용한 모델 실행을 연결하고, 환경 확인과 배포·상태 관리를 자동화하는 것이
목표였습니다.

[설치와 사용법](dure/README.md) · [아키텍처](dure/docs/architecture.md) · [전체 문서](dure/docs/README.md)

## 프로젝트 배경

한 대의 GPU 메모리에 담기 어려운 LLM을 여러 GPU 노드에 나누어 실행하는 방법에서 출발했습니다.
여러 노드를 함께 사용하려면 GPU 용량뿐 아니라 각 노드의 환경, 자원 사용 여부, 모델 준비 상태를
확인해야 합니다. 실행 도중 일부 작업이 실패했을 때 어디서부터 다시 처리할지도 정해야 합니다.

Dure는 이 과정을 CLI, 관리 서버, 노드별 Agent로 연결합니다. 노드의 자원을 조사하고 배포 계획을
만든 뒤, 작업을 전달하고 결과를 수집하는 관리 기능을 구현하는 데 집중했습니다.

캠프에서 진행한 수동 분산 실행과 Dure 개발은 다음과 같이 구분합니다.

- **수동 분산 실행과 API 제공**: 다른 팀원이 Dure를 사용하지 않고 대형 LLM을 여러 GPU에서
  직접 실행했으며, API 키를 발급해 다른 팀에 제공했습니다. Qwen3-235B를 이용한 Weld·VibeCutter의
  연동 결과는 이 모델 API에 대한 사용 기록이며, Dure의 자동 배포 성공 사례가 아닙니다.
- **Dure 개발**: GPU 환경 확인, 모델 배포와 상태 관리 과정을 CLI로 자동화하려는 시도였습니다.
  GPU 사양과 실행 환경의 호환성 문제로 시행착오를 겪었으며, 캠프가 끝날 때도 수동 처리와
  예외 상황이 남아 있었습니다.

## 담당한 작업

백엔드 개발을 맡아 관리 API와 데이터 모델을 구현하고, GPU 자원 예약과 작업 상태를 관리했습니다.

- FastAPI 기반 관리 API와 PostgreSQL의 노드·작업 상태 저장
- 같은 GPU가 중복 예약되지 않도록 트랜잭션 잠금과 데이터베이스 제약조건 적용
- 작업의 만료·재시도 처리와 배포 상태 관리
- API 요청·응답, 오류 처리와 운영 절차 문서화

## 구현에서 집중한 점

| 처리하려는 상황 | 구현한 방식 | 관련 코드 |
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

## 검증 범위

단위 테스트와 CI로 관리 API, 상태 처리 로직, SQLite 기반 마이그레이션과 패키지 빌드를 검증했습니다.
실제 GPU 환경에서 배포부터 추론까지의 자동화 과정을 다양한 장비 구성에서 반복 검증하는 작업은 남아 있습니다.

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
