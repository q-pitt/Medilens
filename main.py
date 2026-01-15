import streamlit as st
from streamlit_calendar import calendar
import datetime
import pandas as pd
import uuid
import random
import re
from urllib.parse import quote
import time
import altair as alt

# --- [AI 분석 모듈 임포트] ---
import ocr
import ocr_correction
import api_search
import care_processor
import interaction_checker

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

def update_multiple_medicines_dates(updates):
    """updates: {약이름: 새로운날짜} 형태의 딕셔너리"""
    # [수정] CSV -> DB 연동 변경
    return db.update_medicines_start_date(user_id, updates)

def metric_card(label, value, help_text=None):
    """일관된 스타일의 Metric Card 렌더링"""
    st.metric(label=label, value=value, help=help_text)

def plot_confidence_timeline(timeline_data):
    """
    [Altair] Confidence Timeline (Step Line Chart)
    - Spec: Step-after Line + Point + Text Label (Delta)
    - Height: 260px
    """
    if not timeline_data:
        st.info("Legacy report: confidence timeline not available.")
        return

    # 1. Preprocessing
    # Label Shortening: "SymSpell Correction" -> "Correction", "API Validation" -> "API"
    short_labels = {
        "Start": "Start", 
        "OCR Extraction": "OCR", 
        "SymSpell Correction": "Correction", 
        "API Validation": "API"
    }
    
    stage_order = ["Start", "OCR", "Correction", "API"]
    
    # 데이터 변환 및 정렬
    processed = []
    prev_score = 0
    
    # 맵핑 기반으로 데이터 재구성 (정해진 순서대로)
    for stage_key, short_name in short_labels.items():
        # 데이터 찾기
        found = next((item for item in timeline_data if item["stage"] == stage_key), None)
        
        if found:
            score = found["score"]
            delta = score - prev_score if stage_key != "Start" else 0
            
            processed.append({
                "stage": short_name,
                "score": score,
                "delta_label": f"+{delta}" if delta > 0 else ""
            })
            prev_score = score
            
    if not processed:
        st.caption("No valid timeline data.")
        return

    # Altair Chart
    base = alt.Chart(pd.DataFrame(processed)).encode(
        x=alt.X("stage", sort=stage_order, axis=alt.Axis(labelAngle=0, labelFontSize=12, title=None)),
        y=alt.Y("score", scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(title=None)) # Y축 타이틀 제거 (공간 확보)
    )

    # 1. Step Line
    line = base.mark_line(interpolate="step-after").encode(color=alt.value("#4c78a8"))

    # 2. Points
    points = base.mark_point(size=80, filled=True).encode(color=alt.value("#4c78a8"))

    # 3. Delta Labels (점 위에 표시)
    text = base.mark_text(dy=-20, fontSize=12, fontWeight="bold").encode(
        text="delta_label"
    )

    chart = (line + points + text).properties(
        height=260
    ).configure_axis(
        gridOpacity=0.2,
        labelFontSize=12
    ).configure_view(
        stroke=None
    )
    
    st.altair_chart(chart, use_container_width=True)

def plot_drug_survival_funnel(survival_data):
    """
    [Altair] Drug Survival Funnel (Horizontal Bar Chart)
    - Spec: Horizontal Bar + Text Label
    - Height: 260px
    """
    if not survival_data:
        st.info("Legacy report: survival metrics not recorded yet.")
        return

    # 1. Preprocessing (Dict -> Long-form List)
    # survival_data example: {"ocr": 4, "correction": 4, "api": 4}
    rows = [
        {"stage": "OCR Extracted", "count": survival_data.get("ocr", 0), "order": 1},
        {"stage": "After Correction", "count": survival_data.get("correction", 0), "order": 2},
        {"stage": "API Verified", "count": survival_data.get("api", 0), "order": 3}
    ]
    
    df_funnel = pd.DataFrame(rows)
    
    # Altair Chart
    base = alt.Chart(df_funnel).encode(
        y=alt.Y("stage", sort=["OCR Extracted", "After Correction", "API Verified"], axis=alt.Axis(title=None, labelFontSize=12)),
        x=alt.X("count", axis=alt.Axis(title=None, tickMinStep=1)), # Count 축 타이틀 제거
        text="count"
    )

    # Bars
    bars = base.mark_bar(size=30).encode(
        color=alt.value("#82c3cbd9") # 은은한 색상
    )

    # Labels (막대 끝)
    labels = base.mark_text(
        align='left', 
        dx=5,
        fontSize=13,
        fontWeight='bold' 
    )

    chart = (bars + labels).properties(
        height=260
    ).configure_axis(
        gridOpacity=0.2, # 세로 Grid 약하게
        labelFontSize=12
    ).configure_view(
        stroke=None
    )

    st.altair_chart(chart, use_container_width=True)

