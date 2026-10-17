# 웹 검색과 AI 샌드박스

## 웹 검색

초기화 시 `.env`의 `COMPOSE_PROFILES=search`를 기본으로 설정합니다.
브라우저에서는 `http://localhost:8888`로 접속합니다.

n8n의 HTTP Request 노드에서는 다음 값을 사용합니다.

| 입력 | 값 |
| --- | --- |
| Method | GET |
| URL | `http://searxng:8080/search` |
| Query parameter `q` | 검색할 문장 |
| Query parameter `format` | `json` |

결과는 `results` 배열에 들어 있습니다. 각 항목의 `title`, `url`, `content`를 다음 노드로 넘깁니다.
n8n 컨테이너에서 `localhost:8888`은 검색 서비스 주소가 아닙니다. 내부 DNS 이름 `searxng:8080`을 사용합니다.
JSON 출력은 제공한 `config/searxng/settings.yml`에서 활성화되어 있습니다.

검증:

```bash
python3 scripts/check.py
```

검색 엔진별 CAPTCHA·요청 제한·접속 실패가 있을 수 있습니다.
API가 응답하는 상태와 외부 엔진에서 실제 결과를 가져오는 상태는 다르므로 결과 배열까지 확인합니다.

## AI 샌드박스

처음부터 설치할 때:

```bash
python3 scripts/setup.py --sandbox
docker compose up -d --wait --wait-timeout 600
```

이미 `.env`가 있다면 초기화 도구를 재실행하지 않고 아래 두 줄을 수정합니다. 암호화 키는 그대로 둡니다.

```dotenv
COMPOSE_FILE=docker-compose.yml,compose.sandbox.yml
COMPOSE_PROFILES=search
```

기본 템플릿의 `COMPOSE_PATH_SEPARATOR=,`를 유지합니다. 이 값으로 Windows와 Unix의 경로 구분자 차이를 피합니다.
추가 후 `docker compose config --quiet`와 `docker compose up -d --wait --wait-timeout 600`을 실행합니다.

샌드박스 API는 n8n에서 `http://sandbox-api:8080`으로 접근합니다.
공유 API 키는 같은 `.env` 항목에서 전달하고 runner와 API 사이에는 mTLS를 사용합니다.
웹 검색은 `N8N_INSTANCE_AI_SEARXNG_URL=http://searxng:8080`으로 AI 어시스턴트에 연결됩니다.
로컬 파일·쉘 gateway는 기본 비활성화하고, 코드 실행용 샌드박스만 연결합니다.

샌드박스 실행기가 기동되면 내부 Docker가 작업 이미지를 추가 다운로드할 수 있습니다.
첫 AI 작업은 이 다운로드 때문에 느릴 수 있습니다. 기본 이미지는 `stable` 채널을 사용합니다.
샌드박스 전체 릴리스를 지정하려면 `.env`에 `SANDBOX_VERSION`을 추가합니다.
기존 작업 이미지가 내부에 캐시되어 있으면 바깥 Compose 업데이트만으로 갱신되지 않으므로 [업데이트 절차](OPERATIONS.md#업데이트)의 내부 pull도 실행합니다.

AI 어시스턴트 동작에는 별도로 모델 이름·OpenAI 호환 endpoint·API 키가 필요합니다.
서비스의 `healthy` 상태는 실제 모델 호출 성공을 증명하지 않습니다.

**이 번들 샌드박스는 개발·테스트용입니다.** `sandbox-runner-1`이 privileged로 동작하므로 신뢰할 수 없는 여러 사용자의 운영 서버에 그대로 공개하는 용도는 피합니다.
[공식 n8n 배포 문서](https://docs.n8n.io/hosting/installation/server-setups/digital-ocean/)는 운영용 sandbox 제공 방식으로 Daytona도 안내합니다.
기본 n8n과 Code runner에는 privileged 권한이나 호스트 Docker socket을 주지 않습니다.

## Redis 메모리·캐시

`.env`의 프로필을 수정하고 다시 시작합니다.

```dotenv
COMPOSE_PROFILES=search,memory
```

n8n Redis credential에는 Host `redis`, Port `6379`, Password는 `.env`의 `REDIS_PASSWORD`를 입력합니다.
현재 구성의 Redis는 워크플로 메모리·캐시용입니다. n8n 실행 큐 모드에는 별도 worker 구성이 필요합니다.

## Qdrant 벡터 저장

```dotenv
COMPOSE_PROFILES=search,vector
```

n8n에서는 URL `http://qdrant:6333`, API key는 `.env`의 `QDRANT_API_KEY`를 사용합니다.
관리 화면은 `http://localhost:6333/dashboard`이며 같은 API 키가 필요합니다.
gRPC 6334는 호스트에 공개하지 않습니다.

## RedisInsight 관리 도구

```dotenv
COMPOSE_PROFILES=search,tools
```

`http://localhost:5540`에서 Redis 서버 `redis:6379`와 비밀번호를 등록합니다.
이 프로필은 Redis도 같이 시작합니다. 관리 화면은 loopback에만 공개합니다.

## 프로필 변경 후 적용

```bash
docker compose up -d --wait --wait-timeout 600
docker compose ps -a
```

프로필에서 이름을 뺀 것만으로 이미 실행 중인 서비스가 자동 중지되지는 않습니다.
예를 들어 Redis와 관리 도구를 중지하려면 `docker compose --profile tools stop redis redisinsight`를 명시적으로 실행합니다.
기존 volume은 유지되므로 다시 활성화하면 저장된 데이터를 사용합니다.
