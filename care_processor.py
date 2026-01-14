from google import genai
from google.genai import types
import streamlit as st
import json
import interaction_checker  # [RAG] 상호작용 검사기 모듈 임포트

def analyze_with_llm(final_json):
    """
    LLM에게 JSON(+ RAG 결과)을 주고, 
    약물별 상세 분석(효능, 주의사항, 복용법, 음식궁합) + [통합 리포트]를 한 번에 요청
    """
    try:
        client = genai.Client(api_key=st.secrets["gemini_api_key"])
        
        # [RAG] 상호작용 규칙 검사 (Local Hybrid RAG)
        detected_warnings = interaction_checker.check_interactions(final_json)
        warning_text = "\n".join(detected_warnings) if detected_warnings else "특이사항 없음"

        # 프롬프트 구성 (Gemini Prompt Strategy)
        prompt = f"""
        <role>
        당신은 환자의 건강 회복을 돕는 '전문 AI 복약 가이드'입니다.
        약사 수준의 전문적인 지식을 갖추고 있지만, 자신을 '약사'라고 직접적으로 지칭하지는 마세요.
        대신 환자가 이해하기 쉬운 따뜻하고 친절한 말투("~해요"체)로 상세하게 설명해주세요.
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
        제공된 데이터를 바탕으로 아래 단계들을 수행하고, 결과를 JSON 포맷으로 반환하세요.
        
        1. **약물별 상세 분석 ('drug_analysis' 배열)**:
           - 각 약물별 'efficacy'(효능), 'caution'(주의사항), 'usage'(복용법), 'food_guide'(음식/생활 가이드) 작성.
           - 단순히 "정보 없음"이라고 하기보다, 약의 성분과 일반적인 특성을 바탕으로 도움이 될 만한 정보를 풍부하게 작성하세요.
           - [Known Interactions]에 경고가 있다면 'caution'나 'food_guide'에 반드시 포함하고 강조하세요.
           - 'days'(처방 일수)는 입력 데이터에서 정수로 추출하세요 (없으면 미표기).
           - **'time_list'**: 해당 약물의 복용 횟수('1일 3회' 등)에 맞춰 **["아침", "점심", "저녁"]** 처럼 리스트로 반환하세요. (중요)

        2. **스케줄링 추론 ('schedule_time_list')**:
           - 전체적인 통합 스케줄을 작성하세요.

        3. **[NEW] 종합 리포트 생성 ('report' 객체)**:
           - "opening_message": 환자의 쾌유를 비는 따뜻하고 감성적인 인사말과 함께, 이번 처방의 전반적인 목적(예: "이번 약은 감기 증상 완화와 염증 치료에 집중되어 있어요")을 요약해주세요.
           - "schedule_proposal": "아침 식사 후 꼭 드세요" 처럼 구체적이고 실천하기 쉬운 스케줄 제안.
           - "safety_warnings": "졸음이 올 수 있으니 운전은 피하세요" 같이 생활 밀착형 안전 주의사항.
           - "medication_tips": 생활 습관, 피해야 할 음식(술, 커피 등), 올바른 보관법 등 실질적 조언.
        </task>
        
        <writing_guidelines>
        1. **풍부한 설명**: 단답형보다는 문장형으로 설명하여 정보의 가치를 높이세요.
        2. **톤앤매너**: 딱딱한 기계적인 말투 지양. 옆에서 챙겨주는 듯한 부드러운 "해요체" 사용.
        3. **정확성**: 약물명(`name`)은 입력된 데이터와 100% 동일하게 유지하세요.
        4. **가독성**: 리포트 내용에는 마크다운(bold, list)을 적절히 사용하여 읽기 편하게 만드세요.
        </writing_guidelines>

        <output_format>
        반드시 아래 JSON 포맷으로, 마크다운 코드블록 없이 순수 JSON 문자열만 응답하세요.

        {{
            "drug_analysis": [
                {{
                    "name": "약물명",
                    "efficacy": "상세 효능 설명",
                    "caution": "상세 주의사항",
                    "usage": "복용법",
                    "days": 3,
                    "food_guide": "음식/생활 가이드",
                    "time_list": ["아침", "점심", "저녁"]
                }}
            ],
            "schedule_time_list": ["아침", "점심", "저녁"],
            "archive_keyword": "대표질환명",
            "report": {{
                "opening_message": "안녕하세요...",
                "schedule_proposal": {{ "title": "⏰ 복용 스케줄 제안", "content": "..." }},
                "safety_warnings": {{ "title": "⚠️ 안전 주의사항", "content": "..." }},
                "medication_tips": {{ "title": "💡 복약 팁", "content": "..." }}
            }}
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

# def generate_summary_report(medicines):
#     """
#     [통합 리포트 생성 함수] (analyze_with_llm에 통합되어 주석 처리됨)
#     등록된 모든 약 정보를 바탕으로 
#     '처방 약 설명', '복용 스케줄', '안전 주의사항', '복약 팁'을 포함한
#     상세한 마크다운 리포트를 생성합니다.
#     """
#     if not medicines:
#         return "⚠️ 등록된 약 정보가 없습니다."
# 
#     try:
#         client = genai.Client(api_key=st.secrets["gemini_api_key"])
#         
#         prompt = f"""
#         당신은 환자의 건강을 책임지는 친절한 AI 전담 약사입니다.
#         제공된 약물 데이터를 바탕으로 세심하고 종합적인 복약 가이드 리포트를 **JSON 형식**으로 작성해주세요.
# 
#         [약물 데이터]:
#         {json.dumps(medicines, ensure_ascii=False, default=str)}
# 
#         [JSON 출력 스키마]:
#         {{
#             "opening_message": "인사말 및 전체적인 요약 (환자의 회복을 기원하는 따뜻한 메시지 포함)",
#             "medicines": [
#                 {{
#                     "name": "약물명 (입력된 이름 그대로)",
#                     "efficacy": "효능 (입력된 'efficacy' 그대로 사용)",
#                     "usage": "용법 (입력된 'usage' 그대로 사용)",
#                     "caution": "주의사항 (입력된 'info' 또는 'precautions' 그대로 사용)",
#                     "food_guide": "음식 가이드 (입력된 'food' 또는 'food_guide' 그대로 사용)"
#                 }}
#             ],
#             "schedule_proposal": {{
#                 "title": "⏰ 복용 스케줄 제안",
#                 "content": "아침/점심/저녁 복용 계획을 상세히 서술 (마크다운 사용 가능)"
#             }},
#             "safety_warnings": {{
#                 "title": "⚠️ 안전 주의사항",
#                 "content": "부작용, 병용 금기 등 안전 관련 필수 정보 (마크다운 사용 가능)"
#             }},
#             "medication_tips": {{
#                 "title": "💡 복약 팁",
#                 "content": "생활 습관, 피해야 할 음식, 올바른 보관법 등 (마크다운 사용 가능)"
#             }}
#         }}
# 
#         [작성 가이드]:
#         1. **데이터 기반**: 입력된 약물의 기본 정보를 바탕으로 하되, 약사로서의 전문 지식을 더해 풍부하게 설명하세요.
#         2. **일관성**: 약물명(`name`)은 반드시 입력 데이터와 똑같이 작성하세요.
#         3. **톤앤매너**: 따뜻하고 신뢰감 있는 "해요체". 질문 유도 멘트 금지.
#         """
# 
#         response = client.models.generate_content(
#             # model="gemini-3-flash-preview",
#             model="gemini-2.0-flash-exp",
#             contents=prompt,
#             config=types.GenerateContentConfig(
#                 response_mime_type="application/json" 
#             )
#         )
#         
#         return json.loads(response.text)
# 
#     except Exception as e:
#         return {"error": f"리포트 생성 실패: {str(e)}"}
