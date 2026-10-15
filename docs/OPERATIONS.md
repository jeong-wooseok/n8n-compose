# 설치 이후 운영

## HTTPS와 외부 접속

기본 설치는 `127.0.0.1`에만 바인딩합니다. 원격 Linux 서버에서는 SSH 터널로 첫 설정 화면에 접속할 수 있습니다.

```bash
ssh -L 5678:127.0.0.1:5678 your-user@your-server
```

그 상태에서 이 PC의 `http://localhost:5678`을 엽니다.
원격 브라우저의 `localhost`와 서버의 `localhost`는 서로 다릅니다.

공개 도메인은 인증서를 관리하는 reverse proxy 또는 tunnel 뒤에 둡니다.
예를 들어 공개 주소가 `https://n8n.example.com`이고 프록시가 한 단계라면 `.env`를 수정합니다.

```dotenv
N8N_HOST=n8n.example.com
N8N_PROTOCOL=https
N8N_EDITOR_BASE_URL=https://n8n.example.com/
N8N_WEBHOOK_URL=https://n8n.example.com/
N8N_PROXY_HOPS=1
N8N_SECURE_COOKIE=true
```

프록시는 WebSocket/SSE와 `X-Forwarded-For`, `X-Forwarded-Host`, `X-Forwarded-Proto`를 전달해야 합니다.
`N8N_PROXY_HOPS`는 실제 신뢰하는 프록시 단계를 반영합니다.
n8n 2.35 이상은 `WEBHOOK_URL` 대신 `N8N_WEBHOOK_URL`을 사용합니다.

호스트에서 동작하는 프록시는 `127.0.0.1:5678`에 연결합니다.
다른 장비나 다른 Docker 네트워크의 프록시는 이 loopback 주소에 접근할 수 없습니다.
그 경우 `N8N_LISTEN_ADDRESS`를 서버의 필요한 LAN 인터페이스 IP로 지정하고 방화벽에서 프록시만 허용하거나,
프록시를 같은 Compose 네트워크에 연결해 `http://n8n:5678`로 접근하도록 구성합니다.
이 템플릿은 특정 NAS·외부 네트워크·인증서 도구를 자동 설치하지 않습니다.

```bash
docker compose config --quiet
docker compose up -d --force-recreate n8n
```

Google Cloud OAuth 클라이언트에 `https://n8n.example.com/rest/oauth2-credential/callback`도 등록합니다.
접속 확인 후 실제 Google 연결과 webhook을 하나씩 실행합니다.

## 데이터가 저장되는 곳

| 저장 대상 | 위치 |
| --- | --- |
| 워크플로·자격정보·실행 내역 | `postgres_data` volume |
| n8n 설정·파일·기타 상태 | `n8n_data` volume |
| 암호화 키·비밀번호·AI 모델 키 | 호스트 `.env` |
| Google OAuth Client ID·Secret | `.local/google-oauth.json` |
| 워크플로 공유 파일 | `data/shared/` |
| 검색 캐시 | `searxng_data` volume |
| Redis·Qdrant | 각각 `redis_data`, `qdrant_data` volume |
| 샌드박스 인증서·내부 Docker 데이터 | `sandbox_tls`, `sandbox_docker` volume |

volume의 실제 이름 앞에는 `COMPOSE_PROJECT_NAME`이 붙습니다.
이미 사용 중인 프로젝트 이름을 바꾸면 다른 volume에 연결되어 초기 설치처럼 보일 수 있습니다.
`N8N_ENCRYPTION_KEY`를 잃거나 바꾸면 기존 credential을 복호화할 수 없습니다.

### Linux 공유 폴더 권한

컨테이너의 n8n은 UID 1000으로 실행됩니다. 다른 UID나 root로 설치한 Linux에서는 아래 명령으로
`data/shared/`를 해당 UID가 쓸 수 있게 준비합니다. 이 명령은 공유 폴더만 변경합니다.

```bash
docker compose run --rm --no-deps --user 0:0 --entrypoint sh n8n -c 'chown 1000:1000 /data/shared && chmod 0750 /data/shared'
```

이후 `python3 scripts/check.py`가 실제 파일 생성·삭제까지 검사합니다.
호스트에서 다른 계정으로 이 폴더를 직접 편집해야 하면 관리자가 해당 계정의 접근 권한을 별도로 설정합니다.
워크플로 파일 노드의 접근 허용 경로는 `N8N_RESTRICT_FILE_ACCESS_TO=/data/shared`로 제한합니다.

## 백업

아래는 macOS·Linux·WSL 터미널 기준입니다. 백업 중에는 워크플로 실행이 잠시 멈춥니다.
원격 서버의 백업은 해당 서버에서 실행합니다.

```bash
umask 077
mkdir -p backups
docker compose stop n8n task-runners
docker compose exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > backups/postgres.dump
docker compose run --rm --no-deps --entrypoint tar n8n -czf - -C /home/node .n8n > backups/n8n-data.tar.gz
tar -czf backups/local-config.tar.gz .env .local/google-oauth.json data/shared
docker compose up -d --wait --wait-timeout 600
```

