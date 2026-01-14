import streamlit as st
from streamlit_calendar import calendar
import datetime
import pandas as pd # 여전히 날짜 계산 등에 필요할 수 있음 (또는 제거 가능)
import os
import json
import uuid
import random
import re
from urllib.parse import quote
import time

# --- [AI 분석 모듈 임포트] ---
import ocr
import ocr_correction
import api_search
import care_processor

# --- [DB 모듈 임포트] ---
import db

# ==========================================
# 1. 초기 설정 및 데이터 관리
# ==========================================
st.set_page_config(page_title="메디렌즈", page_icon="💊", layout="wide")

today = datetime.date.today()

# 사용자 식별 (먼저 가져옴)
user_id = db.get_user_id()

# --- 헬퍼 함수 ---

def get_random_color():
    """약 구분을 위한 랜덤 색상 부여"""
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", 
        "#F06292", "#AED581", "#FFD54F", "#4DB6AC", "#9575CD"
    ]
    return random.choice(colors)

def get_google_calendar_url(drug):
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    # 이름에서 괄호 제거
    clean_name = re.split(r'\(', drug['name'])[0].strip()
    title = quote(f"💊 [메디렌즈] {clean_name} 복용")
    
    details_text = f"용법: {drug.get('usage', '-')}\n효능: {drug.get('efficacy', '-')}\n주의사항: {drug.get('info', '-')}"
    details = quote(details_text)
    
    # 날짜 문자열 처리
    s_date_str = drug['start_date'] # DB에서 가져온건 문자열일 수 있음
    if isinstance(s_date_str, str):
        s_date_obj = datetime.datetime.strptime(s_date_str, "%Y-%m-%d").date()
    else:
        s_date_obj = s_date_str

    start_date = s_date_obj.strftime('%Y%m%d')
    end_date = s_date_obj.strftime('%Y%m%d')
    recur = quote(f"RRULE:FREQ=DAILY;COUNT={drug['days']}")
    
    return f"{base_url}&text={title}&details={details}&dates={start_date}/{end_date}&recur={recur}"

# --- 데이터 로드 (DB 연동) ---
# 세션 상태 초기화 (또는 리프레시)
user_medicines = db.get_medicines(user_id)
st.session_state.medicines = user_medicines

user_history = db.load_history(user_id)
st.session_state.check_history = user_history

# 리포트 로드 (세션에 없으면 DB에서 최신 조회)
if 'last_report' not in st.session_state:
    latest_report = db.load_latest_report(user_id)
    if latest_report:
        st.session_state['last_report'] = latest_report


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
                    st.write("🧠 AI가 복약 지도를 작성 중입니다...")
                    ai_result = care_processor.analyze_with_llm(final_json)
                    
                    if "error" in ai_result:
                        st.error(ai_result["error"])
                        st.stop()
                        
                    status.update(label="✅ 분석 완료! 데이터베이스에 등록합니다.", state="complete", expanded=False)

                # [Debug] 데이터 확인용
                with st.expander("🔍 AI 분석 중간 데이터 확인 (Debug, Click to open)"):
                    st.markdown("### 1. OCR 결과 (글자 인식)")
                    st.json(ocr_result)
                    
                    st.markdown("### 2. LLM 최종 분석 결과")
                    st.json(ai_result)

                    st.warning("위 데이터에서 'frequency'(횟수)가 정확히 3으로 인식되었는지, 'time_list'가 ['아침','점심','저녁']으로 생성되었는지 확인해주세요.")

                # [Case ID 생성] 이번 처방전 업로드를 하나의 사건(Case)으로 그룹핑
                case_id = str(uuid.uuid4())

                # 1. 약물 DB 저장 (반복문)
                count = 0
                for drug in ai_result.get('drug_analysis', []):
                    drug_name = drug.get('name', '알 수 없음')
                    
                    try:
                        raw_days = drug.get('days', 3)
                        days = int(raw_days)
                    except:
                        days = 3
                    
                    # [시간 파싱] 약물별 개별 스케줄 우선 적용
                    d_schedule = drug.get('time_list', [])
                    if not d_schedule:
                        # 없으면 전체 공용 스케줄 사용
                        d_schedule = ai_result.get('schedule_time_list', ["식후 30분"])
                    
                    # 리스트 -> 문자열 변환 ("아침, 점심, 저녁")
                    time_str = ", ".join(d_schedule)

                    # DB 저장용 딕셔너리 구성
                    entry = {
                        "name": drug_name,
                        "days": days,
                        "color": get_random_color(),
                        "time": time_str, 
                        "start_date": today, 
                        "efficacy": drug.get('efficacy', '-'), 
                        "usage": drug.get('usage', '-'),       
                        "info": drug.get('caution', '특이사항 없음'), 
                        "food": drug.get('food_guide', '특이사항 없음')
                    }
                    
                    # case_id 전달
                    if db.add_medicine(user_id, entry, case_id=case_id):
                        count += 1
                
                # 2. 리포트 DB 저장
                if "report" in ai_result:
                    report_data = ai_result["report"]
                    report_data["medicines"] = ai_result.get('drug_analysis', [])
                    
                    # case_id 전달
                    db.save_report(user_id, report_data, case_id=case_id)
                    st.session_state['last_report'] = report_data
                
                st.success(f"{count}개의 약물이 클라우드에 성공적으로 등록되었습니다!")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"처리 중 오류가 발생했습니다: {e}")

    # 사이드바 하단
    for _ in range(10): st.sidebar.write("")
    st.divider()
    
    # 데이터 초기화 (전체 삭제 기능은 복잡하므로 개별 삭제 권장, 일단 비활성화 or 전체 삭제 구현)
    if st.sidebar.button("DB 새로고침", use_container_width=True):
        st.rerun()


