import streamlit as st
from streamlit_calendar import calendar
import datetime
import pandas as pd
import os

# ==========================================
# 1. 초기 설정 및 데이터 관리
# ==========================================
st.set_page_config(page_title="메디렌즈", page_icon="💊", layout="wide")

DB_FILE = "medilens_db.csv"
HISTORY_FILE = "check_history.csv" 
today = datetime.date.today()

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

# 세션 상태 초기화
if 'medicines' not in st.session_state:
    st.session_state.medicines = load_data()
if 'check_history' not in st.session_state:
    st.session_state.check_history = load_history()

# ==========================================
# 2. 사이드바: 이미지 업로드
# ==========================================
# ==========================================
# 2. 사이드바: 이미지 업로드 및 초기화
# ==========================================
with st.sidebar:
    st.title("🧬 MediLens")
    st.subheader("📸 처방전 업로드")
    uploaded_file = st.file_uploader("이미지를 선택하세요", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file:
        st.image(uploaded_file, caption="업로드된 이미지", use_container_width=True)
        if st.button("분석 및 등록", use_container_width=True):
            # 분석 데이터 시뮬레이션
            yesterday = today - datetime.timedelta(days=1)
            new_data = [
                {"name": "세레온캡슐", "days": 14, "color": "#FF4B4B", "time": "식후 30분", "start_date": yesterday, "info": "졸음을 유발할 수 있습니다.", "food": "자몽 주스 피하세요."},
                {"name": "바이겔크림", "days": 1, "color": "#2ECC71", "time": "수시로 바름", "start_date": yesterday, "info": "외용으로만 사용하세요.", "food": "특이사항 없음"},
                {"name": "에스코텐정", "days": 14, "color": "#3D9DF3", "time": "식후 30분", "start_date": yesterday, "info": "위장 장애가 있을 수 있습니다.", "food": "자극적인 음식 금지"}
            ]
            pd.DataFrame(new_data).to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.medicines = load_data()
            st.rerun()

    # 사이드바 하단으로 버튼을 밀어내기 위한 공백 추가
    # 10번 정도 반복하면 버튼이 아래로 내려갑니다.
    for _ in range(10):
        st.sidebar.write("")

    st.divider()
    
    # 데이터 초기화 로직 (확인 절차 추가)
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

# 약 복용 기간 표시 (날짜별/약별로 개별 생성)
for drug in st.session_state.medicines:
    for i in range(int(drug['days'])):
        current_date = drug['start_date'] + datetime.timedelta(days=i)
        current_date_str = current_date.strftime("%Y-%m-%d")
        
        # 해당 날짜 + 해당 약의 이름 조합으로 체크 여부 확인
        h_key = (current_date_str, drug['name'])
        is_checked = st.session_state.check_history.get(h_key, False)
        
        # 체크 여부에 따른 개별 스타일 설정
        display_title = f"✅ {drug['name']}" if is_checked else drug['name']
        base_color = drug.get('color', '#3D9DF3')
        
        calendar_events.append({
            "title": display_title,
            "start": current_date_str,
            "end": current_date_str,
            "allDay": True,
            "display": "block",
            # 체크된 약만 색상 변경 
            "backgroundColor": "#D4EDDA" if is_checked else base_color,
            "borderColor": "#28A745" if is_checked else base_color,
            "textColor": "#000000" if is_checked else "#FFFFFF",
        })


# ==========================================
# 4. 상단: 상세 요약 (기존 5번 섹션을 위로 이동)
# ==========================================
st.title("💊 메디렌즈")
st.divider()

st.subheader("🔍 등록된 약 상세 요약 및 주의사항")

if not st.session_state.medicines:
    st.info("등록된 약 정보가 없습니다. 사이드바에서 처방전을 업로드해 주세요.")
else:
    # 약 정보를 상단에 가로로 배치하거나 리스트로 보여줌
    for drug in st.session_state.medicines:
        with st.expander(f"💡 {drug['name']} 상세 정보", expanded=True): # 기본적으로 열려있게 설정
            ec1, ec2 = st.columns(2)
            with ec1:
                st.markdown("##### 📌 복약 가이드")
                st.info(drug.get('info', '복용 시 주의사항 정보가 없습니다.'))
            with ec2:
                st.markdown("##### 🥗 음식과의 페어링")
                pairing_text = drug.get('food', '관련 음식 정보가 없습니다.')
                st.warning(f"**추천 및 주의 사항:**\n\n{pairing_text}")

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
                    if st.checkbox("", value=is_checked, key=f"cb_{view_date}_{drug['name']}"):
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