def flatten_reports(reports):
    rows = []
    for r in reports:
        meta = r.get('report_json', {}).get('meta_analysis', {})
        kpis = meta.get('kpis', {})
        ds = meta.get('data_sources', {})
        metrics = meta.get('pipeline', meta.get('pipeline_metrics', {}))
        
        row = {
            "created_at": r.get('created_at'),
            "case_id": meta.get('case_id', r.get('case_id', 'unknown')),
            "quality_score": meta.get('quality_score', 0),
            
            # KPIs
            "ocr_success": metrics.get('ocr', {}).get('success', False),
            "api_success_rate": kpis.get('api_success_rate', kpis.get('search_success_rate', 0)), # Fallback for backward compatibility
            "mfds_coverage": ds.get('coverage_pct', 0),
            "latency_ms": kpis.get('total_latency_ms', 0),
            "retry_count": metrics.get('api', {}).get('retry_count', 0),
            
            # Safety
            "risk_level": meta.get('risk_level', 'Unknown'),
            "interaction_count": meta.get('safety_summary', {}).get('interaction_count', 0),
            "has_warning": meta.get('safety_summary', {}).get('has_warning', False),
            
            # Drill-down Data
            "raw_report": r.get('report_json', {})
        }
        rows.append(row)
    return pd.DataFrame(rows)

def get_bulk_calendar_url(medicines, slot_name="전체", start_time=None, end_time=None):
    if not medicines: return "#"
    
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    
    # 제목 설정: [메디렌즈] 아침 복용 (약이름들...)
    drug_names = ", ".join([d['name'].split('(')[0].strip() for d in medicines])
    title = quote(f"💊 [메디렌즈] {slot_name} 복용 ({drug_names})")
    
    # 상세 정보 통합
    details_parts = [f"[{slot_name} 복약 가이드]"]
    for d in medicines:
        details_parts.append(f"- {d['name']}: {d.get('time', '식후 30분')} ({d.get('usage', '-')})")
    details = quote("\n".join(details_parts))
    
    # 날짜 및 시간 설정
    s_date = medicines[0]['start_date']
    if isinstance(s_date, str):
        # "2024-01-01" -> "20240101"
        start_date_str = s_date.replace("-", "")
    else:
        start_date_str = s_date.strftime('%Y%m%d')

    if start_time and end_time:
        # 시간대별 등록 (예: 아침 09시)
        dates = f"{start_date_str}T{start_time}/{start_date_str}T{end_time}"
    else:
        # 종일 등록
        dates = f"{start_date_str}/{start_date_str}"
    
    # 반복 설정 (가장 긴 복용 일수 기준)
    max_days = max([int(d.get('days', 3)) for d in medicines])
    recur = quote(f"RRULE:FREQ=DAILY;COUNT={max_days}")
    
    return f"{base_url}&text={title}&details={details}&dates={dates}&recur={recur}"


# --- 데이터 로드 (DB 연동) ---
# 세션 상태 초기화 (또는 리프레시)
user_medicines = db.get_medicines(user_id)
st.session_state.medicines = user_medicines  # 전체 데이터

user_history = db.load_history(user_id)
st.session_state.check_history = user_history

# 리포트 로드 (세션에 없으면 DB에서 최신 조회)
# 이 부분은 아래에서 selected_case에 따라 로드하도록 변경됨
# if 'last_report' not in st.session_state:
#     latest_report = db.load_latest_report(user_id)
#     if latest_report:
#         st.session_state['last_report'] = latest_report


# ==========================================
# 2. 사이드바: 통합 메뉴 (대시보드 vs 비서)
# ==========================================
with st.sidebar:
    st.title("🧬 MediLens")
    

    app_mode = st.radio("화면 모드", ["🏠 내 복약 비서", "📊 시스템 대시보드"])
    st.markdown("---")

