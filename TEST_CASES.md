### **테스트 케이스 문서**

**1. Backend API 테스트 케이스**

| **Test Case ID** | **Feature/Component** | **Test Scenario** | **Preconditions** | **Test Steps** | **Expected Result** | **Test Type** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BE-AUTH-001** | **인증 (Authentication)** | **소셜 로그인 성공 (신규 유저)** | - 소셜 로그인 제공자(e.g., Google)로부터 유효한 인증 코드를 발급받음<br>- 해당 유저가 DB에 존재하지 않음 | 1. `POST /api/v1/auth/social-login` 요청<br>2. Request Body: `{"provider": "google", "code": "VALID_CODE", ...}` | 1. HTTP 200 OK<br>2. 응답으로 `access_token`과 사용자 정보 수신<br>3. DB `user` 테이블에 신규 유저 레코드 생성 확인 | Integration |
| **BE-AUTH-002** | **인증 (Authentication)** | **소셜 로그인 성공 (기존 유저)** | - `BE-AUTH-001`을 통해 가입한 유저 존재 | 1. `POST /api/v1/auth/social-login` 요청 (동일한 소셜 정보) | 1. HTTP 200 OK<br>2. 응답으로 `access_token` 수신<br>3. DB에 신규 유저가 생성되지 않음 확인 | Integration |
| **BE-AUTH-003** | **인증 (Authentication)** | **내 정보 조회 (`/me`)** | - `BE-AUTH-001` 또는 `002`를 통해 로그인하여 유효한 `access_token` 보유 | 1. `GET /api/v1/auth/me` 요청<br>2. `Authorization` 헤더에 `Bearer VALID_TOKEN` 설정 | 1. HTTP 200 OK<br>2. 응답으로 현재 로그인된 유저의 상세 정보(팀 정보 포함) 수신 | Integration |
| **BE-INFL-001** | **AI 인플루언서** | **인플루언서 생성 성공** | - 유효한 `access_token` 보유 | 1. `POST /api/v1/influencers` 요청<br>2. Request Body: `{"influencer_name": "테스트봇", "personality": "활발함", ...}` | 1. HTTP 200 OK<br>2. 응답으로 생성된 인플루언서 정보 수신<br>3. 백그라운드에서 QA 생성 작업이 트리거됨 (로그 확인) | Integration |
| **BE-INFL-002** | **AI 인플루언서** | **인플루언서 목록 조회** | - `BE-INFL-001`을 통해 1개 이상의 인플루언서 생성 | 1. `GET /api/v1/influencers` 요청 | 1. HTTP 200 OK<br>2. 응답으로 해당 유저가 소유한 인플루언서 목록 (배열) 수신 | Integration |
| **BE-INFL-003** | **AI 인플루언서** | **특정 인플루언서 상세 조회** | - `BE-INFL-001`을 통해 생성된 인플루언서의 `influencer_id` 확인 | 1. `GET /api/v1/influencers/{influencer_id}` 요청 | 1. HTTP 200 OK<br>2. 응답으로 해당 인플루언서의 상세 정보(스타일, MBTI 등) 수신 | Integration |
| **BE-INFL-004** | **AI 인플루언서** | **인플루언서 정보 수정** | - `BE-INFL-001`을 통해 생성된 인플루언서의 `influencer_id` 확인 | 1. `PUT /api/v1/influencers/{influencer_id}` 요청<br>2. Request Body: `{"influencer_name": "수정된 테스트봇"}` | 1. HTTP 200 OK<br>2. 응답으로 수정된 인플루언서 정보 수신<br>3. DB에서 해당 레코드의 `influencer_name`이 변경되었는지 확인 | Integration |
| **BE-INFL-005** | **AI 인플루언서** | **인플루언서 삭제** | - `BE-INFL-001`을 통해 생성된 인플루언서의 `influencer_id` 확인 | 1. `DELETE /api/v1/influencers/{influencer_id}` 요청 | 1. HTTP 200 OK 또는 204 No Content<br>2. DB에서 해당 레코드가 삭제되었는지 확인 | Integration |
| **BE-INFL-006** | **AI 인플루언서** | **말투 생성 API 호출** | - 유효한 `access_token` 보유 | 1. `POST /api/v1/influencers/generate-tones` 요청<br>2. Request Body: `{"personality": "매우 냉소적이고 비판적임"}` | 1. HTTP 200 OK<br>2. 응답으로 생성된 3가지 말투 예시(`conversation_examples`) 수신 | Integration |
| **BE-INFL-007** | **AI 인플루언서** | **QA 생성 상태 조회** | - `BE-INFL-001`을 통해 인플루언서 생성 후, 백그라운드 작업이 시작된 상태 | 1. `GET /api/v1/influencers/{influencer_id}/qa/status` 요청 | 1. HTTP 200 OK<br>2. 응답으로 QA 생성 작업의 현재 상태(`status`, 진행률 등) 수신 | Integration |

**2. VLLM 서버 연동 테스트 케이스**

