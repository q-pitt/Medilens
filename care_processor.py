from google import genai
from google.genai import types
import streamlit as st
import json
import interaction_checker  # [RAG] 상호작용 검사기 모듈 임포트

def analyze_with_llm(final_json):
    """
    LLM에게 JSON(+ RAG 결과)을 주고, 
    약물별 상세 분석(효능, 주의사항, 복용법, 음식궁합) 및 종합 스케줄링을 요청
    """
    try:
        client = genai.Client(api_key=st.secrets["gemini_api_key"])
        
        # [RAG] 상호작용 규칙 검사 (Local Hybrid RAG)
        detected_warnings = interaction_checker.check_interactions(final_json)
        warning_text = "\n".join(detected_warnings) if detected_warnings else "특이사항 없음"

        # 프롬프트 구성 (Gemini Prompt Strategy: XML Tags + Few-Shot)
        prompt = f"""
        <role>
        당신은 20년 경력의 베테랑 약사입니다. 
        환자에게 약에 대해 쉽고 친절하게("~해요"체 사용) 설명해주는 것이 당신의 임무입니다.
        정확하지 않은 정보는 추측하지 말고, 제공된 데이터와 당신의 의학 지식을 바탕으로 답변하세요.
        </role>

        <context>
        JSON 데이터는 환자의 처방전 정보입니다. 
        각 약물에 대해 식약처 API 결과('api_info')가 포함되어 있을 수 있습니다.

        [Known Interactions (확정된 주의사항 - 반드시 반영할 것)]:
        {warning_text}

        [입력 데이터 JSON]:
        {json.dumps(final_json, ensure_ascii=False)}
        </context>

        <task>
        다음 단계로 분석하세요:
        1. **개별 약물 분석**: 각 약물별로 효능, 주의사항, 복용법, 음식/생활 가이드를 작성하세요.
           - 'api_info'가 있다면 최우선으로 참고하세요.
           - [Known Interactions]에 경고가 있다면 'food_guide'나 'precautions'에 반드시 포함시키고 강조하세요.
           - 말투는 친절하고 전문적으로 작성하세요.
        
        2. **스케줄링 추론**: 약물들의 복용 횟수(하루 3회 등)를 종합하여 가장 이상적인 복용 시간 리스트를 만드세요.
           - 기준: 아침(08:00), 점심(13:00), 저녁(19:00), 취침전(22:00)
           
        3. **키워드**: 이 처방의 목적을 대표하는 키워드 1개를 선정하세요. (예: 감기, 고혈압 관리, 장염)
        </task>

        <output_format>
        반드시 아래 JSON 포맷으로만 응답하세요. 마크다운 코드블록(```json) 없이 순수 JSON 문자열만 주세요.

        {{
            "drug_analysis": [
                {{
                    "name": "약품명",
                    "efficacy": "핵심 효능 (1줄 요약)",
                    "precautions": "주요 주의사항 (부작용 등)",
                    "usage": "복용법 (예: 1일 3회 식후 30분)",
                    "days": "처방 일수 (입력 데이터의 'days' 값을 정수로, 없으면 3)",
                    "food_guide": "음식 궁합 및 생활 가이드 (술, 커피, 특정 음식 등)"
                }}
            ],
            "schedule_time_list": ["08:30", "13:30", "19:30"],
            "archive_keyword": "대표질환명"
        }}
        </output_format>
        """

        # 4. AI 호출
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json" 
            )
        )
        
        # 5. 결과 파싱
        return json.loads(response.text)
        
    except Exception as e:
        return {"error": f"AI 분석 실패: {str(e)}"}

def generate_summary_report(medicines):
    """
    [통합 리포트 생성 함수]
    등록된 모든 약 정보를 바탕으로 
    '처방 약 설명', '복용 스케줄', '안전 주의사항', '복약 팁'을 포함한
    상세한 마크다운 리포트를 생성합니다.
    """
    if not medicines:
        return "⚠️ 등록된 약 정보가 없습니다."

    try:
        client = genai.Client(api_key=st.secrets["gemini_api_key"])
        
        prompt = f"""
        당신은 환자의 건강을 책임지는 친절한 AI 전담 약사입니다.
        제공된 약물 데이터를 바탕으로 세심하고 종합적인 복약 가이드 리포트를 **JSON 형식**으로 작성해주세요.

        [약물 데이터]:
        {json.dumps(medicines, ensure_ascii=False, default=str)}

        [JSON 출력 스키마]:
        {{
            "opening_message": "인사말 및 전체적인 요약 (환자의 회복을 기원하는 따뜻한 메시지 포함)",
            "medicines": [
                {{
                    "name": "약물명 (입력된 이름 그대로)",
                    "efficacy": "효능 (입력된 'efficacy' 그대로 사용)",
                    "usage": "용법 (입력된 'usage' 그대로 사용)",
                    "caution": "주의사항 (입력된 'info' 또는 'precautions' 그대로 사용)",
                    "food_guide": "음식 가이드 (입력된 'food' 또는 'food_guide' 그대로 사용)"
                }}
            ],
            "schedule_proposal": {{
                "title": "⏰ 복용 스케줄 제안",
                "content": "아침/점심/저녁 복용 계획을 상세히 서술 (마크다운 사용 가능)"
            }},
            "safety_warnings": {{
                "title": "⚠️ 안전 주의사항",
                "content": "부작용, 병용 금기 등 안전 관련 필수 정보 (마크다운 사용 가능)"
            }},
            "medication_tips": {{
                "title": "💡 복약 팁",
                "content": "생활 습관, 피해야 할 음식, 올바른 보관법 등 (마크다운 사용 가능)"
            }}
        }}

        [작성 가이드]:
        1. **데이터 기반**: 입력된 약물의 기본 정보를 바탕으로 하되, 약사로서의 전문 지식을 더해 풍부하게 설명하세요.
        2. **일관성**: 약물명(`name`)은 반드시 입력 데이터와 똑같이 작성하세요.
        3. **톤앤매너**: 따뜻하고 신뢰감 있는 "해요체". 질문 유도 멘트 금지.
        """

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json" 
            )
        )
        
        return json.loads(response.text)

    except Exception as e:
        return {"error": f"리포트 생성 실패: {str(e)}"}
