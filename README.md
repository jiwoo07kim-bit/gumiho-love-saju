# 구미호 연애운 사주 — PayApp 연동 작업안

기존 디자인은 `static/index.html`에서 사용하며, Flask 서버는 `app.py`입니다.

## 구성
- 연애운 / 재회운 / 궁합 무료 미리보기
- 프리미엄 가격 기본 **4,990원**
- 결제용 휴대전화번호 입력 → 서버에서 PayApp REST 결제요청 생성 → PayApp의 `payurl`로 이동
- 결제 상태는 오직 PayApp 서버 통보(`/api/payapp/feedback`)로 확인
- 판매자 ID, 연동 KEY/VALUE, 주문 번호, 금액, 결제 상태를 서버에서 검증
- 결제 완료 주문만 토큰을 통한 결과 조회 및 AI 프리미엄 리포트 제공

## 필수 환경 변수 (Render > Environment, GitHub에 비밀키 저장 금지)
| 변수 | 설명 |
| --- | --- |
| `PAYAPP_USERID` | 페이앱 판매자 아이디 |
| `PAYAPP_LINKKEY` | 페이앱 연동 KEY (비밀) |
| `PAYAPP_LINKVAL` | 페이앱 연동 VALUE (비밀) |
| `PAYAPP_REQUESTKEY` | 페이앱 결제 KEY (비밀, 통보 SHA-256 검증에 필요) |
| `PAYAPP_PUBLIC_URL` | 페이앱에서 접근 가능한 HTTPS **Flask 서버** 기본 주소 (예: https://YOUR-SERVICE.onrender.com) |
| `SITE_URL` | 결제 후 돌아갈 HTTPS **실제 프런트엔드 주소**. 별도 도메인이면 그 주소 지정 |
| `OPENAI_API_KEY` | AI 결과 생성에 사용하는 키 (비밀) |
| `PREMIUM_PRICE` | 기본 4990 |
| `DB_PATH` | 영구 저장 경로. 임시 파일시스템에서 실결제 금지 |
| `ALLOWED_ORIGINS` | 별도 사이트에서 API 호출하는 경우 허용할 정확한 Origin |

## 반드시 확인할 사항
1. 현재 사용 중인 `chatgpt.site` 배포와 이 GitHub 저장소가 실제로 연결되어 있는지 **확인되지 않았습니다**. GitHub 파일 변경만으로 해당 도메인이 변경된다고 가정하지 마세요.
2. 프런트엔드와 Flask가 서로 다른 도메인일 경우 `static/index.html`의 `API` 상수를 실제 Flask 주소로 지정하고, Flask의 `ALLOWED_ORIGINS`를 설정하세요. `chatgpt.site`에서 프런트엔드 파일을 수정할 권한이 없으면 이 PR만으로 결제 기능을 켤 수 없습니다.
3. 실거래 전 영구 DB, 주문 복구/고객지원, 결제취소 및 환불 처리, 개인정보 처리방침과 사업자 고지를 갖추세요.
4. PayApp 결제통보의 responsedate와 SHA-256 서명은 필수 검증하며, 서버는 한국시간(KST) 기준 15분 이내를 확인합니다. 실제 계정에서 시간대·통보 동작을 검증하세요.
5. 카드결제 승인 후 결제통보가 늦게 도착할 수 있습니다. 사이트는 임의로 결제 성공을 추정하지 않습니다.
6. 실결제 테스트를 수행하지 않았습니다. 페이앱 계정과 API 비밀키가 없는 상태에서는 결제 버튼이 비활성화됩니다.
7. 토스페이먼츠용 기존 코드와 키는 사용하지 않습니다.

PayApp 문서: https://api.payapp.kr/dev_center/dev_center01.html
