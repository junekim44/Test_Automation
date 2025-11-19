import time
from playwright.sync_api import Page
from common_actions import parse_api_response, handle_popup

# ===========================================================
# ⚙️ [내부 액션 함수] 날짜/시간 전용
# ===========================================================

def api_get_datetime(page: Page, ip: str):
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=dateTime&mode=1"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response_text = page.evaluate("""async (url) => {
                try {
                    const response = await fetch(url);
                    if (!response.ok) return `Error: ${response.status}`;
                    return await response.text();
                } catch (e) { return `Error: ${e.message}`; }
            }""", api_url)

            if "Error: 401" in response_text:
                page.reload()
                page.wait_for_selector("#Page200_id", timeout=15000)
                time.sleep(2)
                continue

            if response_text and not response_text.startswith("Error"):
                return parse_api_response(response_text)
        except:
            time.sleep(2)
    return None

def ui_set_ntp(page: Page, use_sync: bool, server_address: str):
    # ⚠️ [확인 필요] 아래 ID들이 실제와 맞는지 F12로 확인 후 수정하세요!
    MENU_DATE_TIME = "#Page202_id"
    CHECKBOX_SYNC = "#time-sync"      # 예: id="timeSync", id="auto-sync" 등 확인
    INPUT_SERVER = "#time-server"     # 예: id="timeServer", id="ntp-server" 등 확인
    BTN_SAVE = "#setup-apply"

    try:
        page.locator("#Page200_id").click()
        page.locator(MENU_DATE_TIME).click()
        page.wait_for_timeout(500)
        
        # 체크박스 상태 동기화
        chk = page.locator(CHECKBOX_SYNC)
        if use_sync != chk.is_checked():
            chk.click()
        
        # 서버 주소 입력
        if use_sync:
            srv = page.locator(INPUT_SERVER)
            srv.fill(server_address)
            srv.dispatch_event("change")

        page.locator(BTN_SAVE).click()
        handle_popup(page)
        return True
    except Exception as e:
        print(f"UI NTP 설정 실패: {e}")
        return False

def ui_set_timezone(page: Page, timezone_label: str):
    # ⚠️ [확인 필요]
    MENU_DATE_TIME = "#Page202_id"
    SELECT_TIMEZONE = "#time-zone"    # 예: id="timeZone", name="timeZone" 등
    BTN_SAVE = "#setup-apply"

    try:
        page.locator("#Page200_id").click()
        page.locator(MENU_DATE_TIME).click()
        page.wait_for_timeout(500)
        
        page.locator(SELECT_TIMEZONE).select_option(label=timezone_label)
        page.locator(BTN_SAVE).click()
        handle_popup(page)
        return True
    except Exception as e:
        print(f"UI 시간대 설정 실패: {e}")
        return False

def ui_set_datetime_format(page: Page, date_fmt: str, time_fmt: str):
    # ⚠️ [확인 필요]
    MENU_DATE_TIME = "#Page202_id"
    SELECT_DATE_FMT = "#date-format"  # 예: id="dateFormat"
    SELECT_TIME_FMT = "#time-format"  # 예: id="timeFormat"
    BTN_SAVE = "#setup-apply"

    try:
        page.locator("#Page200_id").click()
        page.locator(MENU_DATE_TIME).click()
        page.wait_for_timeout(500)
        
        page.locator(SELECT_DATE_FMT).select_option(label=date_fmt)
        page.locator(SELECT_TIME_FMT).select_option(label=time_fmt)
        
        page.locator(BTN_SAVE).click()
        handle_popup(page)
        return True
    except Exception as e:
        print(f"UI 포맷 설정 실패: {e}")
        return False

# ===========================================================
# ⚙️ [테스트 케이스]
# ===========================================================

def run_ntp_test(page: Page, camera_ip: str):
    TEST_SERVER = "pool.ntp.org"
    print(f"\n--- [TC 4-1] NTP 설정 테스트 ({TEST_SERVER}) ---")
    
    if not ui_set_ntp(page, True, TEST_SERVER):
        return False, "UI 설정 실패"
    
    data = api_get_datetime(page, camera_ip)
    if not data: return False, "API 조회 실패"
    
    # 검증
    real_sync = data.get("timeSync")
    real_server = data.get("timeServer")
    
    if real_sync != "on": return False, f"동기화 켜짐 실패 (값: {real_sync})"
    if real_server != TEST_SERVER: return False, f"서버주소 불일치 (값: {real_server})"
        
    print("✅ NTP 설정 성공")
    return True, "NTP 설정 성공"

def run_timezone_test(page: Page, camera_ip: str):
    print("\n--- [TC 4-2] 시간대 변경 테스트 ---")
    # ⚠️ 실제 드롭다운 텍스트와 정확히 일치해야 함
    ZONES = [
        ("(GMT+09:00) Seoul", "Seoul"),
        ("(GMT+00:00) Dublin, Edinburgh, Lisbon, London", "Dublin_Edinburgh_Lisbon_London")
    ]
    
    for label, api_val in ZONES:
        print(f"[진행] 시간대 변경 -> {label}")
        if not ui_set_timezone(page, label): return False, f"UI 변경 실패({label})"
        
        data = api_get_datetime(page, camera_ip)
        if not data: return False, "API 조회 실패"
        
        if data.get("timeZone") != api_val: 
            return False, f"API 불일치 (기대: {api_val}, 실제: {data.get('timeZone')})"
        print(f"✅ {label} 검증 완료")
        
    # 복구
    ui_set_timezone(page, "(GMT+09:00) Seoul")
    return True, "시간대 테스트 성공"

def run_format_test(page: Page, camera_ip: str):
    print("\n--- [TC 4-3] 포맷 변경 테스트 ---")
    # ⚠️ 실제 드롭다운 옵션 텍스트 확인 필요
    UI_DATE_TARGET = "MM/DD/YYYY"
    UI_TIME_TARGET = "12 Hour"  # 또는 "12 시간" 등 실제 텍스트 확인
    
    if not ui_set_datetime_format(page, UI_DATE_TARGET, UI_TIME_TARGET):
        return False, "UI 변경 실패"
        
    data = api_get_datetime(page, camera_ip)
    if not data: return False, "API 조회 실패"
    
    real_date = data.get("dateFormat")
    real_time = data.get("timeFormat", "")
    
    if real_date != "MM/DD/YYYY": return False, f"날짜 포맷 불일치 ({real_date})"
    if "PP" not in real_time: return False, f"시간 포맷 불일치 ({real_time})" # 12H는 AM/PM(PP) 포함
    
    print("✅ 포맷 변경 검증 완료")
    
    # 복구
    ui_set_datetime_format(page, "YYYY/MM/DD", "24 Hour") # 실제 텍스트 확인
    return True, "포맷 테스트 성공"