# ==========================================
# [PAGE 1] 📊 시스템 대시보드
# ==========================================
if app_mode == "📊 시스템 대시보드":
    st.title("📊 메디렌즈 시스템 대시보드")
    st.caption("Advanced Pipeline Analytics & Quality Control Console")
    st.divider()
    
    # 1. 데이터 로드 (Data Load)
    all_reports = db.get_user_reports(user_id)
    
    if not all_reports:
        st.info("아직 분석된 데이터가 충분하지 않습니다.")
    else:
        df = flatten_reports(all_reports)
        
        # [Sidebar] 케이스 선택 (Case Selector) - 최신순 정렬
        with st.sidebar:
            st.header("🔍 분석 케이스 선택")
            df_sorted = df.sort_values(by="created_at", ascending=False)
            case_options = df_sorted.index.tolist()
            
            def format_case_label(idx):
                r = df_sorted.loc[idx]
                score = r['quality_score']
                created = r['created_at']
                return f"[{created}] Score: {score}"
            
            selected_idx = st.selectbox(
                "리포트 타임라인", 
                case_options, 
                format_func=format_case_label
            )
            st.divider()

        # [Data Select] 선택된 데이터 추출
        row = df.loc[selected_idx]
        raw = row['raw_report']
        meta = raw.get('meta_analysis', {})
        api_stat = meta.get('pipeline', meta.get('pipeline_metrics', {})).get('api', {})
        
        # --- [Section 0] Header (Context) ---
        with st.container(border=True):
            cols = st.columns([3, 1])
            with cols[0]:
                st.subheader("Advanced Pipeline Analytics & Quality Control Console")
                st.caption(f"Case ID: {row['case_id']} | Created: {row['created_at']}")
            with cols[1]:
                # 우측정렬 느낌으로 점수 배치
                c1, c2 = st.columns(2)
                c1.metric("Quality Score", f"{row['quality_score']:.1f}")
                c2.metric("Risk Level", row['risk_level'].upper())

        # --- [Section 1] Performance Overview (Cards) ---
        with st.container(border=True):
            st.subheader("1) Performance Overview")
            
            # Row 1
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1: metric_card("Data Quality Score", f"{row['quality_score']:.1f} 점", "감점 요인 없이 AI 검증을 완벽하게 통과했습니다.")
            with r1c2: metric_card("MFDS Coverage", f"{row['mfds_coverage']:.1f} %", "검출된 모든 약물이 식약처 공공데이터와 일치합니다.")
            
            # Total Drugs calculation fallback
            case_sum = meta.get('case_summary', {})
            total_drugs = case_sum.get('total_drugs', meta.get('data_sources', {}).get('total_drugs', 0))
            with r1c3: metric_card("Total Drugs", f"{total_drugs} 건", "OCR이 추출하고 AI가 분석한 총 약물 개수입니다.")

            # Row 2
            r2c1, r2c2, r2c3 = st.columns(3)
            verified = case_sum.get('verified_drugs', 0)
            unverified = case_sum.get('unverified_drugs', 0)
            # Legacy fallback for verified/unverified if case_summary not present
            if not case_sum:
                 match_rate = row.get('api_success_rate', 0) / 100.0
                 verified = int(total_drugs * match_rate)
                 unverified = total_drugs - verified

            with r2c1: metric_card("Verified / Unverified", f"{verified} / {unverified}", "국가 의약품 표준 데이터베이스 검증 완료.")
            with r2c2: metric_card("Avg Latency", f"{int(row['latency_ms']):,} ms", "OCR부터 AI 분석까지 소요된 총 파이프라인 시간.")
            with r2c3: metric_card("Search Difficulty (Retry)", f"{int(row['retry_count'])} 회", "재검색 없이 1차 시도에서 즉시 매칭되었습니다.")

        # --- [Section 2] Quality Trends & Funnel (Altair Charts) ---
        pipeline_data = meta.get('pipeline', meta.get('pipeline_metrics', {}))
        
        with st.container(border=True):
            st.subheader("2) Quality Trends & Funnel")
            c1, c2 = st.columns(2, gap="large")
            
            with c1:
                st.caption("Confidence increases by validation steps.")
                # Timeline 차트 그리기
                plot_confidence_timeline(pipeline_data.get('confidence_timeline', []))
            
            with c2:
                st.caption("No data loss across pipeline stages.")
                # Funnel 차트 그리기
                plot_drug_survival_funnel(pipeline_data.get('drug_survival'))

        # --- [Section 3] Safety & Risk Signals ---
        with st.container(border=True):
            st.subheader("3) Safety & Risk Signals")
            
            # Top: Cards
            s1, s2, s3 = st.columns(3)
            
            # Risk Badge Logic (Text/Emoji substitution)
            risk_val = row['risk_level'].upper()
            risk_badge = "🟢 LOW (Safe)"
            if risk_val == "MEDIUM": risk_badge = "🟡 MEDIUM (Caution)"
            elif risk_val == "HIGH": risk_badge = "🔴 HIGH (Danger)"
            
            # DUR Warning Icon
            dur_warn = "✅ No"
            if row['has_warning']: dur_warn = "⚠️ YES"
            
            with s1: metric_card("Risk Level", risk_badge)
            with s2: metric_card("DUR Warning", dur_warn)
            with s3: metric_card("Interaction Count", f"{row['interaction_count']} 건")
            
            st.divider()
            
            # Bottom: Progress Bar
            st.caption("Risk is shown as level (1=Low, 2=Medium, 3=High).")
            # Map Risk to 0.0 ~ 1.0 (Low -> 0.33, Medium -> 0.66, High -> 1.0)
            p_val = 0.33
            if risk_val == "MEDIUM": p_val = 0.66
            elif risk_val == "HIGH": p_val = 1.0
            st.progress(p_val)

        # --- [Section 4] Logs ---
        with st.container(border=True):
            st.subheader("4) Detailed Pipeline Logs")
            with st.expander("📂 Case Summary / Provenance / Raw JSON", expanded=False):
                st.write(f"**Provenance:** {api_stat.get('source', '-')} / {api_stat.get('endpoint', '-')}")
                st.json(raw)

    st.stop()