# ==========================================
# 3. 달력 이벤트 구성
# ==========================================
calendar_events = []

for drug in st.session_state.medicines:
    # DB에서 가져온 날짜는 String일 수 있음
    s_date_str = drug['start_date']
    if isinstance(s_date_str, str):
        start_date = datetime.datetime.strptime(s_date_str, "%Y-%m-%d").date()
    else:
        start_date = s_date_str

    days = int(drug['days'])
    
    for i in range(days):
        current_date = start_date + datetime.timedelta(days=i)
        current_date_str = current_date.strftime("%Y-%m-%d")
        
        # 키 형식 주의: (날짜문자열, 약이름)
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
# 4. 상단: 상세 요약 및 리포트
# ==========================================
st.title("💊 메디렌즈 - AI 복약 스케줄러")
st.divider()

st.subheader("📝 종합 복약 리포트")
st.write("사용자의 모든 처방 약을 분석하여 종합 가이드를 생성합니다.")

if 'last_report' not in st.session_state or not st.session_state['last_report']:
    if st.session_state.medicines:
        st.info("💡 등록된 리포트가 없습니다.")
    else:
        st.info("비어있는 처방전입니다. 사이드바에서 약을 먼저 등록해주세요.")
        
# [리포트 표시]
if 'last_report' in st.session_state and st.session_state['last_report']:
    report = st.session_state['last_report']
    
    if isinstance(report, str) or "error" in report:
        st.error(report if isinstance(report, str) else report.get("error"))
    else:
        # 1. 인사말
        st.info(report.get("opening_message", "안녕하세요."))
        st.divider()

        # 2. 약물별 상세 카드
        st.subheader("💊 처방 약 설명과 복용법")
        for med in report.get("medicines", []):
            with st.expander(f"**{med.get('name', '약품')}** 상세 정보", expanded=True):
                
                c_eff, c_use = st.columns(2)
                with c_eff:
                    st.markdown("**💊 효능·효과**")
                    st.info(med.get('efficacy', '정보 없음'))
                with c_use:
                    st.markdown("**📝 용법·용량**")
                    st.success(med.get('usage', '정보 없음'))
                
                c_warn, c_food = st.columns(2)
                with c_warn:
                    st.markdown("**⚠️ 주의사항**")
                    st.warning(med.get('caution', '정보 없음'))
                with c_food:
                    st.markdown("**🥗 음식 가이드**")
                    food_txt = med.get('food_guide', '정보 없음')
                    if food_txt and food_txt != '특별한 제한 없음':
                        st.error(food_txt)
                    else:
                        st.caption("특별한 제한 없음")
                
                st.divider()
                c_link, c_del = st.columns([4, 1])
                with c_link:
                    clean_name = re.split(r'\(', med['name'])[0].strip()
                    encoded_name = quote(clean_name)
                    url = f"https://nedrug.mfds.go.kr/searchDrug?itemName={encoded_name}"
                    st.link_button("🔍 식약처 상세 검색", url, use_container_width=True)
                
                with c_del:
                    # [삭제] DB 연동
                    if st.button("🗑️ 삭제", key=f"del_{med['name']}"):
                        if db.delete_medicine(user_id, med['name']):
                            st.success("삭제되었습니다.")
                            time.sleep(0.5)
                            st.rerun()

        st.divider()

        # 3. 종합 정보
        schedules = report.get("schedule_proposal", {})
        if schedules:
            st.subheader(schedules.get("title", "복용 스케줄"))
            st.markdown(schedules.get("content", ""))

        safety = report.get("safety_warnings", {})
        if safety:
            st.subheader(safety.get("title", "안전 주의사항"))
            st.markdown(safety.get("content", ""))
            
        tips = report.get("medication_tips", {})
        if tips:
            st.subheader(tips.get("title", "복약 팁"))
            st.markdown(tips.get("content", ""))

