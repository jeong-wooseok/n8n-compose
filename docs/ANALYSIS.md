# 구성 분석과 정리 계획

## 확인 범위

2026-10-16에 전달받은 `docker-compose.yml`, `Dockerfile.ai`, `env.txt`를 분석했다.
이 폴더에는 Git 저장소, README, 설정 예제, 테스트가 없었다. 실제 운영 서버는 변경하지 않는다.
원본 파일은 정리 후 `.local/original/`에 보관하고 Git 추적에서 제외한다.

## 원본에서 확인한 문제

| 항목 | 영향 | 정리 방침 |
| --- | --- | --- |
| 기본 실행에 11개 서비스 연결 | 부가 서비스 설정 없이는 설치가 어려움 | core 3개와 선택 기능 분리, 요청에 따라 권장 설치에 검색·샌드박스 포함 |
| `.env`, SearXNG 설정, credential overwrite 파일 누락 | 받은 폴더만으로 설치 재현 불가 | 설정 예제·초기화 절차·GCP JSON 자동 변환 제공 |
| `env.txt`에 실제 자격정보 포함 | GitHub 업로드 시 유출 가능 | 원본 로컬 보관, `.env.example`은 빈 비밀값, Git 제외 검증 |
| `N9N_` 오타, 중복 키, 소문자 `n8n_` 변수 | 설정이 적용되지 않거나 판단이 어려움 | 검증한 공식 환경변수만 사용 |
| 이미지 `latest`와 커스텀 빌드 태그 혼용 | 실행 버전 불명확, 공식 이미지 이름에 패치 이미지 생성 | n8n·runners 같은 버전 지정, 기본 커스텀 빌드 제거 |
| 패키지 내부 문자열을 직접 바꾸는 90초→10분 패치 | 특정 패키지 레이아웃에 결합, 업데이트 시 빌드 실패 | 원본만 보관, 배포 경로에서 제외, 제약 문서화 |
| `/home/...` 절대경로, 고정 네트워크·컨테이너 이름 | 다른 장비·여러 설치와 충돌 | 프로젝트별 named volume과 기본 네트워크 사용 |
| 외부 `demo` 네트워크와 `links` | 수동 사전 작업 필요 | Compose 서비스 DNS 사용 |
| PostgreSQL·Redis·관리도구 포트 공개 | 실행만으로 호스트 외부에 내부 서비스 노출 | DB·Redis 포트 미게시, UI는 loopback 기본값 |
| 매 시작 자동 자격정보·워크플로 import | 백업 폴더 없으면 시작 실패, 기존 항목 재수입 | 수동 import 절차로 전환 |
| task runner에 대응하는 n8n external mode 설정 누락 | Code 노드 연결을 보장할 수 없음 | broker 주소·공유 토큰·동일 이미지 버전 설정 |
| Redis가 있으나 queue mode·worker 없음 | 큐 구성으로 오해 가능 | 워크플로용 선택 기능으로 설명 |
| Qdrant REST 포트 6333 누락 | n8n에서 일반 REST 연결 사용이 어려움 | 내부 서비스 주소 6333 안내 |

## 유지할 동작

정리 전에 Compose를 더미 환경변수로 해석하는 회귀 테스트를 먼저 작성한다.
유지할 계약은 n8n→PostgreSQL 연결, n8n 설정·DB 영속 저장, 서비스 간 네트워크,
외부 task runner의 broker 연결, 환경변수로 전달하는 암호화 키다.
운영 데이터 경로·프로젝트 이름 변경은 신규 설치에만 적용하며 기존 데이터 자동 이전은 하지 않는다.

## 작업 순서

1. 더미 설정으로 원본의 핵심 동작을 검사한다. 실제 비밀값은 테스트에 사용하지 않는다.
2. 기본 Compose를 n8n·PostgreSQL·external task runners로 정리한다.
3. Redis·Qdrant·SearXNG·RedisInsight는 프로필로, AI 샌드박스는 별도 명시적 확장 파일로 분리한다.
4. 비밀값 생성, 설정 검사, 기본 기동 확인을 위한 작은 도구와 GitHub Actions를 추가한다.
5. 한국어 README, 선택 기능·HTTPS·백업·복원·이전 가이드를 작성한다.
6. 별도 읽기 전용 검토 후 설정·테스트·민감정보 검사를 통과한 파일만 GitHub에 업로드한다.

## 우회 코드 판단

