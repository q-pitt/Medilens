import streamlit as st
from streamlit_calendar import calendar
import datetime
import pandas as pd
import data_manager as dm
import api_handler as ah
import re
from urllib.parse import quote

# 1. 초기 설정
st.set_page_config(page_title="메디렌즈", page_icon="💊", layout="wide")
today = datetime.date.today()

# 세션 상태 초기화
if 'medicines' not in st.session_state:
    st.session_state.medicines = dm.load_data()
if 'check_history' not in st.session_state:
    st.session_state.check_history = dm.load_history()

@st.cache_data(ttl=600, show_spinner=False)
def get_calendar_events(medicines, check_history):
    events = []
    for drug in medicines:
        for i in range(int(drug['days'])):
            curr = drug['start_date'] + datetime.timedelta(days=i)
            curr_str = curr.strftime("%Y-%m-%d")
            h_key = (curr_str, drug['name'])
            checked = check_history.get(h_key, False)
            
            events.append({
                "title": f"✅ {drug['name']}" if checked else drug['name'],
                "start": curr_str, "end": curr_str, "allDay": True, "display": "block",
                "backgroundColor": "#D4EDDA" if checked else drug.get('color', '#3D9DF3'),
                "borderColor": "#28A745" if checked else drug.get('color', '#3D9DF3'),
                "textColor": "#000000" if checked else "#FFFFFF",
            })
    return events

# 2. 사이드바 로직
with st.sidebar:
    st.title("🧬 MediLens")
    st.subheader("📸 처방전 업로드")
    uploaded_file = st.file_uploader("이미지를 선택하세요", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file:
        st.image(uploaded_file, caption="업로드된 이미지", use_container_width=True)
        if st.button("분석 및 등록", use_container_width=True):
            with st.spinner("Gemini가 처방전을 분석 중입니다..."):
                # 1. api_handler를 통해 이미지 분석
                ocr_result = ah.analyze_prescription(uploaded_file)
                
                if ocr_result:
                    # 2. data_manager를 통해 DB 매칭 및 저장
                    count = dm.process_and_save_ocr(ocr_result)
                    st.success(f"{count}개의 약을 등록했습니다!")
                    st.session_state.medicines = dm.load_data()
                    st.rerun()
                else:
                    st.error("분석에 실패했습니다. 이미지를 확인해주세요.")

    for _ in range(5): st.write("") 
    st.divider()
    
    if "delete_confirm" not in st.session_state: st.session_state.delete_confirm = False
    if not st.session_state.delete_confirm:
        if st.button("🗑️ 데이터 전체 초기화", use_container_width=True):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.sidebar.warning("⚠️ 삭제하시겠습니까?")
        c_y, c_n = st.columns(2)
        with c_y:
            if st.button("예", use_container_width=True):
                dm.reset_all_data()
                st.session_state.medicines = []
                st.session_state.check_history = {}
                st.session_state.delete_confirm = False
                st.rerun()
        with c_n:
            if st.button("아니오", use_container_width=True):
                st.session_state.delete_confirm = False
                st.rerun()

# 3. 달력 이벤트 구성 (캐싱된 함수 호출)
calendar_events = get_calendar_events(st.session_state.medicines, st.session_state.check_history)

# 4. 상단: 상세 정보
st.title("💊 메디렌즈")
with st.expander("🔍 등록된 모든 약 상세 정보 확인하기", expanded=False):
    if not st.session_state.medicines:
        st.info("등록된 약 정보가 없습니다.")
    else:
        for idx, drug in enumerate(st.session_state.medicines):
            col_info, col_del = st.columns([4, 1])
            
            with col_info:
                # --- 이름 정제 로직 ---
                raw_name = drug['name'].strip()
                last_open = raw_name.rfind('(')
                last_close = raw_name.rfind(')')

                # 마지막 괄호가 열리기만 하고 닫히지 않은 경우만 잘라냄
                if last_open > last_close:
                    display_name = raw_name[:last_open].strip()
                else:
                    display_name = raw_name
                # -----------------------

                st.markdown(f"### 💡 {display_name}")
                c1, c2, c3 = st.columns([2, 2, 1])

                with c1: st.info(drug.get('info', ' 정보 없음'))
                with c2: st.warning(drug.get('food', ' 정보 없음'))
                with c3:
                        clean_name_for_url = re.split(r'\(', drug['name'])[0].strip()
                        
                        # 2. 한글 이름을 URL 형식에 맞게 인코딩 (예: '세레온' -> '%EC%84%B8%EB%A0%88%EC%98%A8')
                        encoded_name = quote(clean_name_for_url)
                        
                        # 3. 최종 URL 생성
                        search_url = f"https://nedrug.mfds.go.kr/searchDrug?itemName={encoded_name}"
                        st.link_button("🔍 식약처 검색", search_url, use_container_width=True)
            
            with col_del:
                # 각 약마다 고유한 키를 부여하여 삭제 버튼 생성
                st.write("") # 간격 맞춤용
                if st.button(f"🗑️ 삭제", key=f"del_{drug['name']}_{idx}", use_container_width=True):
                    if dm.delete_medicine(drug['name']):
                        st.success(f"{drug['name']} 삭제 완료")
                        # 삭제 후 세션 상태 업데이트 및 새로고침
                        st.session_state.medicines = dm.load_data()
                        st.rerun()
            st.divider()

st.divider()

# 5. 하단: 달력 & 체크리스트
col_left, col_right = st.columns([1.2, 1], gap="large") 

with col_left:
    st.subheader("🗓️ 복약 스케줄")
    state = calendar(events=calendar_events, options={"height": 450}, key="fixed_medilens_calendar")

with col_right:
    clicked_date = state.get("dateClick", {}).get("date")
    if clicked_date:
        temp_date = datetime.datetime.strptime(clicked_date[:10], "%Y-%m-%d").date()
        view_date = temp_date + datetime.timedelta(days=1) if "T" in clicked_date else temp_date
    else:
        view_date = today

    st.subheader(f"📋 {view_date.strftime('%m월 %d일')} 체크리스트")
    active_drugs = [d for d in st.session_state.medicines if d['start_date'] <= view_date <= (d['start_date'] + datetime.timedelta(days=int(d['days'])-1))]
    
    for drug in active_drugs:
        with st.container(border=True):
            c_cb, c_name, c_day = st.columns([0.5, 3, 1])
            h_key = (str(view_date), drug['name'])
            checked = st.session_state.check_history.get(h_key, False)
            
            with c_cb:
                if st.checkbox("", value=checked, key=f"cb_{view_date}_{drug['name']}"):
                    if not checked:
                        st.session_state.check_history[h_key] = True
                        dm.save_history(st.session_state.check_history)
                else:
                    if checked:
                        st.session_state.check_history[h_key] = False
                        dm.save_history(st.session_state.check_history)
            
            with c_name:
                # --- 이름 정제 로직 ---
                d_raw_name = drug['name'].strip()
                d_last_open = d_raw_name.rfind('(')
                d_last_close = d_raw_name.rfind(')')

                if d_last_open > d_last_close:
                    d_display_name = d_raw_name[:d_last_open].strip()
                else:
                    d_display_name = d_raw_name
                # -----------------------
                st.markdown(f"**{d_display_name}** <span style='color:gray; font-size:0.8em;'>({drug['days']}일분)</span>", unsafe_allow_html=True)
                st.caption(f":blue[{drug['time']}]")
                
    if not active_drugs:
        st.info("복용할 약이 없습니다.")