st.divider()

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
        if "T" in clicked_date_str: # Timezone issue fix
            view_date = temp_date + datetime.timedelta(days=1)
        else:
            view_date = temp_date
    else:
        view_date = today

    st.subheader(f"📋 {view_date.strftime('%m월 %d일')} 체크리스트")
    
    active_drugs = []
    
    # DB 데이터를 순회하며 해당 날짜에 먹어야 하는 약 필터링
    for i, drug in enumerate(st.session_state.medicines):
        s_date_str = drug['start_date']
        if isinstance(s_date_str, str):
            drug_start = datetime.datetime.strptime(s_date_str, "%Y-%m-%d").date()
        else:
            drug_start = s_date_str
            
        try:
            raw_days = drug.get('days', 3)
            days = int(raw_days)
        except:
            days = 3
        drug_end = drug_start + datetime.timedelta(days=days - 1)
        
        if drug_start <= view_date <= drug_end:
            active_drugs.append(drug)
            remaining = (drug_end - view_date).days
            
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2.2, 1.5, 1, 0.8, 1.2])
                
                with c1: st.markdown(f"**{drug['name']}**")
                with c2: st.caption(f"{drug['time']}")
                with c3: st.caption(f"📅 {days}일분")
                with c4: st.markdown(f"**D-{remaining}**")
                with c5 :
                    cal_link = get_google_calendar_url(drug)
                    st.markdown(
                        f'<a href="{cal_link}" target="_blank" style="font-size: 0.75em; color: white; background-color: #4285F4; padding: 4px 8px; border-radius: 5px; text-decoration: none; display: inline-block;">🔔 알림 등록</a>', 
                        unsafe_allow_html=True)

                st.divider()
                
                # [Time-based Check logic]
                # 시간 파싱: "아침, 저녁" -> ["아침", "저녁"] / "식후 30분" -> ["식후 30분"]
                time_list = [t.strip() for t in drug['time'].split(',')]
                
                # 한 줄에 여러 체크박스 배치
                cols = st.columns(len(time_list))
                target_date_str = view_date.strftime("%Y-%m-%d")

                for idx, t_val in enumerate(time_list):
                    with cols[idx]:
                        # Key에 Drug Index(i)와 Time Index(idx) 모두 포함하여 절대 중복 방지
                        h_key = (target_date_str, drug['name'], t_val)
                        
                        # DB에서 로드해온 기록 확인
                        is_checked = st.session_state.check_history.get(h_key, False)
                        
                        # Key에 i (약물 인덱스) 추가
                        if st.checkbox(f"{t_val} 복용", value=is_checked, key=f"cb_{i}_{target_date_str}_{drug['name']}_{t_val}"):
                            if not is_checked: # False -> True 될 때
                                db.toggle_check(user_id, target_date_str, drug['name'], t_val, True)
                                st.session_state.check_history[h_key] = True
                                st.rerun()
                        else:
                            if is_checked: # True -> False 될 때
                                db.toggle_check(user_id, target_date_str, drug['name'], t_val, False)
                                st.session_state.check_history[h_key] = False
                                st.rerun()


    if not active_drugs and st.session_state.medicines:
        st.info("해당 날짜에는 복용할 약이 없습니다.")