`Dockerfile.ai`는 대상 패키지 개수와 교체 전 문자열을 확인하므로 오류를 숨기는 패치는 아니다.
다만 배포 버전 내부 구현에 결합된 로컬 우회다. 공식 이미지 기반의 공용 배포 경로에서 제거하고
원본을 보존한다. AI 응답 중단 시간이 길어지는 동작까지 새 배포가 유지한다고 주장하지 않는다.
자동 import의 `sleep 3`은 DB readiness 확인 뒤에도 사용된 고정 지연으로, 수동 import 전환과 함께 제거한다.

## 공식 근거

- [n8n Docker 설치](https://docs.n8n.io/hosting/installation/docker/)
- [n8n external task runners](https://docs.n8n.io/hosting/configuration/task-runners/): 본체와 runner의 이미지 버전 일치.
- [n8n webhook과 reverse proxy](https://docs.n8n.io/hosting/configuration/configuration-examples/webhook-url/): 2.35 이상은 `N8N_WEBHOOK_URL` 사용.
- [Docker Compose 프로필](https://docs.docker.com/compose/how-tos/profiles/)
- [SearXNG 컨테이너 설치](https://docs.searxng.org/admin/installation-docker.html)

## 검증 기록

원본 `docker compose --env-file env.txt config --quiet`는 `.env` 누락으로 실패했다.
원본의 실비밀값을 이용한 실행은 하지 않았다. 새 설치는 새로운 임의 비밀값으로 진행했다.

- 원본 정리 전 핵심 동작 6개 회귀 테스트 통과.
- 정리 후 setup·GCP JSON 변환·오류 시 원본 보존·비밀값 최소 전달·프로필 조합 등 31개 테스트 통과.
- 독립 검토에서 찾은 Linux 공유 폴더 UID 차이에 대한 준비 명령과 쓰기 검사를 추가.
- `docker compose up -d --wait`로 PostgreSQL·n8n·Code runner·검색·sandbox API·sandbox runner 기동 확인.
- 실제 웹 검색 JSON API에서 결과 20개 반환 확인.
- n8n 컨테이너에서 API 키로 sandbox 생성 → `printf` 실행 성공 → 삭제 → 404 확인.
- Code runner launcher의 HTTP health와 n8n의 JavaScript/Python launcher 등록 로그 확인. 실제 Code 노드 워크플로는 별도 검증 대상.
- Google 다운로드 JSON 변환은 합성 데이터로 검사. 실제 Google 로그인·사용자 동의·토큰 교환은 미수행.
- 모델 API 키가 없는 새 설치로 AI 어시스턴트 모델 호출은 미수행.
- 이 PC의 기존 5678 포트 충돌을 피해 로컬 `.env`만 15678로 설정. 저장소 기본값은 5678.
- 기존 운영 DB·외부 서버·DNS·GCP 프로젝트 설정은 변경하지 않음.

샌드박스 설정은 n8n `2.36.9` 공식 소스의 `N8N_SANDBOX_SERVICE_URL`과 `N8N_SANDBOX_SERVICE_API_KEY`로 수정했다.
`N8N_AI_TIMEOUT_MAX`와 `N8N_USER_MANAGEMENT_JWT_SECRET`은 지원되는 공식 변수다.
기본 템플릿에서는 과도한 시간 연장과 별도 JWT secret 지정을 생략하고 n8n 기본 동작을 사용한다.
소문자 `n8n_AUTO_EDIT*`는 공식 지원 근거를 확인하지 못해 제거했다.
초기 배포(2026-10-16)에서는 추가 서비스 이미지를 multi-architecture manifest digest로 고정해 기동을 검증했다.
2026-10-17에는 사용자가 쉽게 갱신하도록 `.env.example`에서 이미지 digest와 중복 기본값을 제거했다.
n8n·Code 실행기는 공통 `N8N_VERSION=latest`, 샌드박스 묶음은 공통 `SANDBOX_VERSION=latest`를 기본으로 사용한다.
업데이트는 사용자가 필요할 때 `docker compose pull`과 `docker compose up -d`로 적용한다.
PostgreSQL은 데이터 경로 호환성을 위해 17 계열을 유지한다. 기존 `.env`와 실행 중인 서비스는 이 변경만으로 바뀌지 않는다.
새 릴리스의 실제 기동 검증은 초기 배포의 기동 기록과 구분하며, 최신 결과는 GitHub Actions에서 확인한다.
