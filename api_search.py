# api_search.py
import requests
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
