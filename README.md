# 💊 Medilens Care (메디렌즈 케어)

> **AI 기반 처방전 분석 및 복약 스케줄러**  
> 처방전을 찍으면 AI 약사가 분석해주고, 달력에 자동으로 등록해줍니다.

## 📂 프로젝트 구조 (필수 파일)

이 파일들이 한 폴더 안에 있어야 정상 작동합니다.

```
📁 Medilens_Care
├── 📄 main.py               # [실행 파일] 메인 앱
├── 📄 ocr.py                # OCR (글자 인식) 모듈
├── 📄 ocr_correction.py     # 오타 보정 모듈
├── 📄 api_search.py         # 식약처 API 검색 모듈
├── 📄 care_processor.py     # AI 분석 (Gemini) 모듈
├── 📄 interaction_checker.py # 약물 상호작용 검사기
├── 📄 drug_db.csv           # 의약품 이름 DB (오타 보정용)
├── 📂 data
│   └── 📄 drug_rules.json   # 약물/음식 상호작용 규칙 데이터
└── 📂 .streamlit
    └── 📄 secrets.toml      # API 키 (Gemini / 공공데이터포털)
```

*(참고: `medilens_db.csv`와 `check_history.csv`는 앱 실행 시 자동으로 생성됩니다.)*

---

## 🚀 설치 및 실행 방법

### 1. 환경 설정
필요한 파이썬 라이브러리를 설치합니다.
```bash
pip install -r requirements.txt
```

### 2. API 키 설정
`secrets_example.toml` 파일을 `.streamlit/secrets.toml`로 복사하고 키값을 채워주세요.
```bash
mkdir .streamlit
cp secrets_example.toml .streamlit/secrets.toml
# 이후 secrets.toml을 열어 API 키 입력
```

### 3. 앱 실행
터미널에서 아래 명령어를 입력하세요.
```bash
streamlit run main.py
```

---

## ✨ 주요 기능

1.  **📸 처방전 AI 분석**
    *   좌측 사이드바에 처방전 이미지를 업로드하세요.
    *   **"🚀 AI 정밀 분석 및 등록"** 버튼을 누르면 OCR과 LLM이 분석을 시작합니다.
    *   *오타 자동 보정*, *식약처 정보 대조*, *음식 궁합 분석*이 한 번에 수행됩니다.

2.  **🗓️ 자동 복약 스케줄링**
    *   분석이 끝나면 달력에 복용해야 할 약이 색깔별로 자동 등록됩니다.
    *   복용 기간과 횟수도 AI가 자동으로 설정합니다.

3.  **✅ 매일 복용 체크**
    *   달력에서 날짜를 클릭하면 우측에 **체크리스트**가 나옵니다.
    *   약을 먹고 체크박스를 누르면 기록이 저장됩니다. ("복용 완료" 표시)

4.  **💡 약 상세 정보**
    *   메인 화면 상단에서 약물 카드를 펼치면 **효능, 용법, 주의사항, 음식 가이드**를 자세히 볼 수 있습니다.

---

## 🗑️ 데이터 초기화
테스트 중 데이터가 꼬이거나 처음부터 다시 시작하고 싶다면:
1.  좌측 사이드바 맨 아래로 스크롤하세요.
2.  **`🗑️ 데이터 전체 초기화`** 버튼을 누르면 모든 기록이 삭제됩니다.
