import streamlit as st
from streamlit_calendar import calendar
import datetime
import pandas as pd
import os
import json
import random
import re
from urllib.parse import quote

# --- [AI 분석 모듈 임포트] ---
import ocr
import ocr_correction
import api_search
import care_processor

# ==========================================
# 1. 초기 설정 및 데이터 관리
# ==========================================
st.set_page_config(page_title="메디렌즈", page_icon="💊", layout="wide")

DB_FILE = "medilens_db.csv"
HISTORY_FILE = "check_history.csv" 
today = datetime.date.today()

def get_random_color():
    """약 구분을 위한 랜덤 색상 부여"""
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", 
        "#F06292", "#AED581", "#FFD54F", "#4DB6AC", "#9575CD"
    ]
    return random.choice(colors)

# 데이터 로드 함수
def load_data():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df['start_date'] = pd.to_datetime(df['start_date']).dt.date
        return df.to_dict('records')
    return []

def load_history():
    if os.path.exists(HISTORY_FILE):
        df_h = pd.read_csv(HISTORY_FILE)
        # (날짜문자열, 약이름) 튜플을 키로 사용
        return dict(zip(zip(df_h['date'].astype(str), df_h['name']), df_h['checked']))
    return {}

# 데이터 저장 함수
def save_history():
    history_list = []
    for (date, name), checked in st.session_state.check_history.items():
        history_list.append({"date": date, "name": name, "checked": checked})
    if history_list:
        pd.DataFrame(history_list).to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')

def delete_medicine(drug_name):
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
        except:
            df = pd.read_csv(DB_FILE, encoding='cp949')
            
        new_df = df[df['name'] != drug_name]
        new_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        return True
    return False

# 세션 상태 초기화
if 'medicines' not in st.session_state:
    st.session_state.medicines = load_data()
if 'check_history' not in st.session_state:
    st.session_state.check_history = load_history()

# ==========================================
# 2. 사이드바: 이미지 업로드
# ==========================================
with st.sidebar:
    st.title("🧬 MediLens")
    st.subheader("📸 처방전 업로드")
    uploaded_file = st.file_uploader("이미지를 선택하세요", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file:
        st.image(uploaded_file, caption="업로드된 이미지", use_container_width=True)
        if st.button("🚀 AI 정밀 분석 및 등록", use_container_width=True):
            
            try:
                # --- [AI 분석 파이프라인 시작] ---
                with st.status("Medilens AI가 분석 중입니다...", expanded=True) as status:
                    
                    # 1. OCR
                    st.write("👁️ 글자를 읽고 있습니다... (OCR)")
                    ocr_result = ocr.run_ocr(uploaded_file)
                    if not ocr_result:
                        status.update(label="❌ OCR 실패", state="error")
                        st.stop()
                        
                    # 2. 오타 보정
                    st.write("🔧 약물 DB와 대조하여 오타를 수정합니다...")
                    corrected_data = ocr_correction.correct_ocr_data(ocr_result)
                    
                    # 3. API 검색
                    st.write("🔍 식약처 데이터를 조회합니다...")
                    final_data_list = api_search.run_api_search(corrected_data)
                    
                    final_json = {
                        "drugs": final_data_list, 
                        "meta": {"source": "Medilens", "timestamp": str(datetime.datetime.now())}
                    }
                    
                    # 4. LLM 분석 (RAG 포함)
                    st.write("🧠 AI 약사가 복약 지도를 작성 중입니다...")
                    ai_result = care_processor.analyze_with_llm(final_json)
                    
                    if "error" in ai_result:
                        st.error(ai_result["error"])
                        st.stop()
                        
                    status.update(label="✅ 분석 완료! 데이터베이스에 등록합니다.", state="complete", expanded=False)

                # --- [데이터 변환 및 저장] ---
                new_data = []
                # colors = ["#FF4B4B", "#2ECC71", "#3D9DF3", "#FFA500", "#9B59B6"] (기존 고정 색상 제거)
                schedule_list = ai_result.get('schedule_time_list', [])
                time_str = ", ".join(schedule_list) if schedule_list else "식후 30분"
                
                for idx, drug in enumerate(ai_result.get('drug_analysis', [])):
                    drug_name = drug.get('name', '알 수 없음')
                    days = 3 # 기본 3일
                    
                    entry = {
                        "name": drug_name,
                        "days": days,
                        "color": get_random_color(), # 랜덤 파스텔톤 색상 적용
                        "time": time_str, 
                        "start_date": today, 
                        "efficacy": drug.get('efficacy', '-'), # [추가] 효능
                        "usage": drug.get('usage', '-'),       # [추가] 용법
                        "info": drug.get('precautions', '특이사항 없음'),
                        "food": drug.get('food_guide', '특이사항 없음')
                    }
                    new_data.append(entry)

                if os.path.exists(DB_FILE):
                    df_old = pd.read_csv(DB_FILE)
                    df_new = pd.DataFrame(new_data)
                    df_combined = pd.concat([df_old, df_new], ignore_index=True)
                else:
                    df_combined = pd.DataFrame(new_data)
                    
                df_combined.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
                
                st.session_state.medicines = load_data()
                st.success(f"{len(new_data)}개의 약물이 성공적으로 등록되었습니다!")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"처리 중 오류가 발생했습니다: {e}")

    # 사이드바 하단 공백
    for _ in range(10): st.sidebar.write("")
    st.divider()
    
    # 데이터 초기화 로직
    if "delete_confirm" not in st.session_state:
        st.session_state.delete_confirm = False

    if not st.session_state.delete_confirm:
        if st.sidebar.button("🗑️ 데이터 전체 초기화", use_container_width=True):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.sidebar.warning("⚠️ 정말 모든 데이터를 삭제할까요?")
        col_yes, col_no = st.sidebar.columns(2)
        with col_yes:
            if st.button("예", use_container_width=True):
                if os.path.exists(DB_FILE): os.remove(DB_FILE)
                if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
                st.session_state.medicines = []
                st.session_state.check_history = {}
                st.session_state.delete_confirm = False
                st.rerun()
        with col_no:
            if st.button("아니오", use_container_width=True):
                st.session_state.delete_confirm = False
                st.rerun()

