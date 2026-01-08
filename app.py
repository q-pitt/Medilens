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
with st.sidebar:
    st.title("🧬 MediLens")
    st.subheader("📸 처방전 업로드")
    uploaded_file = st.file_uploader("이미지를 선택하세요", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file:
        st.image(uploaded_file, caption="업로드된 이미지", use_container_width=True)
        if st.button("분석 및 등록", use_container_width=True):
            # 분석 데이터 시뮬레이션 (image1.jpg 기준)
            yesterday = today - datetime.timedelta(days=1)
            new_data = [
                {"name": "세레온캡슐", "days": 14, "color": "#FF4B4B", "time": "식후 30분", "start_date": yesterday, "info": "졸음을 유발할 수 있습니다.", "food": "자몽 주스 피하세요."},
                {"name": "바이겔크림", "days": 1, "color": "#2ECC71", "time": "수시로 바름", "start_date": yesterday, "info": "외용으로만 사용하세요.", "food": "특이사항 없음"},
                {"name": "에스코텐정", "days": 14, "color": "#3D9DF3", "time": "식후 30분", "start_date": yesterday, "info": "위장 장애가 있을 수 있습니다.", "food": "자극적인 음식 금지"}
            ]
            pd.DataFrame(new_data).to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.medicines = load_data()
            st.rerun()

    st.divider()
    if st.sidebar.button("데이터 전체 초기화"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.session_state.medicines = []
        st.session_state.check_history = {}
        st.rerun()

# ==========================================
# 3. 달력 이벤트 구성 (기간 막대 + 완료 배경색)
# ==========================================
calendar_events = []

# (1) 약 복용 기간 표시 (막대기)
for drug in st.session_state.medicines:
    end_date = drug['start_date'] + datetime.timedelta(days=int(drug['days']))
    calendar_events.append({
        "title": drug['name'],
        "start": drug['start_date'].strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d"),
        "color": drug.get('color', '#3D9DF3')
    })

# (2) 모든 약 체크 시 배경색 변경 (Y/N 표시)
dates_in_history = set([date for (date, name) in st.session_state.check_history.keys()])
for d_str in dates_in_history:
    d_obj = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
    # 해당 날짜에 복용해야 할 약 목록
    required = [m['name'] for m in st.session_state.medicines if m['start_date'] <= d_obj <= (m['start_date'] + datetime.timedelta(days=int(m['days'])-1))]
    
    # 해당 날짜의 모든 약이 체크되었는지 확인
    if required and all(st.session_state.check_history.get((d_str, name), False) for name in required):
        calendar_events.append({
            "start": d_str,
            "display": "background",
            "color": "#D4EDDA"
        })

# ==========================================
# 4. 메인 화면: 5:5 분할 레이아웃
# ==========================================
st.title(" 메디렌즈")
st.divider()

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
    # 에러 방지: T15:00:00... 형태의 데이터를 처리하기 위해 앞 10자만 슬라이싱
    clicked_date_str = state.get("dateClick", {}).get("date")
    if clicked_date_str:
        temp_date = datetime.datetime.strptime(clicked_date_str[:10], "%Y-%m-%d").date()
        
        # [중요] 8일을 눌렀는데 7일이 나온다면, 시차 보정을 위해 하루를 더해줍니다.
        # 클릭한 데이터에 시간 정보(T...)가 포함되어 있다면 시차로 인해 하루 전날로 인식될 수 있습니다.
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
        
        # 선택한 날짜가 복용 범위 내에 있는 경우만 표시
        if drug_start <= view_date <= drug_end:
            active_drugs.append(drug)
            remaining = (drug_end - view_date).days
            
            with st.container(border=True):
                # [체크박스 // 이름 // 복용법 // 며칠분 // 디데이]
                c1, c2, c3, c4, c5 = st.columns([0.5, 2, 2, 1.5, 1])
                with c1:
                    h_key = (str(view_date), drug['name'])
                    is_checked = st.session_state.check_history.get(h_key, False)
                    # 체크박스 클릭 시 파일 저장
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

    if not active_drugs:
        if not st.session_state.medicines:
            st.info("사이드바에서 처방전을 업로드하여 약을 등록해 주세요.")
        else:
            st.info("해당 날짜에는 복용할 약이 없습니다.")

# ==========================================
# 5. 하단: 상세 요약 (스크롤 다운)
# ==========================================
st.markdown("---")
st.subheader("🔍 등록된 약 상세 요약 및 주의사항")

if not st.session_state.medicines:
    st.write("등록된 약 정보가 없습니다.")
else:
    for drug in st.session_state.medicines:
        # 약 이름별로 펼칠 수 있는 메뉴 생성
        with st.expander(f"💡 {drug['name']} 상세 정보"):
            # 왼쪽(주의사항)과 오른쪽(음식과의 페어링) 2칸으로 분할
            ec1, ec2 = st.columns(2)
            
            with ec1:
                st.markdown("##### 📌 복약 가이드")
                # 기존 info 컬럼 내용을 파란색 박스로 표시
                st.info(drug.get('info', '복용 시 주의사항 정보가 없습니다.'))
            
            with ec2:
                st.markdown("##### 🥗 음식과의 페어링")
                # 기존 food 컬럼 내용을 노란색 박스(warning)에 담아 표시
                # '함께 먹으면 좋은 음식' 칸은 삭제하고 여기에 통합되었습니다.
                pairing_text = drug.get('food', '관련 음식 정보가 없습니다.')
                st.warning(f"**추천 및 주의 사항:**\n\n{pairing_text}")