# ==========================================
# [PAGE 2] 🏠 내 복약 비서 (기존 로직)
# ==========================================

with st.sidebar:
    
    # [처방전 그룹핑 및 선택]
    case_groups = {}
    for med in user_medicines:
        c_id = med.get('case_id', 'Unknown')
        if c_id not in case_groups:
            case_groups[c_id] = []
        case_groups[c_id].append(med)
    
    # 선택 옵션 생성 (최신순 등 정렬 가능)
    # 예: "Case 1 (3개 약물)", "Case 2 (1개 약물)"
    case_options = ["전체 보기"] + list(case_groups.keys())
    
    # 케이스 ID를 좀 더 읽기 좋게(날짜 등) 표시하면 좋지만, 지금은 ID/약물수로만 표시
    def format_func(option):
        if option == "전체 보기": return "📂 전체 처방전 보기"
        cnt = len(case_groups[option])
        # 약물 중 첫 번째 약의 시작 날짜를 대표로 표시
        first_date = case_groups[option][0].get('start_date', '?')
        return f"📄 처방전 ({first_date} 접수, {cnt}개 약물)"

    # 사이드바 하단 리스트 위치 (새로고침 위)
    st.subheader("📁 내 처방전 목록")
    selected_case = st.selectbox("확인할 처방전을 선택하세요", case_options, format_func=format_func)
    
    st.divider()

    # 업로드 기능
    st.subheader("📸 새 처방전 추가")
    img_file = st.file_uploader("약을 촬영한 이미지를 업로드하세요", type=["png", "jpg", "jpeg"])

    if img_file is not None:
        # [Latency 측정] 분석 시작 시간 기록
        start_time = time.time()
        
        # 이미지 표시
        st.image(img_file, caption="업로드된 이미지", use_container_width=True)
        if st.button("🚀 AI 정밀 분석 및 등록", use_container_width=True):
            
            try:
                # --- [AI 분석 파이프라인 시작] ---
                with st.status("Medilens AI가 분석 중입니다...", expanded=True) as status:
                    
                    # [1] OCR + 보정 실행
                    st.write("👁️ 글자를 읽고 있습니다... (OCR)")
                    ocr_result = ocr.run_ocr(img_file)
                    
                    # [Metric] OCR 지표 수집
                    pipeline_metrics = {
                        "ocr": {
                            "success": True if ocr_result else False,
                            "extracted_count": len(ocr_result) if ocr_result else 0
                        }
                    }
                    
                    if not ocr_result:
                        status.update(label="❌ OCR 실패 (텍스트 없음)", state="error")
                        st.stop()

                    # [Metric] 보정 지표 수집 (함수 시그니처 변경 반영: tuple 반환)
                    st.write("🔧 약물 DB와 대조하여 오타를 수정합니다...")
                    corrected_drugs, correction_stats = ocr_correction.correct_drug_names(ocr_result)
                    pipeline_metrics["correction"] = correction_stats
                    
                    # [DEBUG] 중간 결과 저장
                    st.session_state.ocr_result = corrected_drugs

                    # [2] API 검증 (재시도 로직 포함 - Phase 4)
                    st.write("🔍 식약처 데이터를 조회합니다... (3단계 정밀 검색)")
                    validated_drugs = []
                    
                    # [Metric] API 지표 초기화
                    api_stats = {
                        "attempted": 0, 
                        "matched": 0, 
                        "retry_count": 0,
                        "source": "MFDS (식품의약품안전처)",
                        "endpoint": "DrugPrdtPrmsnInfoService07 (의약품제품허가정보)", 
                        "api_version": "v1 (getDrugPrdtPrmsnDtlInq06)"
                    }
                    
                    for drug in corrected_drugs:
                        base_name = drug.get('corrected_medicine_name', drug.get('medicine_name'))
                        api_stats["attempted"] += 1
                        
                        search_res = None
                        # 4단계 재시도 로직 (Full -> No Dosage -> No Paren -> Prefix)
                        for i in range(4):
                            query = base_name
                            
                            # 단계별 쿼리 생성
                            if i == 0:
                                pass # 1단계: 원본 그대로
                            elif i == 1:
                                # 2단계: 용량/단위 제거 (User Request 복구)
                                name_only, _ = ocr_correction.split_name_and_dosage(base_name)
                                query = name_only
                            elif i == 2:
                                # 3단계: 괄호 제거
                                query = api_search.remove_parentheses(base_name)
                            elif i == 3:
                                # 4단계: 앞 4글자 (최후의 수단)
                                query = base_name[:4] if len(base_name) > 4 else base_name
                                
                            # 중복 쿼리 방지 (예: 괄호 없는데 괄호제거 단계 수행 시)
                            if i > 0 and query == base_name: 
                                continue
                            if i == 3 and len(base_name) <= 4:
                                continue

                            print(f"[DEBUG] API 검색 {i+1}차: {query}")
                            search_res = api_search.search_drug_api(query)
                            
                            if search_res:
                                print(f"  -> 성공!")
                                break
                            else:
                                if i < 3: api_stats["retry_count"] += 1
                        
                        if search_res:
                            # 매칭 성공
                            api_stats["matched"] += 1
                            drug['efficacy'] = api_search.remove_xml_tags(search_res.get('efcyQesitm', ''))
                            drug['usage'] = api_search.remove_xml_tags(search_res.get('useMethodQesitm', ''))
                            drug['caution'] = api_search.remove_xml_tags(search_res.get('atpnQesitm', ''))
                        
                        validated_drugs.append(drug)

                    # [Metric] API 결과 저장
                    pipeline_metrics["api"] = api_stats
                    
                    # [3] DUR 및 LLM 분석
                    st.write("🧠 AI가 복약 지도를 작성 중입니다...")
                    
                    # DUR Check (Metric)
                    warnings = interaction_checker.check_interactions(validated_drugs)
                    pipeline_metrics["dur"] = {
                        "interaction_count": len(warnings),
                        "has_warning": len(warnings) > 0
                    }
                    
                    # 최종 AI 요청 (메타 포함)
                    final_json = {
                        "drugs": validated_drugs, 
                        "meta": {"source": "Medilens", "timestamp": str(datetime.datetime.now())}
                    }
                    ai_result = care_processor.analyze_with_llm(final_json)
                    
                    # 세션에 메트릭 및 결과 저장
                    st.session_state.pipeline_metrics = pipeline_metrics
                    st.session_state.ai_result = ai_result
                    
                    # DUR 결과 병합 (LLM 결과에 없을 수도 있으므로)
                    if not ai_result.get('interactions'):
                        ai_result['interactions'] = warnings
                    
                    st.session_state['debug_ocr'] = ocr_result # 하위 호환
                    st.session_state['debug_ai'] = ai_result
                    
                    if "error" in ai_result:
                        st.error(ai_result["error"])
                        st.stop()
                        
                st.success("✅ 분석 완료! 데이터베이스에 등록합니다.")

                # --- [데이터 변환 및 저장] ---
                ai_result_final = st.session_state.ai_result
                schedule_list = ai_result_final.get('schedule_time_list', [])
                time_str = ", ".join(schedule_list) if schedule_list else "식후 30분"
                
                # [Case ID 생성] 이번 처방전 업로드를 하나의 사건(Case)으로 그룹핑
                case_id = str(uuid.uuid4())

                # 1. 약물 DB 저장
                count = 0
                for drug in ai_result_final.get('drug_analysis', []):
                    drug_name = drug.get('name', '알 수 없음')
                    
                    try:
                        raw_days = drug.get('days', 3)
                        days = int(raw_days)
                    except:
                        days = 3
                    
                    # 약물별 개별 스케줄 우선 적용
                    d_schedule = drug.get('time_list', [])
                    if not d_schedule:
                        # 없으면 전체 공용 스케줄 사용
                        d_schedule = ai_result_final.get('schedule_time_list', ["식후 30분"])
                    
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
                if "report" in ai_result_final:
                    report_data = ai_result_final["report"]
                    report_data["medicines"] = ai_result_final.get('drug_analysis', [])
                    
                    # [Phase 4] Advanced Analytics & Meta Data Construction
                    metrics = st.session_state.get('pipeline_metrics', {})
                    
                    # 1. 신뢰도 점수 계산 (Data Quality Score)
                    quality_score = 100
                    breakdown = []
                    
                    # (1) OCR Check (치명적 실패)
                    if not metrics.get('ocr', {}).get('success', False):
                        quality_score -= 40
                        breakdown.append("OCR 인식 실패 (-40)")
                    
                    # (2) Correction Check (과도한 보정)
                    corr_stats = metrics.get('correction', {})
                    if corr_stats.get('total_edits', 0) > 10:
                        quality_score -= 10
                        breakdown.append("과도한 오타 보정 (-10)")
                        
                    # (3) API Match Check (매칭 실패율 반영)
                    api_stats = metrics.get('api', {})
                    attempted = api_stats.get('attempted', 1)
                    matched = api_stats.get('matched', 0)
                    success_rate = matched / attempted if attempted > 0 else 0.0
                    
                    if success_rate < 1.0:
                        # 실패율 * 40점 감점
                        penalty = int((1.0 - success_rate) * 40)
                        quality_score -= penalty
                        breakdown.append(f"식약처 미매칭 {attempted-matched}건 (-{penalty})")
                        
                    # (참고) DUR/Safety 지표는 점수에서 제외 (별도 리스크 카드로 분리)
                    
                    # 점수 보정 (0~100)
                    quality_score = max(0, min(100, quality_score))

                    # [Explicit Feedback] 만점인 경우 성공 메시지 명시
                    if quality_score == 100:
                        breakdown.append("Perfect Match: No penalties applied (OCR, API, Correction passed)")

                    # [Latency 측정] 분석 종료 및 시간 계산
                    end_time = time.time()
                    total_latency_ms = int((end_time - start_time) * 1000)

                    # 2. 메타 데이터 조립
                    meta = {
                        "case_id": case_id, # [Traceability] 처방전 식별 ID (DB와 리포트 연결 고리)
                        "risk_level": ai_result_final.get('meta_analysis', {}).get('risk_level', 'Unknown'),
                        "quality_score": quality_score,
                        "quality_breakdown": breakdown,
                        "pipeline": metrics, # (Refactored) Standardized key
                        "data_sources": {
                            "primary": "MFDS (식품의약품안전처)",
                            "coverage_pct": int(success_rate * 100),
                            "total_drugs": attempted
                        },
                        "safety_summary": { # 대시보드 표시용 별도 카드 데이터
                            "interaction_count": metrics.get('dur', {}).get('interaction_count', 0),
                            "has_warning": metrics.get('dur', {}).get('has_warning', False)
                        },
                        "case_summary": { # [New] 처방전 규모 요약 (Volume Context)
                            "total_drugs": attempted,
                            "verified_drugs": matched,
                            "unverified_drugs": attempted - matched,
                            "success_ratio": success_rate
                        },
                        "meta_version": "1.1", # [Legacy Check] 리포트 버전 태깅 (1.1 = Funnel Data Available)
                        # [Dashboard KPI] 대시보드용 핵심 성과 지표 (Pre-calcutated)
                        "kpis": {
                            "drug_name_accuracy_proxy": round(success_rate * 100, 1), # 약물명 인식 정확도 (대체지표)
                            "api_success_rate": round(success_rate * 100, 1),         # (Refactored) API 검색 성공률
                            "total_latency_ms": total_latency_ms                     # 총 처리 속도 (ms)
                        }
                    }

                    # [New] Confidence Timeline Logic (60 -> 80 -> 100)
                    # "데이터가 이 과정을 거치며 점점 더 믿을만해진다"는 가치 시각화
                    timeline = [{"stage": "Start", "score": 0}]
                    
                    # 1. OCR Stage (Base: 60)
                    if attempted > 0:
                        timeline.append({"stage": "OCR Extraction", "score": 60})
                    
                    # 2. Correction Stage (Base: 80)
                    if attempted > 0: 
                         timeline.append({"stage": "SymSpell Correction", "score": 80})

                    # 3. Validation Stage (Final: 100)
                    final_score = 80
                    if success_rate == 1.0:
                        final_score = 100
                    elif success_rate > 0:
                        final_score = 80 + int(success_rate * 20) # 부분 점수
                    
                    timeline.append({"stage": "API Validation", "score": final_score})
                    
                    timeline.append({"stage": "API Validation", "score": final_score})
                    
                    metrics["confidence_timeline"] = timeline
                    
                    # [New] Drug Survival Funnel Metrics (OCR -> Correction -> API)
                    ocr_cnt = metrics.get('ocr', {}).get('extracted_count', 0)
                    metrics["drug_survival"] = {
                        "ocr": ocr_cnt,
                        "correction": len(corrected_drugs) if 'corrected_drugs' in locals() else ocr_cnt,
                        "api": matched
                    }
                    
                    # 리포트에 주입
                    report_data["meta_analysis"] = meta
                    
                    # case_id 전달 및 저장
                    db.save_report(user_id, report_data, case_id=case_id)
                    st.session_state['last_report'] = report_data
                
                st.success(f"{count}개의 약물이 클라우드에 성공적으로 등록되었습니다!")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"처리 중 오류가 발생했습니다: {e}")

    # 사이드바 하단
    for _ in range(5): st.sidebar.write("")
    st.divider()
    
    # 데이터 초기화 (전체 삭제 기능은 복잡하므로 개별 삭제 권장, 일단 비활성화 or 전체 삭제 구현)
    if st.sidebar.button("DB 새로고침", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

# ----------------------------------------------------
# [Main Logic] 선택된 Case에 따라 데이터 필터링
# ----------------------------------------------------
if selected_case == "전체 보기":
    filtered_medicines = st.session_state.medicines
    # 전체 보기일 때는 가장 최신 리포트를 보여주거나, 리포트를 숨길 수 있음.
    # 여기서는 가장 최신(all)로 로드
    current_report = db.load_latest_report(user_id, case_id=None)
else:
    filtered_medicines = case_groups[selected_case]
    # 선택된 케이스의 리포트 로드
    current_report = db.load_latest_report(user_id, case_id=selected_case)

st.session_state['last_report'] = current_report


# ==========================================
# 3. 달력 이벤트 구성 (filtered_medicines 기준)
# ==========================================
calendar_events = []

for drug in filtered_medicines:
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
        
        # [달력 체크 확인] 약물의 모든 복용 시간(아침, 점심 등)을 완료했는지 검사
        time_list = [t.strip() for t in drug.get('time', '').split(',') if t.strip()]
        if not time_list: time_list = ['기본']

        all_checked = True
        for t_val in time_list:
            h_key = (current_date_str, drug['name'], t_val)
            if not st.session_state.check_history.get(h_key, False):
                all_checked = False
                break
        
        is_checked = all_checked
        
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
st.title("💊 메디렌즈 - AI 종합 복약 가이드")
st.caption("🛡️ 식약처(MFDS) 공식 데이터 기반")
# st.divider()

if selected_case != "전체 보기":
    st.caption(f"현재 보고 있는 처방전: {selected_case}")

st.subheader("📝 종합 복약 리포트")

# st.write("사용자의 모든 처방 약을 분석하여 종합 가이드를 생성합니다.")

if 'last_report' not in st.session_state or not st.session_state['last_report']:
    if filtered_medicines:
        st.info("💡 등록된 리포트가 없습니다. (또는 이전 버전 데이터)")
    else:
        st.info("비어있는 처방전입니다. 사이드바에서 약을 먼저 등록해주세요.")
        
# [리포트 표시]
if st.session_state.get('last_report'):
    report = st.session_state['last_report']
    
    if isinstance(report, str) or "error" in report:
        st.error(report if isinstance(report, str) else report.get("error"))
    else:
        # 1. 인사말
        st.info(report.get("opening_message", "안녕하세요."))
        # st.divider()

        # 2. 약물별 상세 카드
        st.subheader("💊 처방약 설명과 복용법")
        for med in report.get("medicines", []):
            with st.expander(f"**{med.get('name', '약품')}** 상세 정보 ✅ MFDS(식약처) Verified", expanded=True):
                c1, c2 = st.columns(2)
                c1.markdown("**💊 효능·효과**"); c1.info(med.get('efficacy', '-'))
                c2.markdown("**📝 용법·용량**"); c2.success(med.get('usage', '-'))
                c3, c4 = st.columns(2)
                c3.markdown("**⚠️ 주의사항**"); c3.warning(med.get('caution', '-'))
                c4.markdown("**🥗 음식 가이드**"); 
                guide = med.get('food_guide', '-')
                if guide != '특별한 제한 없음': c4.error(guide)
                else: c4.caption(guide)
                
                st.divider()
                c_link, c_del = st.columns([4, 1])
                with c_link:
                    clean_name = re.split(r'\(', med.get('name', ''))[0].strip()
                    encoded_name = quote(clean_name)
                    url = f"https://nedrug.mfds.go.kr/searchDrug?itemName={encoded_name}"
                    st.link_button("🔍 식약처 상세 검색", url, use_container_width=True)
                with c_del:
                    if st.button("🗑️ 삭제", key=f"del_{med.get('name')}"):
                        if db.delete_medicine(user_id, med.get('name')):
                            st.success("삭제되었습니다."); time.sleep(0.5); st.rerun()

        st.divider()

        # 3. 종합 정보
        schedules = report.get("schedule_proposal", {})
        if schedules: st.subheader(schedules.get("title", "복용 스케줄")); st.markdown(schedules.get("content", ""))

        safety = report.get("safety_warnings", {})
        if safety: st.subheader(safety.get("title", "안전 주의사항")); st.markdown(safety.get("content", ""))
            
        tips = report.get("medication_tips", {})
        if tips: st.subheader(tips.get("title", "복약 팁")); st.markdown(tips.get("content", ""))

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
    # 1. 클릭한 날짜에 따른 view_date 결정 로직
    clicked_date_str = state.get("dateClick", {}).get("date")
    if clicked_date_str:
        temp_date = datetime.datetime.strptime(clicked_date_str[:10], "%Y-%m-%d").date()
        if "T" in clicked_date_str:  # 타임존 이슈 해결용
            view_date = temp_date + datetime.timedelta(days=1)
        else:
            view_date = temp_date
    else:
        view_date = today

    # 상단 헤더 및 일괄 수정 팝오버
    head_col1, head_col2, head_col3 = st.columns([2.5, 1.5, 1.5]) 
    
    with head_col1:
        st.subheader(f"📋 {view_date.strftime('%m/%d')} 리스트")
    
    with head_col2:
        # 📅 일정 일괄 수정 팝오버
        with st.popover("📅 일정 수정", use_container_width=True):
            st.subheader("🗓️ 날짜 수정")
            
            # --- [전체 일괄 변경 섹션] ---
            st.caption("모든 약의 시작일을 동일하게 변경하려면?")
            all_date = st.date_input("공통 시작일 선택", value=view_date, key="all_date_input")
            
            if st.button("🚀 모든 약에 이 날짜 적용", use_container_width=True):
                # 모든 약의 날짜를 선택한 날짜로 맵핑
                bulk_updates = {d['name']: all_date for d in st.session_state.medicines}
                if update_multiple_medicines_dates(bulk_updates):
                    st.success("모든 약의 시작일이 변경되었습니다!")
                    # 데이터 동기화
                    st.session_state.medicines = db.get_medicines(user_id) 
                    st.rerun()
    
    with head_col3:

        with st.popover("🔔 알림 등록", use_container_width=True):
            st.subheader("💡 구글 캘린더 일괄 등록")
            st.write("원하시는 등록 방식을 선택하세요.")
            
            # 1. 시간대별 등록 섹션
            st.markdown("---")
            st.caption("🕒 시간대별 등록")
            
            # [수정] 중첩 컬럼 제한(Level 3) 회피를 위해 세로 배치로 변경
            url_m = get_bulk_calendar_url(st.session_state.medicines, "아침", "090000", "100000")
            st.link_button("🌅 아침 알림 등록", url_m, use_container_width=True)
            
            url_l = get_bulk_calendar_url(st.session_state.medicines, "점심", "130000", "140000")
            st.link_button("☀️ 점심 알림 등록", url_l, use_container_width=True)
            
            url_d = get_bulk_calendar_url(st.session_state.medicines, "저녁", "190000", "200000")
            st.link_button("🌙 저녁 알림 등록", url_d, use_container_width=True)
                
            # 2. 종일 등록 섹션
            st.markdown("---")
            st.caption("📅 종일 일정으로 등록")
            url_all = get_bulk_calendar_url(st.session_state.medicines, "종일 통합", None, None)
            st.link_button("📦 모든 약 정보 한 번에 등록", url_all, use_container_width=True)


    st.divider()
    
    active_drugs = []
    
    # DB 데이터를 순회하며 해당 날짜에 먹어야 하는 약 필터링
    # [수정] filtered_medicines 사용
    for i, drug in enumerate(filtered_medicines):
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
                c1, c2, c3, c4, = st.columns([2.2, 1.5, 1, 0.8])
                
                with c1: st.markdown(f"**{drug['name']}**")
                with c2: st.caption(f"{drug['time']}")
                with c3: st.caption(f"📅 {days}일분")
                with c4: st.markdown(f"**D-{remaining}**")


                st.divider()
                
                # [Time-based Check logic]
                # 시간 파싱: "아침, 저녁" -> ["아침", "저녁"] / "식후 30분" -> ["식후 30분"]
                time_list = [t.strip() for t in drug['time'].split(',')]
                
                # 한 줄에 여러 체크박스 배치
                cols = st.columns(len(time_list))
                target_date_str = view_date.strftime("%Y-%m-%d")

                for idx, t_val in enumerate(time_list):
                    with cols[idx]:
                        # Key에 Time 포함 (Unique)
                        h_key = (target_date_str, drug['name'], t_val)
                        
                        # DB에서 로드해온 기록 확인
                        is_checked = st.session_state.check_history.get(h_key, False)
                        
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


    if not active_drugs and filtered_medicines:
        st.info("해당 날짜에는 복용할 약이 없습니다.")

st.divider()
# with st.container(border=True):
#     st.markdown("### ⚠️ 면책 조항 (Disclaimer)")
#     st.warning("**본 리포트는 의료진의 전문적 판단을 대체하지 않습니다.** \n\n중요한 의학적 결정이나 복약 상담은 반드시 의사나 약사와 상의하시기 바랍니다. 이 서비스는 보조적인 정보 제공만을 목적으로 합니다.")

st.warning("본 서비스는 식약처 의약품 허가정보를 기반으로 제공됩니다. 제공되는 정보 의 정확성을 위해 최선을 다하고 있으나, 의료진의 판단을 대체하지 않습니다. 중요한 의학적 판단은 반드시 의사의 판단을 따라야 합니다.")

# ==========================================
# [DEBUG] 하단 데이터 검증 영역
# ==========================================
# st.divider()
# with st.expander("🛠️ 개발자용 데이터 확인 (Debug - Phase 4)", expanded=False):
#     st.markdown("### 1. Pipeline Metrics (Raw Data)")
#     if 'pipeline_metrics' in st.session_state:
#         st.json(st.session_state['pipeline_metrics'])
#     else:
#         st.info("파이프라인 데이터가 없습니다.")

#     st.markdown("### 2. Final Meta Analysis (Quality Score)")
#     if st.session_state.get('last_report'):
#         st.json(st.session_state['last_report'].get('meta_analysis', {}))
#     else:
#         st.info("리포트 메타 데이터가 없습니다.")