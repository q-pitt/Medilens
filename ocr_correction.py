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

def correct_drug_names(ocr_list):
    """
    OCR 결과 리스트를 받아 오타를 보정한 리스트와
    보정 메트릭(수정 거리 등)을 함께 반환합니다.
    """
    sym_spell, jamo_to_original = load_symspell_db()
    
    if not sym_spell:
        # DB 로드 실패 시 원본 그대로 + 빈 통계 반환
        return ocr_list, {"total_edits": 0, "corrected_count": 0} 
        
    corrected_list = []
    
    # [Metrics] 통계 집계용 변수
    total_edits = 0
    corrected_count = 0
    change_logs = [] # [Evidence] 변경 증거 수집
    
    for item in ocr_list:
        raw_name = item.get('medicine_name', '').strip()
        if not raw_name:
            corrected_list.append(item)
            continue
            
        # 1. 단위 정규화 및 자모 분해
        norm_name = normalize_unit(raw_name)
        search_term = decompose_text(norm_name)
        
        # 2. SymSpell 검색
        suggestions = sym_spell.lookup(search_term, Verbosity.CLOSEST, max_edit_distance=2)
        
        # [Safety Check] 기본값: 원본 유지
        final_name = raw_name
        distance = 0
        is_corrected = False
        
        if suggestions:
            best_sug = suggestions[0]
            corrected_term = best_sug.term
            dist = best_sug.distance 
            
            # 원래 이름으로 복원
            candidate_name = jamo_to_original.get(corrected_term, raw_name)
            
            # [CRITICAL] 숫자 일치 여부 검증 (dosge mismatch 방지)
            if check_number_match(raw_name, candidate_name):
                final_name = candidate_name
                distance = dist
                if distance > 0:
                    is_corrected = True
            else:
                # 숫자 불일치 시 보정 거부 (안전 제일)
                pass

        # 결과 저장
        new_item = item.copy()
        new_item['corrected_medicine_name'] = final_name
        new_item['original_medicine_name'] = raw_name     
        
        corrected_list.append(new_item)
        
        # [Metrics] 집계
        if is_corrected:
            total_edits += distance
            corrected_count += 1
            change_logs.append({
                "before": raw_name,
                "after": final_name
            })
            
    # 통계 딕셔너리 생성
    stats = {
        "total_edits": total_edits,      # 총 수정된 글자 수
        "corrected_count": corrected_count, # 수정된 약물 개수
        "change_examples": change_logs[:5]  # [Evidence] 실제 변경 사례 (최대 5개)
    }
            
    return corrected_list, stats