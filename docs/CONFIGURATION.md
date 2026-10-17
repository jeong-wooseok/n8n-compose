# 필요한 설정만 바꾸기

`.env.example`에는 자주 바꾸는 값과 자동 생성할 비밀값만 둡니다.
이미지 이름, 데이터베이스 이름, 내부 네트워크 등 공통 기본값은 Compose 파일에서 관리합니다.
새 설치는 기존처럼 `setup.py --sandbox`로 준비하며 Python 패키지를 따로 설치하지 않습니다.

## 보통 사용하는 항목

| 항목 | 기본값과 쓰임 |
| --- | --- |
| `N8N_VERSION` | `latest`. n8n과 Code 실행기에 같은 태그를 사용 |
| `GENERIC_TIMEZONE` | `Asia/Seoul` |
| `N8N_PORT` | `5678`. 바꾸면 아래 두 URL과 Google Redirect URI도 수정 |
| `N8N_EDITOR_BASE_URL` | `http://localhost:5678/` |
| `N8N_WEBHOOK_URL` | `http://localhost:5678/` |
| `SEARXNG_PORT` | `8888` |
| `N8N_INSTANCE_AI_MODEL`, `N8N_INSTANCE_AI_MODEL_URL`, `N8N_INSTANCE_AI_MODEL_API_KEY` | AI 어시스턴트 모델을 사용할 때만 입력 |

`COMPOSE_*`는 프로젝트 이름, 검색 프로필과 샌드박스 설정 파일 선택에 사용합니다.
`setup.py --sandbox`가 설정 파일 선택을 처리하므로 처음 설치할 때 직접 바꿀 필요는 없습니다.
`POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY` 등 비밀값 9개는 도구가 자동 생성합니다.
업데이트할 때 새로 만들거나 예제의 빈 값으로 덮어쓰지 않습니다.

## 이미지 기본값과 업데이트

| 서비스 | 기본 이미지 | 필요할 때 추가하는 재정의 변수 |
| --- | --- | --- |
| n8n | `docker.n8n.io/n8nio/n8n:latest` | `N8N_VERSION` |
| Code 실행기 | `n8nio/runners:latest` | 같은 `N8N_VERSION` |
| PostgreSQL | `postgres:17-alpine` | `POSTGRES_IMAGE` |
| 웹 검색 | `ghcr.io/searxng/searxng:latest` | `SEARXNG_IMAGE` |
| Redis | `redis:7.4-alpine` | `REDIS_IMAGE` |
| RedisInsight | `redis/redisinsight:latest` | `REDISINSIGHT_IMAGE` |
| Qdrant | `qdrant/qdrant:latest` | `QDRANT_IMAGE` |
| 샌드박스 API | `ghcr.io/n8n-io/n8n-sandbox-service-api:latest` | `SANDBOX_VERSION` 또는 `SANDBOX_API_IMAGE` |
| 샌드박스 실행기 | `ghcr.io/n8n-io/n8n-sandbox-service-runner-dind:latest` | `SANDBOX_VERSION` 또는 `SANDBOX_RUNNER_IMAGE` |
| 샌드박스 작업 이미지 | `ghcr.io/n8n-io/n8n-sandbox-service-sandbox:latest` | `SANDBOX_VERSION` 또는 `SANDBOX_WORKLOAD_IMAGE` |

`latest`는 게시자가 새 이미지로 갱신하는 태그입니다. 필요한 시점에 다음 명령으로 이미지를 받고 적용합니다.

```bash
docker compose pull
docker compose up -d
```

별도 자동 업데이트 프로그램이나 강제 다운로드 정책은 추가하지 않습니다.
본체와 Code 실행기는 같은 `N8N_VERSION`으로 함께 업데이트합니다.
PostgreSQL은 기존 데이터 경로를 유지하기 위해 17 계열로 제한하고 그 안에서 갱신합니다. 메이저 변경은 별도 DB 이전이 필요합니다.

샌드박스의 작업 이미지는 실행기 **내부 Docker**에 저장됩니다.
샌드박스를 사용한다면 바깥 Compose를 갱신한 뒤 내부 이미지도 받습니다. 이 명령은 PowerShell과 macOS 터미널에서 같습니다.

```bash
docker compose exec sandbox-runner-1 sh -c 'docker pull $SANDBOX_RUNNER_DOCKER_SANDBOX_IMAGE'
```

