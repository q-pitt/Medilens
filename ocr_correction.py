# ocr_correction.py
import csv
import re
import streamlit as st
from symspellpy import SymSpell, Verbosity
from jamo import h2j, j2hcj

import os 

# === [DB 로딩 캐싱] 속도 최적화 ===
@st.cache_resource
def load_symspell_db(db_path='drug_db.csv'): 
    # print(f"[DEBUG] load_symspell_db 시작")
    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    jamo_to_original = {}
    
    # 절대 경로 계산 (현재 파일 위치 기준)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(current_dir, db_path)
    # print(f"[DEBUG] DB 경로: {full_path}")

    if not os.path.exists(full_path):
        # print(f"[ERROR] DB 파일이 없습니다: {full_path}")
        return None, None
    
    try:
        with open(full_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                full_name = row.get('drug_name', '').strip() 
                if not full_name: continue
                
                # 전처리
                search_name = re.sub(r'\(.*?\)', '', full_name).strip()
                search_name = normalize_unit(search_name)
                jamo_word = decompose_text(search_name)
                
                sym_spell.create_dictionary_entry(jamo_word, 1)
                
                clean_full_name = re.sub(r'\s+', '', full_name)
                jamo_to_original[jamo_word] = convert_to_api_format(clean_full_name)
                count += 1
            # print(f"[DEBUG] DB 로딩 완료. {count}개 단어 로드됨.")
                
    except Exception as e:
        st.error(f"DB 로딩 실패: {e}")
        print(f"[ERROR] DB 로딩 예외: {e}")
        return None, None
        
    return sym_spell, jamo_to_original


def decompose_text(text):
    if not text: return ""
    return j2hcj(h2j(text))
    
def normalize_unit(text):
    if not text: return ""
    text = re.sub(r'\s+', '', text).lower()
    text = text.replace("밀리그램", "mg").replace("밀리그람", "mg")
    return text

def convert_to_api_format(text):
    text = re.sub(r'(\d+)mg', r'\1밀리그램', text, flags=re.IGNORECASE)
    return text

def check_number_match(text1, text2):
    nums1 = set(re.findall(r'\d+', text1))
    nums2 = set(re.findall(r'\d+', text2))
    return nums1 == nums2

def split_name_and_dosage(text):
    pattern = r'(\d+(?:\.\d+)?(?:밀리그램|밀리리터|그램|mg|ml|g|l))'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
         dosage = match.group(1)
         name_only = text.replace(dosage, "").strip()
         return name_only, dosage
    return text, ""

def correct_ocr_data(ocr_list):
    """
    [입력] OCR 결과 리스트 (딕셔너리 리스트)
    [출력] 보정된 리스트
    """
    # 1. DB 로딩 (캐싱됨)
    sym_spell, jamo_to_original = load_symspell_db()
    
    if not sym_spell:
        return ocr_list # DB 없으면 원본 반환

    corrected_list = []
    
    for item in ocr_list:
        new_item = item.copy() # 원본 보존
        input_text = item.get('medicine_name', '')
        
        if not input_text:
            corrected_list.append(new_item)
            continue
            
        # 보정 로직
        normalized_input = normalize_unit(input_text)
        input_jamo = decompose_text(normalized_input)
        
        suggestions = sym_spell.lookup(input_jamo, Verbosity.CLOSEST, max_edit_distance=2)
        
        final_text = convert_to_api_format(re.sub(r'\s+', '', input_text))
        
        if suggestions:
            best_jamo = suggestions[0].term
            if best_jamo in jamo_to_original:
                corrected_word = jamo_to_original[best_jamo]
                # 숫자 일치 확인
                if check_number_match(input_text, corrected_word):
                    final_text = corrected_word
        
        new_item['corrected_medicine_name'] = final_text
        
        # 힌트 생성
        base, dosage = split_name_and_dosage(final_text)
        new_item['api_search_hint'] = {
            "full_query": final_text,
            "base_query": base,
            "dosage": dosage
        }
        
        corrected_list.append(new_item)
        
    return corrected_list