# Windows에서 설치하기

개인 Windows PC에서 **Docker Desktop + PowerShell**로 진행합니다.
첫 실행 명령은 `docker compose up -d`입니다. `up`까지 입력해야 합니다.
처음 한 번 Python 도구로 비밀번호와 암호화 키를 만든 뒤 시작합니다.

## 1. Docker Desktop 준비

[공식 Windows 설치 안내](https://docs.docker.com/desktop/setup/install/windows-install/)에서 내 PC에 맞는 Docker Desktop을 설치합니다.
WSL 2 사용 항목이 보이면 선택하고, 재시작을 요구하면 Windows를 다시 시작합니다.
Docker Desktop을 열고 **Engine running** 상태를 확인합니다. Linux containers를 사용합니다.

PowerShell에서 Docker를 사용하는 데 Ubuntu 설치나 WSL Integration 설정은 필요하지 않습니다.
별도 Linux 배포판 없이 사용할 수 있다는 내용은 [Docker WSL 공식 문서](https://docs.docker.com/desktop/features/wsl/)에서 확인할 수 있습니다.

WSL 설치·업데이트 오류가 나올 때만 관리자 PowerShell에서 준비합니다. 이미 WSL이 있다면 업데이트부터 확인합니다.

```powershell
wsl --install --no-distribution
```

처음 설치한 후 **Windows를 다시 시작**하고 관리자 PowerShell에서 실행합니다.

```powershell
wsl --update
wsl --version
```

설치 옵션과 재시작 안내는 [Microsoft WSL 명령 문서](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)를 참고합니다.

## 2. Python 준비

일반 PowerShell에서 확인합니다. Python 3.10 이상이면 기존 설치를 사용합니다.

```powershell
py -3 --version
```

없다면 [Python 공식 Windows 다운로드](https://www.python.org/downloads/windows/)에서 Python Install Manager를 설치합니다.
PowerShell을 새로 열고 Python을 준비합니다. 아래 3.14는 안정 버전 예시입니다.

```powershell
py install 3.14
py -3 --version
```

`py install`이 파일을 찾을 수 없다는 오류로 실패하면 기존 Python Launcher가 실행된 경우일 수 있습니다.
먼저 `py -3 --version`으로 기존 Python을 확인하고, 필요하면 [공식 Windows Python 안내](https://docs.python.org/3/using/windows.html)를 따릅니다.
프로젝트용 Python 패키지 설치는 필요하지 않습니다.

Docker Desktop이 실행된 상태에서 확인합니다.

```powershell
docker version
docker compose version
```

Docker **Client와 Server**가 모두 표시되고 Compose 버전이 2.24 이상이면 준비되었습니다.

## 3. 설치 파일 받기

1. [공개 저장소](https://github.com/jeong-wooseok/n8n-compose)에서 **Code → Download ZIP**을 누릅니다.
2. 내려받은 ZIP을 우클릭해 **모두 압축 풀기**를 실행합니다.
3. README.md와 scripts가 바로 들어 있는 폴더 이름을 `n8n-compose`로 바꿉니다.
4. 파일 탐색기 주소창에 `%USERPROFILE%`을 입력하고 그 홈 폴더로 `n8n-compose`를 옮깁니다.

ZIP을 열어 둔 상태에서는 실행하지 않습니다. 압축을 완전히 풀어야 합니다.
같은 이름의 폴더가 이미 있다면 기존 설치와 데이터가 있는지 먼저 확인하고 덮어쓰지 않습니다.

## 4. 초기 설정과 시작

일반 PowerShell에서 한 줄씩 실행합니다.

```powershell
cd "$HOME\n8n-compose"
py -3 scripts/setup.py --sandbox
docker compose config --quiet
docker compose up -d
```

초기 설정은 설치마다 새로운 비밀번호와 암호화 키를 만들고 웹 검색과 샌드박스를 함께 활성화합니다.
기존 `.env`가 있다는 안내가 나오면 파일을 지우지 말고 설정 검사부터 진행합니다.
시작 명령은 필요한 이미지를 자동으로 내려받으므로 첫 실행에는 준비 시간이 걸립니다.

```powershell
docker compose ps -a
```

`n8n`, `postgres`, `searxng`, `sandbox-api`의 `healthy`와 실행기들의 실행 상태를 확인합니다.
`sandbox-certs`의 `Exited (0)`은 인증서 준비를 마친 정상 상태입니다.
`starting`이면 잠시 후 상태 확인을 다시 실행합니다. 준비가 끝나면 기능을 검사합니다.

```powershell
py -3 scripts/check.py
```

마지막 성공 안내를 확인합니다. Google JSON을 아직 넣지 않았다면 관련 `PENDING` 안내는 다음 연결 단계에서 해결합니다.

브라우저에서 [n8n 열기](http://localhost:5678)로 접속해 소유자 계정을 만듭니다.
[웹 검색 열기](http://localhost:8888)에서 검색 결과도 확인합니다.
AI 어시스턴트 모델을 사용하려면 [기능 가이드](FEATURES.md)의 모델 설정을 추가합니다.

## 5. Google JSON 등록

[Google 연결 가이드](GOOGLE_OAUTH.md)에서 프로젝트, API, 동의 화면, 테스트 사용자와 **Web application OAuth 클라이언트**를 준비합니다.
리디렉션 URI는 다음과 같습니다. 포트를 바꾼 경우 n8n Credential에 표시된 주소를 기준으로 맞춥니다.

```text
http://localhost:5678/rest/oauth2-credential/callback
```

다운로드한 파일 이름을 `google-client.json`으로 바꾼 뒤 프로젝트 폴더의 PowerShell에서 실행합니다.
파일 탐색기에서 파일 확장명을 표시해 `.json.json`이 되지 않았는지 확인합니다.

```powershell
Copy-Item "$HOME\Downloads\google-client.json" .local/google-client.json
py -3 scripts/setup.py --google-oauth
docker compose up -d --force-recreate n8n
```

다운로드 폴더가 다르면 첫 명령의 원본 경로를 실제 JSON 위치로 바꿉니다. 공백이 있는 경로는 큰따옴표로 감쌉니다.
새 Google Sheets OAuth2 Credential에서 Google 로그인을 하고 내 테스트 시트의 한 행을 읽어 확인합니다.
JSON 등록은 공통 Client ID·Secret을 제공하는 단계이며, 사용자 로그인과 권한 동의도 필요합니다.

## 다음에 다시 사용하기

Docker Desktop을 먼저 실행하고 PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
cd "$HOME\n8n-compose"
docker compose up -d
```

잠시 중지할 때는 다음 명령을 사용합니다.

```powershell
docker compose stop
```

업데이트가 필요할 때는 프로젝트 폴더에서 다음 두 줄을 실행합니다.
기본 이미지 태그는 `latest`이며, 새 이미지를 받은 뒤 실행 중인 컨테이너에 적용합니다.

```powershell
docker compose pull
docker compose up -d
```

샌드박스 내부 작업 이미지도 갱신하려면 [업데이트 안내](OPERATIONS.md#업데이트)의 추가 명령을 실행합니다.

설정은 `notepad .env`로 열어 **기존 항목의 값**을 수정하고 Ctrl+S로 저장합니다. `.env.txt`로 저장하지 않습니다.
`.env`와 `.local`의 JSON은 비공개로 보관합니다.
오류·백업·복구는 [운영 가이드](OPERATIONS.md)를 참고합니다. `docker compose down -v`는 데이터를 삭제하므로 재시도 명령으로 사용하지 않습니다.