| **Test Case ID** | **Feature/Component** | **Test Scenario** | **Preconditions** | **Test Steps** | **Expected Result** | **Test Type** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **VLLM-INT-001** | **VLLM 연동** | **VLLM 서버 상태 확인** | - VLLM 서버가 정상적으로 실행 중 | 1. `vllm_client.health_check()` 함수 호출 | 1. `True`를 반환 | Unit/Integration |
| **VLLM-INT-002** | **VLLM 연동** | **LoRA 어댑터 로드** | - VLLM 서버 실행 중<br>- HuggingFace에 유효한 LoRA 모델 존재 | 1. `vllm_client.load_adapter()` 함수 호출<br>2. 파라미터: `model_id`, `hf_repo_name`, `hf_token` | 1. 성공적으로 어댑터가 로드되었다는 응답 수신<br>2. `vllm_client.list_adapters()` 호출 시 로드된 어댑터 목록에 포함 확인 | Integration |
| **VLLM-INT-003** | **VLLM 연동** | **텍스트 응답 생성** | - `VLLM-INT-002`를 통해 어댑터가 로드된 상태 | 1. `vllm_client.generate_response()` 함수 호출<br>2. 파라미터: `user_message`, `system_message`, `model_id` | 1. 생성된 텍스트 응답(`response`)을 포함한 JSON 객체 수신 | Integration |
| **VLLM-INT-004** | **VLLM 연동** | **파인튜닝 시작** | - VLLM 서버 실행 중<br>- 파인튜닝에 필요한 QA 데이터 준비 | 1. `vllm_client.start_finetuning()` 함수 호출<br>2. 파라미터: `influencer_id`, `qa_data`, `hf_repo_id` 등 | 1. 파인튜닝 작업이 시작되었음을 알리는 응답(`task_id` 포함) 수신 | Integration |
| **VLLM-INT-005** | **VLLM 연동** | **파인튜닝 상태 조회** | - `VLLM-INT-004`를 통해 파인튜닝 작업이 시작된 상태 | 1. `vllm_client.get_finetuning_status()` 함수 호출<br>2. 파라미터: `task_id` | 1. 해당 작업의 현재 상태(`status`, 진행률 등)를 포함한 JSON 객체 수신 | Integration |
| **VLLM-INT-006** | **VLLM 연동 (WebSocket)** | **WebSocket 연결 및 채팅** | - VLLM 서버 실행 중이며 WebSocket 엔드포인트 활성화 | 1. `VLLMWebSocketClient` 인스턴스 생성 및 `connect()` 호출<br>2. `send_message()`로 메시지 전송<br>3. `receive_response()`로 응답 수신 | 1. WebSocket 연결 성공<br>2. 전송한 메시지에 대한 스트리밍 응답을 성공적으로 수신 | Integration |

---

**3. Frontend & VLLM 테스트 케이스 (템플릿)**

접근 권한 문제로 직접 분석은 어려웠지만, 일반적인 구조를 가정하여 다음과 같은 테스트 케이스 템플릿을 제안합니다. 실제 프로젝트 구조에 맞게 수정하여 사용하시면 됩니다.

**Frontend 테스트 케이스 템플릿**

| **Test Case ID** | **Feature/Component** | **Test Scenario** | **Preconditions** | **Test Steps** | **Expected Result** | **Test Type** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FE-LOGIN-001** | **로그인 페이지** | **로그인 성공 및 리디렉션** | - 백엔드 서버 정상 동작 | 1. 로그인 페이지 접속<br>2. 소셜 로그인(Google) 버튼 클릭<br>3. 소셜 로그인 팝업에서 인증 완료 | 1. 메인 페이지(대시보드)로 이동<br>2. 유저 닉네임 등 개인화 정보가 화면에 표시됨 | E2E |
| **FE-INFL-C-001** | **인플루언서 생성** | **생성 폼 유효성 검사 (이름 누락)** | - 로그인된 상태 | 1. 인플루언서 생성 페이지로 이동<br>2. 이름 필드를 비워두고 '생성' 버튼 클릭 | 1. "이름을 입력해주세요"와 같은 오류 메시지 표시<br>2. API 요청이 발생하지 않음 | Unit/Component |
| **FE-INFL-C-002** | **인플루언서 생성** | **인플루언서 생성 성공** | - 로그인된 상태 | 1. 인플루언서 생성 페이지로 이동<br>2. 모든 필수 필드(이름, 성격, 말투 등) 입력<br>3. '생성' 버튼 클릭 | 1. "생성되었습니다" 토스트 메시지 표시<br>2. 인플루언서 목록 페이지로 이동<br>3. 방금 생성한 인플루언서가 목록에 표시됨 | E2E |
| **FE-CHAT-001** | **채팅 페이지** | **메시지 전송 및 응답 수신** | - 인플루언서가 생성 및 학습 완료된 상태 | 1. 채팅 페이지로 이동하여 특정 인플루언서 선택<br>2. 메시지 입력창에 "안녕?" 입력 후 전송 | 1. 내가 보낸 메시지가 채팅창에 표시됨<br>2. 잠시 후, 인플루언서의 답변이 채팅창에 표시됨 | E2E |

**VLLM 서버 자체 테스트 케이스 템플릿**

| **Test Case ID** | **Feature/Component** | **Test Scenario** | **Preconditions** | **Test Steps** | **Expected Result** | **Test Type** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **VLLM-API-001** | **`/generate` 엔드포인트** | **기본 모델 응답 생성** | - 기본 언어 모델이 로드된 상태 | 1. `POST /generate` 요청<br>2. Request Body: `{"user_message": "오늘 날씨 어때?"}` | 1. HTTP 200 OK<br>2. 응답으로 적절한 답변을 포함한 JSON 수신 | Functional |
| **VLLM-API-002** | **`/load_adapter` 엔드포인트** | **유효하지 않은 repo로 어댑터 로드 시도** | - | 1. `POST /load_adapter` 요청<br>2. Request Body: `{"hf_repo_name": "invalid/repo"}` | 1. HTTP 4xx 또는 5xx 에러<br>2. "어댑터 로드 실패" 관련 에러 메시지 수신 | Negative |
| **VLLM-FT-001** | **파인튜닝 로직** | **적은 데이터셋으로 파인튜닝** | - | 1. 10개 미만의 QA 데이터로 파인튜닝 시작 | 1. 파인튜닝 작업이 정상적으로 완료됨<br>2. 파인튜닝된 모델이 과적합(overfitting) 경향을 보이는지 확인 | Performance |
