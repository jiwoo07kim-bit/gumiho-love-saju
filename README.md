# 🦊 구미호 연애운 사주

기존 `index.html.txt` 디자인을 바탕으로 만든 Flask + 정적 HTML 프로젝트입니다.

## 포함된 기능
- 연애운 / 재회운 / 궁합 선택, 생년월일·시간 입력
- 무료 미리보기 API: **출생연도 기준 간이 상징 해석** (정밀 만세력 아님)
- OpenAI API를 이용한 결제 후 프리미엄 자기성찰 리포트
- 토스페이먼츠 결제 요청 및 **서버 측 승인/금액 확인**
- 주문 SQLite 저장, 결제 완료 주문만 AI 결과 제공, 생성 결과 재조회
- 결제 키가 없으면 결제 버튼 비활성화

## 1. GitHub 업로드
압축을 풀고 `gumiho-love-saju` 폴더 안의 파일들을 GitHub 저장소 **최상위**에 업로드하세요. `app.py`, `requirements.txt`, `static/index.html` 폴더 구조를 유지해야 합니다. `index.html.txt`를 그대로 올리는 대신 `static/index.html`을 사용하세요.

## 2. Render 배포 (가장 쉬운 권장 방법)
1. GitHub 저장소를 Render의 새 **Web Service**에 연결합니다.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. Render 서비스 URL로 접속하면 첫 화면이 열립니다. 별도 GitHub Pages 설정이 필요 없습니다.
5. `/api/health`에 접속해 `{"ok":true}`가 보이는지 확인하세요.

**주의:** Render의 임시 파일 시스템에 SQLite를 저장하면 재배포나 재시작 때 주문 데이터가 사라질 수 있습니다. **실제 결제 운영 전** 영구 디스크(해당 플랜에서 지원할 경우)를 설정하고 `DB_PATH`를 디스크 경로로 지정하거나 관리형 DB로 전환하세요. 동시 요청이 많다면 PostgreSQL 같은 관리형 DB를 권장합니다.

## 3. AI 및 결제 환경 변수
Render > Environment에 아래 항목을 설정합니다. **키는 GitHub 파일에 적지 마세요.**

| 변수 | 용도 |
|---|---|
| `OPENAI_API_KEY` | AI 프리미엄 해석 |
| `OPENAI_MODEL` | 기본 `gpt-4.1-mini` (계정에서 사용 가능한 모델로 변경 가능) |
| `TOSS_CLIENT_KEY` | 토스페이먼츠 클라이언트 키 |
| `TOSS_SECRET_KEY` | 토스페이먼츠 시크릿 키 |
| `PREMIUM_PRICE` | 결제 금액 (기본 예시 4900원, 운영자가 결정) |
| `DB_PATH` | 주문 DB 저장 경로 |
| `ALLOWED_ORIGINS` | GitHub Pages 분리 호스팅 시 허용 출처 |

토스페이먼츠 **테스트 키**로 먼저 결제 승인/성공/실패 흐름을 확인하세요. 실제 결제 운영에는 토스 가맹점 심사, 상품/가격/환불 규정, 사업자·연락처 및 개인정보 처리방침 등 필수 고지가 필요합니다. 이 프로젝트는 이를 대신하지 않습니다.

## 4. GitHub Pages를 별도로 쓸 경우
`static/index.html`을 저장소 루트의 `index.html`로 복사하고 GitHub Pages를 켭니다. HTML 스크립트의 `API` 주소를 **실제 Render 서비스 URL**로 바꾸세요. Render의 `ALLOWED_ORIGINS`에 `https://사용자명.github.io`를 입력하세요. 가능하면 Render 단독 배포가 더 간단합니다.

## 5. 로컬 테스트
```bash
pip install -r requirements.txt
python app.py
```
`http://127.0.0.1:5000`에서 미리보기를 확인합니다.

## 운영 전 필수 개선
- 현재 연간(年干) 및 띠 표시는 **양력 출생연도만** 기준으로 한 간이 값입니다. 입춘 이전 출생, 절기, 일주, 월주, 시주 및 신강·오행은 산출하지 않습니다. 정밀 사주를 제공하려면 검증된 만세력 엔진을 추가해야 합니다.
- 결제 완료 뒤 사용자가 페이지를 닫았을 때 복구할 수 있는 **인증된 주문 조회**, 관리자 고객지원 및 환불 처리 절차를 추가하세요. 현재 주문번호만으로 결과를 조회하므로 공개 상용 운영 전 계정 인증 또는 안전한 1회용 접근 토큰 설계가 필요합니다.
- 서버에서 개인정보 보존 기간, 접근 통제, 삭제 정책, 비정상 요청 제한 및 CSRF/남용 방지 등을 보강하세요.
- AI 생성 요청은 외부 API 비용이 발생하며, 결과 생성 실패 시 재시도와 고객지원 절차가 필요합니다.
