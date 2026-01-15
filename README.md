# 💊 Medilens (메디렌즈)

> **신뢰할 수 있는 AI 처방전 분석 및 복약 검증 플랫폼**  
> "단순히 읽는 것을 넘어, 분석의 신뢰성을 증명합니다."

---

## 📂 프로젝트 구조 (Project Structure)

```
📁 Medilens
├── 📄 main.py               # [Controller] UI 및 파이프라인 오케스트레이션
├── 📄 ocr.py                # [Vision] Gemini 3 Flash 기반 텍스트 추출
├── 📄 ocr_correction.py     # [Correction] SymSpell + Jamo 하이브리드 보정
├── 📄 api_search.py         # [Search] 식약처 API 연동 (단일 조회)
├── 📄 care_processor.py     # [Reasoning] LLM 종합 분석 및 Risk Level 판정
├── 📄 interaction_checker.py # [Safety] 룰 기반 상호작용/병용금기 탐지 (RAG)
├── 📄 db.py                 # [Persistence] Supabase 클라우드 DB 연동 핸들러
├── 📄 drug_db.csv           # [Ref] 빠른 검색용 로컬 의약품 DB
└── 📂 data
    └── 📄 drug_rules.json   # [Ref] 약물 병용 금기 규칙 데이터
```

---

## 🚀 주요 기능 (Key Features)

### 1. 🛡️ Trustworthy AI Analysis (신뢰성 중심 분석)
- **Quality Score**: AI 분석의 전 과정(OCR→보정→검증)을 수치화하여 사용자에게 신뢰도를 증명합니다.
- **Safety Gate**: 약물 병용 금기 및 상호작용을 사전에 탐지하여 위험 수준(Risk Level)을 알려줍니다.
- **MFDS Verified**: 모든 약물 정보는 **식약처(MFDS) 공공데이터**와 교차 검증된 정본 데이터입니다.

### 2. 📝 종합 복약 리포트 & 면책 조항
- **Safety First**: 리포트 상/하단에 명확한 면책 조항(Disclaimer)을 배치하여 의료 보조 도구임을 명시합니다.
- **Context-Aware**: 단순 복약 정보뿐만 아니라, 환자의 상황에 맞는 따뜻한 어조의 가이드를 제공합니다.

### 3. 📊 시스템 대시보드 (System Dashboard)
- **Dual View**: 환자용 '복약 비서' 모드와 관리자용 '시스템 대시보드' 모드를 제공합니다.
- **Pipeline Analytics**: OCR 성공률, 데이터 정제율, API 매칭률 등 파이프라인 성능을 실시간으로 시각화합니다.

### 4. ☁️ Cloud Persistence
- **Supabase 연동**: 사용자 데이터와 복약 기록은 안전한 클라우드 DB(Supabase)에 암호화되어 저장됩니다.
- **Multi-Device**: 언제 어디서나 접속해도 나의 복약 기록이 동기화됩니다.

---

## 🛠️ 설치 및 실행 (Setup)

### 1. 필수 설정 (Secrets)
`.streamlit/secrets.toml` 파일에 다음 키가 반드시 필요합니다.

```toml
gemini_api_key = "YOUR_GEMINI_KEY"

[public_data_portal]
api_key = "YOUR_MFDS_KEY"

# [NEW] Supabase Configuration
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_KEY"
```

### 2. 실행
```bash
pip install -r requirements.txt
streamlit run main.py
```

---

## 📦 기술 스택 (Tech Stack)

| 분류 | 기술 | 비고 |
| --- | --- | --- |
| **Logic** | Python, Streamlit | Pipeline Controller & UI |
| **AI/Vision** | **Gemini 3 Flash** | Multimodal OCR & Reasoning |
| **Correction** | **SymSpell + Jamo** | 하이브리드 오타 보정 알고리즘 |
| **Database** | **Supabase** | User Data & Report Logs (Cloud) |
| **Data Source** | **MFDS API** | 공공데이터포털 의약품허가정보 |

---

## ⚠️ 라이선스 및 면책 (License & Disclaimer)

본 서비스는 의료 보조 목적으로 개발되었으며, **제공되는 정보는 결코 전문 의료진의 의학적 판단을 대체할 수 없습니다.** 중요한 의료적 결정은 반드시 의사나 약사와 상의하십시오.
