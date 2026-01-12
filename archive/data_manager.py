import pandas as pd
import os
import datetime
import streamlit as st
import re
import random
import api_search

USER_DB = "user_meds.csv"
HISTORY_FILE = "check_history.csv"

def get_random_color():
    """약 구분을 위한 랜덤 색상 부여"""
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", 
        "#F06292", "#AED581", "#FFD54F", "#4DB6AC", "#9575CD"
    ]
    return random.choice(colors)

@st.cache_data(ttl=600, show_spinner=False) 
def load_data():
    if os.path.exists(USER_DB):
        try:
            df = pd.read_csv(USER_DB, encoding='utf-8-sig')
        except:
            df = pd.read_csv(USER_DB, encoding='cp949')
        
        df['start_date'] = pd.to_datetime(df['start_date']).dt.date
        return df.to_dict('records')
    return []

def process_and_save_ocr(ocr_data):
    """Gemini 결과를 식약처 API 정보와 결합하여 저장"""
    today = datetime.date.today()
    
    # 처방전 내 최장 복용일수 계산 (보정용)
    all_days = [int(item.get('days', 1)) for item in ocr_data if item.get('days')]
    max_days = max(all_days) if all_days else 3

    new_med_list = []
    for item in ocr_data:
        raw_name = item.get('medicine_name', '').strip()
        # 이름 정제 (괄호 앞부분만 추출)
        clean_name = re.split(r'\(', raw_name)[0].strip()
        
        # --- 식약처 정보 매칭 로직 ---
        # api_search.search_drug_api를 사용 (dict 또는 None 반환)
        api_result = api_search.search_drug_api(clean_name)
        
        if api_result:
            # API에서 가져온 실제 정보 할당 (XML 태그 제거 함수 등을 api_search 내부에서 처리하지 않고 원본을 반환한다면 여기서 처리 필요하지만, 
            # api_search.py 코드를 보면 search_drug_api는 원본 dict를 반환함. 
            # 하지만 api_search.run_api_search 에서는 태그 제거 로직이 있음.
            # search_drug_api 결과는 raw 데이터임. 태그 제거가 필요함.
            # api_search.py에 remove_xml_tags가 있지만 import 가능 여부 확인 필요.
            # api_search.py 내의 remove_xml_tags는 모듈 레벨 함수이므로 import 가능.
            
            display_info = api_search.remove_xml_tags(api_result.get('EE_DOC_DATA', "효능 정보가 없습니다."))
            display_food = api_search.remove_xml_tags(api_result.get('NB_DOC_DATA', "주의사항 정보가 없습니다."))
        else:
            display_info = "❓ 정보 없음 (식약처 미등록 또는 검색 실패)"
            display_food = "정보 없음"
        # ----------------------------

        # 복용 일수 보정
        current_days = int(item.get('days', 1))
        if current_days <= 1:
            current_days = max_days
        
        med_info = {
            "name": clean_name,
            "info": display_info,
            "food": display_food,
            "color": get_random_color(),
            "start_date": today,
            "days": current_days,
            "time": item.get('usage', '식후 30분')
        }
        new_med_list.append(med_info)

    # 신규 데이터 저장
    pd.DataFrame(new_med_list).to_csv(USER_DB, index=False, encoding='utf-8-sig')
    
    st.cache_data.clear()
    return len(new_med_list)

@st.cache_data
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            df_h = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
        except:
            df_h = pd.read_csv(HISTORY_FILE, encoding='cp949')
        return dict(zip(zip(df_h['date'].astype(str), df_h['name']), df_h['checked']))
    return {}

def save_history(check_history):
    history_list = []
    for (date, name), checked in check_history.items():
        history_list.append({"date": date, "name": name, "checked": checked})
    if history_list:
        pd.DataFrame(history_list).to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
    st.cache_data.clear() 

def reset_all_data():
    if os.path.exists(USER_DB): os.remove(USER_DB)
    if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
    st.cache_data.clear()

def delete_medicine(drug_name):
    if os.path.exists(USER_DB):
        df = pd.read_csv(USER_DB, encoding='utf-8-sig')
        new_df = df[df['name'] != drug_name]
        new_df.to_csv(USER_DB, index=False, encoding='utf-8-sig')
        st.cache_data.clear()
        return True
    return False