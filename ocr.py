# ocr.py
import streamlit as st
from google import genai
from google.genai import types
import PIL.Image
import json
import re

def run_ocr(image_file):
    """
    이미지 파일을 받아 Gemini 3 Flash를 이용해 1차 OCR 결과를 반환하는 함수
    """
    # 1. API 키 설정 (secrets.toml 사용)
    try:
        api_key = st.secrets["gemini_api_key"]
    except:
        st.error("❌ secrets.toml에 'gemini_api_key'가 설정되지 않았습니다.")
        return []

    client = genai.Client(api_key=api_key)
    MODEL_ID = "gemini-3-flash-preview" 

    # 2. 이미지 로드
    img = PIL.Image.open(image_file)

    # 3. 프롬프트
    SYSTEM_PROMPT = """
    당신은 약봉투/처방전 OCR 전문가입니다.
    이미지에서 아래 정보를 추출하여 JSON 리스트로만 응답하세요.
    
    추출 항목:
    - medicine_name: 약품명(성분 제외)
    - dosage: 1회 분량
    - frequency: 일일 횟수(숫자)
    - days: 총 일수(숫자)
    - usage: 복용법
    
    출력 형식:
    [{"medicine_name": "...", "dosage": "...", "frequency": "...", "days": "...", "usage": "..."}]
    """

    # 4. Gemini 호출
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[SYSTEM_PROMPT, img],
            config=types.GenerateContentConfig(
                temperature=0.0, # 정확도를 위해 0으로 설정 
                response_mime_type="application/json" 
            )
        )
        
        # 5. 결과 파싱
        res_text = response.text
        start_idx = res_text.find("[")
        end_idx = res_text.rfind("]")
        
        if start_idx != -1 and end_idx != -1:
            json_str = res_text[start_idx:end_idx+1]
            return json.loads(json_str)
        else:
            return json.loads(res_text)

    except Exception as e:
        st.error(f"OCR 처리 중 오류 발생: {e}")
        return []