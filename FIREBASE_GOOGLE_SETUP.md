# 마음결 구글 로그인 및 상담 내역 보관 (무료로 시작하기)

## Firebase 앱 연결에 실패할 때

ChatGPT 안에서 'Firebase 연결하지 못했습니다'가 표시되어도 **Firebase 서비스를 이용할 수 없는 것은 아닙니다.** Firebase Console 웹사이트에서 직접 프로젝트를 만들 수 있습니다.

1. https://console.firebase.google.com/ → Google 로그인 → **프로젝트 만들기**
2. 별도 결제 업그레이드를 선택하지 말고 무료 **Spark**로 시작. Firebase에서 무료 등급 조건을 확인합니다.
3. 프로젝트 설정 → **앱 추가** → **웹(</>)** → 웹 앱을 등록하고 표시되는 `firebaseConfig`의 네 항목 `apiKey`, `authDomain`, `projectId`, `appId`를 복사합니다.
4. 빌드 → Authentication → 시작하기 → Sign-in method에서 **Google** 로그인 제공업체 사용 설정
5. Authentication → Settings → **Authorized domains**에서 `maumgyeol-ai-chat-2026.onrender.com`을 허용합니다.
6. 빌드 → Firestore Database → 데이터베이스 만들기 → 위치 선택 → **프로덕션/잠금 모드**로 시작 → Rules에 저장소의 `firestore.rules` 전체 내용을 붙여넣고 Publish 합니다.
7. Render https://dashboard.render.com/web/srv-dbhi8a8ae00c73drjdj0/env 에서 환경 변수 추가:
   - `FIREBASE_PROJECT_ID` : firebaseConfig의 projectId
   - `FIREBASE_API_KEY` : firebaseConfig의 apiKey (웹 설정값이며 서버 비밀키 아님)
   - `FIREBASE_APP_ID` : firebaseConfig의 appId
   - `FIREBASE_AUTH_DOMAIN` : firebaseConfig의 authDomain (예: 프로젝트ID.firebaseapp.com)
8. Render에서 저장하고 재배포하면 로그인 게이트가 활성화됩니다. 네 항목을 모두 등록하기 전에는 기존 **초대 코드** 방식이 유지됩니다.

> 오픈 API 키나 서비스 계정 비공개 키를 이 채팅에 보내지 마세요. 서버에는 서비스 계정 JSON·관리자 키를 사용하지 않습니다.

## 기능

- 구글로 회원가입 및 로그인: 처음 인증 시 계정 생성, 같은 기기에서는 Firebase 로그인이 유지됩니다.
- 사용자가 기록 저장과 개인정보 처리에 동의하면, 상담 대화는 Firestore `users/{본인UID}/sessions/{대화ID}` 경로에 저장됩니다.
- 과거 대화를 다시 불러오거나, 한 대화만 삭제하거나, 모든 기록 삭제가 가능합니다.
- 통합 마음 관리의 감정 비율은 사용자 발화의 단순 키워드 출현 수를 100%로 환산한 참고 지표이며 임상 검사가 아닙니다.
- 생각 정리 노트는 별도의 저장 없이 화면에서만 관리합니다. 사용자가 '마음결과 이어서 이야기하기'를 누를 때만 대화로 전송됩니다.

## 개인정보 및 안전 주의

- 상담 내용은 매우 민감할 수 있습니다. 실제 운영 전 **개인정보 처리방침, 개인정보 수집 및 보유 기간, 삭제 요청·계정 탈퇴 절차, 전문 상담·응급 대응의 한계**를 명확히 고지해야 합니다.
- Firestore의 Rules를 시험용 전체 허용으로 놓으면 다른 사용자의 기록이 노출될 수 있습니다. 반드시 이 저장소의 `firestore.rules`를 적용하세요.
- Firebase 프로젝트 관리자는 권한에 따라 원본 데이터를 볼 수 있습니다. 종단간 암호화가 된 시스템은 아닙니다.
- 외부 언어모델과 브라우저 음성 인식 제공업체는 입력을 처리할 수 있습니다. 필요한 안내와 동의는 삭제하지 마세요.
- Firebase 무료 등급은 사용량 한도가 있습니다. 로그인·저장 테스트 시 실제 콘솔에서 읽기/쓰기 사용량을 점검하세요.
- 구글 팝업 로그인은 Safari 팝업 차단·도메인 설정에 따라 실패할 수 있습니다. Firebase 공식 문서의 브라우저와 redirect 제한을 확인하세요.

## 개발 검증

설정 전: Render 사이트는 기존 초대 코드로 접근하며 상담 기록의 Firebase 저장 기능은 **비활성**입니다.
설정 후: 다른 구글 계정으로 각각 로그인하여 서로의 기록이 보이지 않는지 확인하고, 앱을 다시 열었을 때 이전 대화를 복구할 수 있는지 확인하세요.