각 명령의 성공과 백업 파일 크기를 확인한 뒤 서버 밖의 안전한 저장소에 복제합니다.
동일한 파일명으로 실행하면 이전 백업이 교체되므로 날짜별 하위 폴더를 사용하는 편이 좋습니다.
`.env`와 Google 파일이 포함된 백업에는 비밀값이 들어 있습니다. GitHub에 올리지 않습니다.
추가로 사용하는 Redis·Qdrant의 데이터는 각 서비스의 snapshot/백업 기능으로 별도 보관합니다.
샌드박스 내부의 임시 작업 컨테이너를 업무 데이터의 영구 저장소로 쓰지 않습니다.

## 복구

복구 대상이 **새 설치 또는 복구용 인스턴스**인지 먼저 확인합니다.
기존 운영 DB에 아래 명령을 실행하면 백업 시점으로 되돌아갑니다.
먼저 안전하게 보관한 `.env`, `.local/google-oauth.json`, 공유 파일을 해당 위치에 복원합니다.
원래 사용한 `N8N_VERSION`, 이미지 digest와 `N8N_ENCRYPTION_KEY`를 유지합니다.

```bash
docker compose stop n8n task-runners
docker compose up -d --wait postgres
docker compose exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backups/postgres.dump
docker compose run --rm --no-deps --entrypoint tar n8n -xzf - -C /home/node < backups/n8n-data.tar.gz
docker compose up -d --wait --wait-timeout 600
python3 scripts/check.py
```

복구 후 Google credential과 대표 워크플로를 실제 실행해 확인합니다.
새 인스턴스를 기존 인스턴스와 동시에 운영하면 예약·webhook이 중복 실행될 수 있으므로 전환 순서를 정합니다.

## 업데이트

1. 위 절차로 DB·n8n volume·설정을 백업합니다.
2. 릴리스 노트와 호환성을 확인한 뒤 `.env`의 `N8N_VERSION`을 변경합니다. 본체와 task runner가 같은 값을 사용합니다.
3. 부가 서비스 업데이트는 각 `*_IMAGE`에 새 태그 또는 확인한 digest를 지정합니다.
4. 아래 명령으로 적용하고 실제 대표 워크플로를 실행합니다.

```bash
docker compose pull
docker compose up -d --wait --wait-timeout 600
python3 scripts/check.py
```

이 템플릿은 부가 이미지를 digest로 고정하므로 `pull`만으로 다른 버전으로 바뀌지 않습니다.
이미지 digest 확인에는 `docker buildx imagetools inspect IMAGE:TAG`를 사용할 수 있습니다.
PostgreSQL 메이저 버전은 데이터 디렉터리를 공유해 단순 변경하지 않습니다. 별도 DB 이전이 필요합니다.
n8n 업데이트 후 DB migration이 실행되었다면 이미지 버전만 낮추는 rollback은 보장되지 않습니다.
필요하면 이전 이미지와 **업데이트 전 DB 백업을 함께** 복원합니다.

## 기존 서버에서 이전

새 구성은 신규 volume을 사용합니다. 기존 서버의 폴더를 자동으로 연결하지 않습니다.
기존 PostgreSQL 17 데이터가 있다면 기존 서버에서 논리 백업 후 위 복구 절차로 옮깁니다.
기존 n8n 설정 volume과 암호화 키도 함께 옮겨야 저장된 credential을 사용할 수 있습니다.
기존 `credentials-overwrite.json`은 GCP 다운로드 JSON과 구조가 다릅니다. 이미 변환된 파일이라면
그 내용을 검토한 뒤 `.local/google-oauth.json`에 배치하고 n8n을 재생성합니다.
OAuth client나 공개 주소를 변경했다면 리디렉션 URI 등록 및 사용자 재연결을 확인합니다.

원본의 자동 import 서비스는 제거했습니다. 워크플로 JSON은 UI에서 필요한 것만 import하거나,
운영 백업을 복원한 뒤 CLI import를 별도로 수행합니다. 서버 시작마다 반복 import하지 않습니다.

## 문제 해결

| 증상 | 확인 방법 |
| --- | --- |
| `.env already exists` | 재초기화 방지 동작. 기존 파일을 편집하고 키를 보존 |
| `port is already allocated` | 다른 서비스 포트 확인. `.env`의 호스트 포트와 public URL·OAuth URI를 함께 수정 |
| sandbox 시작 중 오래 대기 | `docker compose logs --tail 100 sandbox-api sandbox-runner-1` |
| DB unhealthy | `docker compose logs --tail 100 postgres`, 기존 volume과 사용자·비밀번호 일치 확인 |
| Code 노드 실행 대기 | `docker compose logs --tail 100 task-runners`, 버전·토큰 일치 확인 |
| Google 파일 Permission denied | `.local/` 0700 및 변환 파일 0644 유지. 컨테이너는 다른 UID로 읽음 |
| 공유 폴더 Permission denied | 위 Linux 공유 폴더 권한 준비 명령 실행 |
| 검색 결과 없음 | 검색 엔진 네트워크·제한 확인, `config/searxng/settings.yml` 검토 |
| unhealthy 뒤 재시작되지 않음 | Docker healthcheck는 상태 표시. 원인 수정 뒤 수동 재시작하거나 별도 모니터링 구성 |

검사를 공유할 때는 `docker compose config --quiet`를 사용합니다.
`docker compose config` 전체 출력에는 해석된 비밀번호가 들어갈 수 있습니다.
