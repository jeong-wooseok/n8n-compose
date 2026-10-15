# Google JSON으로 계정 연결 준비하기

운영자가 Google Cloud의 웹 애플리케이션 OAuth 앱을 한 번 설정합니다.
그 JSON을 n8n 서버에 등록하면 사용자는 Client ID·Secret을 직접 입력하지 않고 Google 연결 버튼으로 자기 계정에 로그인합니다.
이는 운영자의 앱을 사용하는 자체 관리 OAuth입니다. n8n Cloud가 제공하는 Google OAuth 앱을 셀프호스팅에 가져오는 기능은 아닙니다.

## 1. Google Cloud에서 앱 준비

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 선택하거나 만듭니다.
2. **API 및 서비스 → 라이브러리**에서 사용할 API를 켭니다. Sheets에는 **Google Sheets API와 Google Drive API**가 필요합니다. Gmail·Calendar도 사용할 API를 각각 켭니다.
3. **Google Auth Platform**에서 브랜딩·대상·데이터 액세스를 설정합니다. 테스트 상태라면 사용할 Google 계정을 테스트 사용자로 추가합니다.
4. **클라이언트 → OAuth 클라이언트 만들기 → 웹 애플리케이션**을 선택합니다. 데스크톱 앱이나 서비스 계정 키를 선택하지 않습니다.
5. 승인된 리디렉션 URI를 등록합니다.

| 실행 위치 | 리디렉션 URI 예시 |
| --- | --- |
| 이 PC 기본 설치 | `http://localhost:5678/rest/oauth2-credential/callback` |
| HTTPS 도메인 | `https://n8n.example.com/rest/oauth2-credential/callback` |

주소·프로토콜·포트·경로가 n8n의 OAuth 화면에 표시된 값과 정확히 같아야 합니다.
Google의 UI 이름은 바뀔 수 있으므로 [공식 n8n Google 설정 문서](https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service)를 함께 참고합니다.

## 2. JSON 다운로드·등록

생성한 OAuth 클라이언트에서 JSON을 다운로드합니다. 대략 다음 구조여야 합니다.

```json
{
  "web": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost:5678/rest/oauth2-credential/callback"]
  }
}
```

설치 폴더에서 파일 경로를 지정합니다. 파일 경로에 공백이 있으면 따옴표로 감쌉니다.

```bash
python3 scripts/setup.py --google-oauth "/path/to/downloaded-client.json"
docker compose up -d --force-recreate n8n
```

또는 `.local/google-client.json`에 파일을 둔 후 `python3 scripts/setup.py --google-oauth`를 실행합니다.
파일 내용이나 Client Secret은 터미널에 출력하지 않습니다.

변환 결과는 다음 형식으로 `.local/google-oauth.json`에 저장됩니다.

```json
{
  "googleOAuth2Api": {
    "clientId": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "clientSecret": "YOUR_CLIENT_SECRET"
  }
}
```

이 공통 부모 credential은 Sheets·Drive·Gmail·Calendar 등의 Google OAuth credential에 상속됩니다.
`CREDENTIALS_OVERWRITE_DATA_FILE=/run/secrets/google-oauth.json`으로 n8n에 주입하며 원본 JSON 전체를 컨테이너에 전달하지 않습니다.
비밀 파일을 갱신하면 n8n 컨테이너를 재생성해야 새 파일을 읽습니다.

## 3. 사용자가 연결

1. n8n에서 Credentials를 열고 Google Sheets 또는 Google Drive 자격정보를 만듭니다.
2. 연결 버튼을 누르고 **자신의 Google 계정**으로 로그인합니다.
3. 앱이 요청한 접근 권한을 확인하고 동의합니다.
4. 테스트 워크플로에서 본인이 접근 가능한 시트나 파일을 조회합니다.

Client ID·Secret이 중앙 주입되어도 사용자의 토큰이나 동의가 자동으로 생성되지는 않습니다.
이미 Client ID·Secret을 직접 저장한 기존 credential은 이 버전의 overwrite로 강제 교체되지 않습니다.
새 credential을 만들어 중앙 앱 연결을 확인한 뒤, 워크플로에서 새 credential을 선택합니다.

## 자주 막히는 부분

| 증상 | 확인할 것 |
| --- | --- |
| `redirect_uri_mismatch` | n8n에 표시된 콜백 주소와 GCP에 등록한 주소가 정확히 같은지 |
| `403 access_denied` | 앱 대상·테스트 사용자·조직 정책·요청 scope |
| Client ID 입력 화면이 계속 보임 | 변환 파일 등록, n8n 재생성, 새 credential인지 확인 |
| Sheets에서 파일을 찾지 못함 | Sheets API와 Drive API 둘 다 활성화했는지, 로그인 계정에 파일 권한이 있는지 |
| 며칠 후 재인증 필요 | 외부 앱의 테스트 상태에서는 일부 scope의 refresh token이 7일 후 만료될 수 있음 |
| JSON 형식 오류 | `web` 객체인지 확인. `installed`·서비스 계정 JSON은 사용할 수 없음 |

여러 사용자에게 넓게 배포할 때는 Google의 앱 게시·검증 및 민감 scope 정책을 확인합니다.
앱을 게시했다는 사실만으로 Google의 검증이나 조직의 접근 허용이 완료되는 것은 아닙니다.

## 파일 보관

`.env`, `.local/`, `client_secret*.json`, `google-client*.json`은 Git 추적에서 제외합니다.
파일 이름이 다른 원본 JSON은 저장소 루트에 두지 말고 `.local/` 안에 둡니다.
`.local/`은 호스트에서 소유자만 들어갈 수 있도록 0700으로 만들고, 변환 파일은 컨테이너의 n8n 사용자에게 읽기 권한을 줍니다.
Compose의 파일 기반 secret은 암호화 저장소가 아니므로 서버 백업·사용자 권한도 함께 관리합니다.

근거: [Credential overwrites](https://docs.n8n.io/administer/manage-credentials/credential-overwrites.md),
[2.36.9 덮어쓰기 코드](https://github.com/n8n-io/n8n/blob/n8n@2.36.9/packages/cli/src/credentials-overwrites.ts),
[Google OAuth 공식 가이드](https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service).
