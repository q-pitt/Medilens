# api_search.py
import requests
import json
import re
import html
import streamlit as st 

# =========================================================
# 1. 설정 및 유틸리티
# =========================================================
# API 키는 secrets.toml에서 가져옴
try:
    # secrets.toml에 [public_data_portal] 섹션의 api_key를 사용
    SERVICE_KEY = st.secrets["public_data_portal"]["api_key"]
except Exception as e:
    st.error("❌ secrets.toml에 [public_data_portal] api_key 설정이 필요합니다.")
    print(f"[ERROR] API Key Missing: {e}")
    SERVICE_KEY = "" 

API_URL = "http://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06"

def remove_xml_tags(text):
    if not text: return ""
    text = html.unescape(text)
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return clean_text

def remove_parentheses(text):
    if not text: return ""
    return re.sub(r'\(.*?\)', '', text).strip()

def search_drug_api(drug_name):
    """단일 약품 검색 함수"""
    if not drug_name: return None
    
    params = {
        "serviceKey": SERVICE_KEY,
        "type": "json", 
        "item_name": drug_name,
        "numOfRows": "1",
        "pageNo": "1"
    }
    
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        
        if response.status_code != 200:
            return None

        try:
            data = response.json()
        except:
            return None
            
        if 'body' in data and 'items' in data['body']:
            items = data['body']['items']
            if items: return items[0]
            
        return None
            
    except Exception as e:
        print(f"API Error: {e}")
        return None

# =========================================================
# 2. 메인 처리 함수 (외부 호출용)
# =========================================================
def run_api_search(corrected_data_list):
    """
    [입력] 보정된 약품 리스트 (List of Dict)
    [출력] API 정보가 추가된 리스트
    """
    final_list = []
    
    for item in corrected_data_list:
        new_item = item.copy()
        
        # 검색어 결정 순서: 1.보정된 이름 -> 2.힌트(전체) -> 3.원본 이름
        hints = new_item.get('api_search_hint', {})
        full_query = new_item.get('corrected_medicine_name', hints.get('full_query', ''))
        base_query = hints.get('base_query', '')
        
        api_result = None
        search_method = ""

        # --- 3단계 검색 ---
        print(f"\n[DEBUG] API 검색 시작: {full_query}")
        
        # 1차: 풀네임 검색
        if full_query:
            print(f"  -> 1차 검색 시도: {full_query}")
            api_result = search_drug_api(full_query)
            if api_result: 
                search_method = "1차_풀네임"
                print(f"  -> 1차 성공!")
        
        # 2차: 제품명(용량제외) 검색
        if not api_result and base_query and full_query != base_query:
            print(f"  -> 2차 검색 시도: {base_query}")
            api_result = search_drug_api(base_query)
            if api_result: 
                search_method = "2차_제품명"
                print(f"  -> 2차 성공!")
            
        # 3차: 괄호 제거 검색
        if not api_result and base_query:
            clean_query = remove_parentheses(base_query)
            if clean_query != base_query and len(clean_query) > 1:
                # print(f"  -> 3차 검색 시도: {clean_query}")
                api_result = search_drug_api(clean_query)
                if api_result: 
                    search_method = "3차_괄호제거"
                    print(f"  -> 3차 성공!")

        # --- 결과 매핑 ---
        if api_result:
            # XML 태그 제거 후 저장
            efficacy = remove_xml_tags(api_result.get('EE_DOC_DATA', ''))
            usage = remove_xml_tags(api_result.get('UD_DOC_DATA', ''))
            caution = remove_xml_tags(api_result.get('NB_DOC_DATA', ''))
            
            new_item['api_info'] = {
                "success": True,
                "method": search_method,
                "item_name": api_result.get('ITEM_NAME'),
                "entp_name": api_result.get('ENTP_NAME'),
                "efficacy": efficacy,
                "usage": usage,
                "precautions": caution,
                "valid_term": api_result.get('VALID_TERM'),
                "storage_method": api_result.get('STORAGE_METHOD'),
                "image_url": api_result.get('ITEM_IMAGE') # (옵션) 약 사진 URL이 있다면
            }
        else:
            new_item['api_info'] = {
                "success": False,
                "note": "식약처 데이터 검색 실패"
            }
            
        final_list.append(new_item)
        
    return final_list