import json
import os
import streamlit as st

@st.cache_resource
def load_drug_rules(rule_path='data/drug_rules.json'):
    """
    약물 상호작용 규칙 데이터(JSON)를 로드합니다.
    """
    # 절대 경로 계산
    current_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(current_dir, rule_path)
    
    if not os.path.exists(full_path):
        # print(f"[ERROR] Interaction rules not found: {full_path}")
        return []
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            rules = json.load(f)
            # print(f"[DEBUG] {len(rules)} interaction rules loaded.")
            return rules
    except Exception as e:
        print(f"[ERROR] Failed to load rules: {e}")
        return []

def check_interactions(drug_list_json):
    """
    [입력] OCR/API 처리가 끝난 drug list (여러 약물)
    [출력] 발견된 위험 상호작용 리스트 (문자열 리스트)
    
    RAG 로직:
    1. 로컬 규칙(drug_rules.json)을 로드
    2. 입력 약물명에 규칙의 키워드가 포함되는지 검사
    3. 매칭되면 해당 메시지를 수집하여 반환
    """
    rules = load_drug_rules()
    found_warnings = []
    
    if not rules:
        return []
        
    # drug_list_json은 {"drugs": [...]} 형태일 수 있으므로 파싱
    target_drugs = drug_list_json if isinstance(drug_list_json, list) else drug_list_json.get('drugs', [])
    
    for drug in target_drugs:
        drug_name = drug.get('corrected_medicine_name', '') or drug.get('medicine_name', '')
        
        for rule in rules:
            keywords = rule.get('keywords', [])
            
            # 규칙 키워드 중 하나라도 약물명에 포함되면 경고 
            # 예: "아스피린프로텍트정" 안에 "아스피린"이 있으면 매칭
            for k in keywords:
                if k in drug_name:
                    # [RAG] 원본 상세 내용을 그대로 반환
                    content = rule.get('original_content', '')
                    msg = f"⚠️ [식약처 상호작용 정보 found] 키워드 '{k}' 관련:\n{content}"
                    
                    if msg not in found_warnings:
                        found_warnings.append(msg)
                    break 
                    
    return found_warnings