`compose pull`은 이 내부 작업 이미지를 받지 않습니다. 실행기는 같은 이름의 이미지가 이미 있으면 내려받기를 생략하므로 위 단계가 필요합니다.
갱신한 이미지는 이후 새로 만드는 샌드박스에 적용됩니다. 이미 실행 중인 샌드박스는 기존 이미지로 계속 동작합니다.
전체 절차와 백업은 [운영 가이드](OPERATIONS.md#업데이트)를 참고합니다.

## 특정 버전을 유지하고 싶을 때

필요할 때만 `.env`에 정확한 릴리스 태그를 지정합니다. 예를 들어 다음 값은 2026-10-17 공개 레지스트리에서 확인한 릴리스이며 영구적인 최신 버전 표시는 아닙니다.

```dotenv
N8N_VERSION=2.43.7
SANDBOX_VERSION=1.9.0
```

본체와 Code 실행기에는 첫 번째 값, 샌드박스 API·실행기·작업 이미지에는 두 번째 값이 함께 적용됩니다.
최신 태그를 다시 사용하려면 `N8N_VERSION=latest`로 바꾸고 `SANDBOX_VERSION`을 지우거나 `latest`로 바꿉니다.
개별 `*_IMAGE`를 직접 지정했다면 그 값이 그룹의 기본값보다 우선합니다.

운영 환경에서 정확히 같은 이미지를 재현해야 한다면 개별 `*_IMAGE`에 `이미지:태그@sha256:...`를 지정할 수 있습니다.
digest는 해당 이미지의 정확한 파일을 고르는 기능이므로 그 값을 유지한 채 `pull`해도 새 이미지로 바뀌지 않습니다.

## 이전 템플릿으로 이미 설치했다면

GitHub의 `.env.example` 변경은 내 PC의 `.env`를 바꾸지 않습니다.
프로젝트 업데이트 후에도 기존 `.env`가 이미지 digest를 지정하면 이전 이미지가 계속 선택됩니다.

1. [백업 절차](OPERATIONS.md#백업)로 데이터와 설정을 보관합니다.
2. PowerShell은 `notepad .env`, Mac은 `open -e .env`로 엽니다.
3. `N8N_VERSION=latest`로 바꿉니다. `SANDBOX_VERSION`도 지정되어 있다면 지우거나 `latest`로 바꿉니다.
4. 이전 예제에서 복사한 다음 이미지 항목을 삭제하면 새 Compose 기본값을 사용합니다. 직접 선택한 이미지가 있다면 그 값을 유지할지 먼저 판단합니다.

```text
POSTGRES_IMAGE
SEARXNG_IMAGE
REDIS_IMAGE
QDRANT_IMAGE
REDISINSIGHT_IMAGE
SANDBOX_API_IMAGE
SANDBOX_RUNNER_IMAGE
SANDBOX_WORKLOAD_IMAGE
```

비밀번호·`N8N_ENCRYPTION_KEY`·Google JSON·프로젝트 이름은 유지합니다. `.env`를 지우고 초기 설정을 다시 실행하지 않습니다.
저장 후 운영 가이드의 업데이트 명령을 실행합니다. 실제 서비스의 업그레이드는 이 절차를 수행할 때 이루어집니다.

## 드물게 바꾸는 항목

필요할 때 `.env`에 추가하면 됩니다. 기본 예제에 없어도 Compose가 읽습니다.

| 항목 | 기본값 |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER` | 각각 `n8n` |
| `N8N_LISTEN_ADDRESS` | `127.0.0.1` |
| `N8N_HOST`, `N8N_PROTOCOL` | `localhost`, `http` |
| `N8N_PROXY_HOPS`, `N8N_SECURE_COOKIE` | `0`, `false` |
| `QDRANT_PORT`, `REDISINSIGHT_PORT` | `6333`, `5540` |
| `EXECUTIONS_DATA_MAX_AGE` | `168`시간 |

외부 도메인·HTTPS를 쓸 때는 [운영 가이드](OPERATIONS.md#https와-외부-접속)의 관련 항목을 함께 설정합니다.

## 공식 근거

- [n8n Docker 설치와 업데이트](https://docs.n8n.io/hosting/installation/docker/)
- [n8n 외부 task runner의 버전 조건](https://docs.n8n.io/hosting/configuration/task-runners/)
- [Docker의 이미지 태그와 digest](https://docs.docker.com/reference/cli/docker/image/pull/)
- [Compose 기본값과 변수 재정의](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [샌드박스 1.9.0의 내부 이미지 캐시 처리](https://github.com/n8n-io/n8n-sandbox-service/blob/service/v1.9.0/internal/runner/runtime/docker/docker_client.go#L291)