# ==========================================
# 3. 달력 이벤트 구성
# ==========================================
calendar_events = []

for drug in st.session_state.medicines:
    for i in range(int(drug['days'])):
        current_date = drug['start_date'] + datetime.timedelta(days=i)
        current_date_str = current_date.strftime("%Y-%m-%d")
        
        h_key = (current_date_str, drug['name'])
        is_checked = st.session_state.check_history.get(h_key, False)
        
        display_title = f"✅ {drug['name']}" if is_checked else drug['name']
        base_color = drug.get('color', '#3D9DF3')
        
        calendar_events.append({
            "title": display_title,
            "start": current_date_str,
            "end": current_date_str,
            "allDay": True,
            "display": "block",
            "backgroundColor": "#D4EDDA" if is_checked else base_color,
            "borderColor": "#28A745" if is_checked else base_color,
            "textColor": "#000000" if is_checked else "#FFFFFF",
        })

# ==========================================
# 4. 상단: 상세 요약
# ==========================================
st.title("💊 메디렌즈 - AI 복약 스케줄러")
st.divider()

st.subheader("🔍 등록된 약 상세 요약 및 주의사항")

if not st.session_state.medicines:
    st.info("등록된 약 정보가 없습니다. 사이드바에서 처방전을 업로드해 주세요.")
else:
    for drug in st.session_state.medicines:
        with st.expander(f"💡 {drug['name']} 상세 정보", expanded=True):
            # 1. 상단: 효능 & 용법
            c_eff, c_use = st.columns(2)
            with c_eff:
                st.markdown("**� 효능·효과**")
                st.info(drug.get('efficacy', '정보 없음'))
            with c_use:
                st.markdown("**📝 용법·용량**")
                st.success(drug.get('usage', '정보 없음'))
            
            # 2. 하단: 주의사항 & 음식
            c_warn, c_food = st.columns(2)
            with c_warn:
                st.markdown("**⚠️ 주의사항**")
                st.warning(drug.get('info', '정보 없음'))
            with c_food:
                st.markdown("**🥗 음식 가이드**")
                food_txt = drug.get('food', '정보 없음')
                if food_txt and food_txt != '특별한 제한 없음':
                    st.error(food_txt)
                else:
                    st.secondary_label = "특별한 제한 없음"
                    st.caption("특별한 제한 없음")
            
            st.divider()
            c_link, c_del = st.columns([4, 1])
            
            with c_link:
                # 식약처 검색 링크
                clean_name = re.split(r'\(', drug['name'])[0].strip()
                encoded_name = quote(clean_name)
                url = f"https://nedrug.mfds.go.kr/searchDrug?itemName={encoded_name}"
                st.link_button("🔍 식약처 상세 검색", url, use_container_width=True)
                
            with c_del:
                # 개별 삭제 버튼
                if st.button("🗑️ 삭제", key=f"del_{drug['name']}"):
                    if delete_medicine(drug['name']):
                        st.success("삭제되었습니다.")
                        st.session_state.medicines = load_data()
                        st.rerun()

st.markdown("---")

# ==========================================
# 5. 하단: 5:5 분할 레이아웃 (달력 & 체크리스트)
# ==========================================
col_left, col_right = st.columns([1, 1], gap="large")

# --- [왼쪽: 바둑판 달력] ---
with col_left:
    st.subheader("🗓️ 복약 스케줄")
    calendar_options = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"},
        "initialView": "dayGridMonth", 
        "height": 550,
    }
    state = calendar(events=calendar_events, options=calendar_options, key="main_cal")

# --- [오른쪽: 체크리스트] ---
with col_right:
    clicked_date_str = state.get("dateClick", {}).get("date")
    if clicked_date_str:
        temp_date = datetime.datetime.strptime(clicked_date_str[:10], "%Y-%m-%d").date()
        if "T" in clicked_date_str:
            view_date = temp_date + datetime.timedelta(days=1)
        else:
            view_date = temp_date
    else:
        view_date = today

    st.subheader(f"📋 {view_date.strftime('%m월 %d일')} 체크리스트")
    
    active_drugs = []
    for drug in st.session_state.medicines:
        drug_start = drug['start_date']
        drug_end = drug_start + datetime.timedelta(days=int(drug['days']) - 1)
        
        if drug_start <= view_date <= drug_end:
            active_drugs.append(drug)
            remaining = (drug_end - view_date).days
            
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([0.5, 2, 2, 1.5, 1])
                with c1:
                    h_key = (str(view_date), drug['name'])
                    is_checked = st.session_state.check_history.get(h_key, False)
                    if st.checkbox("복용 완료", label_visibility="collapsed", value=is_checked, key=f"cb_{view_date}_{drug['name']}"):
                        st.session_state.check_history[h_key] = True
                        save_history()
                    else:
                        st.session_state.check_history[h_key] = False
                        save_history()
                with c2: st.markdown(f"**{drug['name']}**")
                with c3: st.caption(f"⏰ {drug['time']}")
                with c4: st.caption(f"📅 {drug['days']}일분")
                with c5: st.markdown(f"**D-{remaining}**")

    if not active_drugs and st.session_state.medicines:
        st.info("해당 날짜에는 복용할 약이 없습니다.")
