import streamlit as st
from supabase import create_client, Client
import datetime
import uuid
import json

# Supabase 초기화 함수
# secrets.toml 파일에 SUPABASE_URL과 SUPABASE_KEY가 있어야 합니다.
@st.cache_resource
def init_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase 연결 오류: secrets.toml 설정을 확인해주세요. ({e})")
        return None

# --- 사용자 관리 ---

def get_user_id():
    """사용자 식별을 위한 UUID 생성 및 조회 (URL 파라미터 기반 영속성 확보)"""
    # 1. URL 파라미터에서 user_id 확인
    query_params = st.query_params
    
    # query_params가 딕셔너리처럼 동작 (Streamlit 최신 버전)
    url_user_id = query_params.get("user_id", None)
    
    # 2. URL에 ID가 있으면 그걸 사용 (세션에도 동기화)
    if url_user_id:
        if 'user_id' not in st.session_state or st.session_state.user_id != url_user_id:
            st.session_state.user_id = url_user_id
        return url_user_id

    # 3. URL에 없으면 새로 생성 후 URL에 주입
    if 'user_id' not in st.session_state:
        new_id = str(uuid.uuid4())
        st.session_state.user_id = new_id
        # URL 파라미터 업데이트 (앱이 리런되며 주소창에 ?user_id=... 표시됨)
        st.query_params["user_id"] = new_id
        
    return st.session_state.user_id

# --- 약물 관리 (Medicines) ---

def get_medicines(user_id):
    """사용자의 모든 약물 정보 가져오기"""
    supabase = init_supabase()
    if not supabase: return []
    
    try:
        response = supabase.table("medicines").select("*").eq("user_id", user_id).execute()
        return response.data
    except Exception as e:
        st.error(f"데이터 조회 실패: {e}")
        return []

def add_medicine(user_id, drug_data):
    """약물 추가"""
    supabase = init_supabase()
    if not supabase: return False

    try:
        # 데이터 정리
        payload = {
            "user_id": user_id,
            "name": drug_data.get("name"),
            "days": int(drug_data.get("days", 3)),
            "start_date": drug_data.get("start_date").strftime("%Y-%m-%d"), # Date -> String
            "color": drug_data.get("color"),
            "time": drug_data.get("time"),
            "efficacy": drug_data.get("efficacy"),
            "usage": drug_data.get("usage"),
            "info": drug_data.get("info"),
            "food": drug_data.get("food")
        }
        supabase.table("medicines").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"약물 추가 실패: {e}")
        return False

def delete_medicine(user_id, drug_name):
    """약물 삭제"""
    supabase = init_supabase()
    if not supabase: return False
    
    try:
        supabase.table("medicines").delete().eq("user_id", user_id).eq("name", drug_name).execute()
        
        # 관련된 체크 기록도 삭제할지 여부는 정책 나름 (Foreign Key 설정 없으면 수동 삭제 권장)
        supabase.table("check_history").delete().eq("user_id", user_id).eq("drug_name", drug_name).execute()
        
        return True
    except Exception as e:
        st.error(f"삭제 실패: {e}")
        return False

# --- 복용 기록 (History) ---

def load_history(user_id):
    """체크리스트 기록 로드 -> 딕셔너리 형태로 변환 {(날짜, 약이름): True}"""
    supabase = init_supabase()
    if not supabase: return {}
    
    try:
        response = supabase.table("check_history").select("*").eq("user_id", user_id).execute()
        
        history_dict = {}
        for row in response.data:
            key = (row['date'], row['drug_name'])
            history_dict[key] = row['is_checked']
        return history_dict
    except Exception as e:
        # st.error(f"기록 조회 실패: {e}") # 로그 너무 많이 찍히면 시끄러우므로 생략 가능
        return {}

def toggle_check(user_id, date_str, drug_name, is_checked):
    """복용 체크 상태 토글 (Upsert: 있으면 수정, 없으면 추가)"""
    supabase = init_supabase()
    if not supabase: return
    
    try:
        # 유니크 제약조건(user_id, date, drug_name)이 걸려 있어야 upsert가 완벽히 동작
        # 여기서는 단순 delete -> insert 또는 select -> update 방식보다 upsert 권장
        payload = {
            "user_id": user_id,
            "date": date_str,
            "drug_name": drug_name,
            "is_checked": is_checked
        }
        # on_conflict 컬럼들을 기준으로 upsert 수행
        # Supabase 테이블 생성 시 (user_id, date, drug_name)을 Unique Key로 잡아줘야 함
        supabase.table("check_history").upsert(payload, on_conflict="user_id, date, drug_name").execute()
    except Exception as e:
        st.error(f"체크 저장 실패: {e}")

# --- 리포트 저장 (Report) ---

def save_report(user_id, report_data):
    """최신 리포트 저장 (덮어쓰기 또는 로그로 쌓기)"""
    supabase = init_supabase()
    if not supabase: return

    try:
        # 방법 A: 로그처럼 계속 쌓기
        supabase.table("reports").insert({
            "user_id": user_id,
            "report_json": report_data  # JSONB 컬럼 권장
        }).execute()
    except Exception as e:
        st.error(f"리포트 저장 실패: {e}")

def load_latest_report(user_id):
    """가장 최근 리포트 불러오기"""
    supabase = init_supabase()
    if not supabase: return None

    try:
        # created_at 내림차순 정렬 후 1개만 가져오기
        response = supabase.table("reports") \
            .select("report_json") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if response.data:
            return response.data[0]['report_json']
        return None
    except Exception as e:
        return None
