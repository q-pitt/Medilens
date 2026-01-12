import json
import PIL.Image
import os
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

# .env 파일 로드
load_dotenv()

# API 설정
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
KFDA_API_KEY = os.getenv("KFDA_API_KEY") # 식약처 API 키 추가

client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_ID = "gemini-3-flash-preview"

SYSTEM_PROMPT = """
OCR 전문가로서 이미지의 약 정보를 추출하여 JSON 리스트로만 출력하세요. 설명 금지.
형식: [{"medicine_name": "..", "dosage": "..", "frequency": "..", "days": "..", "usage": ".."}]
"""

def analyze_prescription(uploaded_file):
    """Gemini를 이용해 이미지를 분석하여 JSON 데이터 반환"""
    try:
        img = PIL.Image.open(uploaded_file)
        
        fast_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            temperature=1.0
        )

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[SYSTEM_PROMPT, img],
            config=fast_config
        )
        
        res_text = response.text
        start_idx = res_text.find("[")
        end_idx = res_text.rfind("]") + 1
        json_data = json.loads(res_text[start_idx:end_idx])
            
        return json_data
    except Exception as e:
        print(f"Gemini API 분석 에러: {e}")
        return None

def get_kfda_info(drug_name):
    """식약처 API를 호출하여 약 정보를 가져오는 함수"""
    # 1. 키가 설정되지 않았거나 예시 값인 경우
    if not KFDA_API_KEY or "your_kfda" in KFDA_API_KEY:
        return "NEED_KEY"

    url = "http://apis.data.go.kr/1471000/DrbEasyService/getDrbEasyDrugList"
    params = {
        'serviceKey': KFDA_API_KEY,
        'itemName': drug_name,
        'type': 'json'
    }

    try:
        # timeout 15초 설정
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            items = data.get('body', {}).get('items', [])
            if items:
                return items[0] # 검색 결과가 있으면 첫 번째 아이템 반환
    except Exception as e:
        print(f"식약처 API 통신 에러: {e}")
    
    return "NO_DATA" # 키는 있으나 검색 결과가 없거나 통신 실패 시