import time
from playwright.sync_api import Page
from common_actions import parse_api_response, handle_popup

# ===========================================================
# ⚙️ [내부 액션 함수] jQuery UI 드롭다운 처리기 (개선됨)
# ===========================================================
def select_jquery_dropdown(page: Page, button_selector: str, option_text: str):
    """
    jQuery UI 드롭다운 선택 (개선판: 스크롤 및 부분 텍스트 매칭 강화)
    """
    try:
        # 1. 드롭다운 버튼 클릭
        btn = page.locator(button_selector)
        btn.wait_for(state="visible")
        btn.click()
        
        # 메뉴가 열릴 때까지 잠시 대기
        page.wait_for_timeout(500)
        
        # 2. 메뉴 ID 추론 (버튼 ID '-button' -> 메뉴 ID '-menu')
        menu_id = button_selector.replace("-button", "-menu")
        
        # 3. 옵션 찾기 (부분 텍스트 매칭)
        # <li> 태그 전체를 타겟팅하여 검색 범위를 넓힘
        # scroll_into_view_if_needed()를 사용하여 스크롤 문제 해결 시도
        option = page.locator(f"{menu_id} li").filter(has_text=option_text).last
        
        print(f"   [Dropdown] '{option_text}' 항목 찾는 중...")
        
        # 요소가 존재하면 스크롤 후 클릭
        if option.count() > 0:
            option.scroll_into_view_if_needed()
            option.click(force=True) # 가려져 있어도 강제 클릭 시도
            return True
        else:
            print(f"❌ [Dropdown] 메뉴 내에 '{option_text}' 텍스트가 없습니다.")
            return False

    except Exception as e:
        print(f"❌ 드롭다운 선택 실패 ({button_selector}): {e}")
        # 실패 시 스크린샷 저장 (디버깅용)
        # page.screenshot(path=f"error_dropdown_{option_text}.png")
        return False

# ===========================================================
# ⚙️ [내부 액션 함수] API & UI 설정
# ===========================================================
def api_get_datetime(page: Page, ip: str):
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=dateTime&mode=1"
    for _ in range(3):
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
    """NTP 설정 (체크박스 & 입력창)"""
    try:
        # 체크박스 (#time-sync)
        chk = page.locator("#time-sync")
        if use_sync != chk.is_checked():
            chk.click()
        
        if use_sync:
            page.locator("#time-server-list").select_option(value="0") # 0: 수동 설정
            
            # 입력창 (#time-server)
            input_el = page.locator("#time-server")
            input_el.fill(server_address)
            input_el.dispatch_event("change")

        return True
    except Exception as e:
        print(f"❌ NTP UI 설정 실패: {e}")
        return False

def ui_save(page: Page):
    """저장 버튼 클릭 및 팝업 처리"""
    try:
        btn = page.locator("#setup-apply")
        # 버튼 활성화 대기
        btn.wait_for(state="visible", timeout=2000)
        if not btn.is_disabled():
            btn.click()
            if handle_popup(page):
                # 저장 완료 후 버튼 비활성화 대기
                btn.wait_for(state="disabled", timeout=5000)
                return True
        return True # 이미 저장된 상태
    except:
        return False

# ===========================================================
# ⚙️ [통합 테스트 케이스] 날짜/시간 전체 테스트
# ===========================================================
def run_datetime_tests(page: Page, camera_ip: str):
    """
    날짜/시간 관련 테스트 모음 (NTP, Timezone, Format)
    """
    print("\n===============================================")
    print("🕒 [통합 테스트] 날짜/시간 (Date/Time) 시작")
    print("===============================================")
    
    # 메뉴 진입
    page.locator("#Page200_id").click() # 시스템
    page.locator("#Page202_id").click() # 날짜/시간
    page.wait_for_timeout(1000)

    # --- [Step 1] NTP 설정 테스트 ---
    TEST_SERVER = "pool.ntp.org"
    print(f"\n[Step 1] NTP 서버 설정 ({TEST_SERVER})...")
    
    if ui_set_ntp(page, True, TEST_SERVER):
        ui_save(page)
        data = api_get_datetime(page, camera_ip)
        
        if data and data.get("timeSync") == "on" and data.get("timeServer") == TEST_SERVER:
            print("✅ NTP 설정 검증 성공")
        else:
            print(f"❌ NTP 검증 실패 (API: {data})")
            return False, "NTP 검증 실패"
    else:
        return False, "NTP UI 조작 실패"

    # --- [Step 2] 시간대(Timezone) 테스트 ---
    # HTML Select Button ID: #timezone-button
    # UI 검색 키워드: "Dublin" (텍스트 매칭용)
    TARGET_TZ_KEYWORD = "Dublin"
    TARGET_TZ_API = "Dublin_Edinburgh_Lisbon_London"
    
    print(f"\n[Step 2] 시간대 변경 (키워드: {TARGET_TZ_KEYWORD})...")
    
    # jQuery Dropdown 선택
    if select_jquery_dropdown(page, "#timezone-button", TARGET_TZ_KEYWORD):
        ui_save(page)
        
        # API 값 조회
        data = api_get_datetime(page, camera_ip)
        current_tz = data.get("timeZone", "")
        
        if current_tz == TARGET_TZ_API:
            print(f"✅ 시간대 검증 성공 (API: {current_tz})")
        else:
            print(f"❌ 시간대 검증 실패 (예상: {TARGET_TZ_API}, 실제: {current_tz})")
            return False, f"시간대 불일치 ({current_tz})"
    else:
        return False, "시간대 드롭다운 선택 실패"
        
    # (복구) 서울로 원상 복귀
    print("[복구] 시간대 서울로 복귀...")
    select_jquery_dropdown(page, "#timezone-button", "Seoul")
    ui_save(page)

    # --- [Step 3] 포맷(Format) 테스트 ---
    # HTML: #date-format-button, #time-format-button
    
    # 날짜 포맷 변경 (MM/DD/YYYY)
    TARGET_DATE_TXT = "(MM/DD/YYYY)" # 텍스트 일부 포함으로 찾기
    print(f"\n[Step 3] 날짜 포맷 변경 ({TARGET_DATE_TXT})...")
    
    if select_jquery_dropdown(page, "#date-format-button", TARGET_DATE_TXT):
        ui_save(page)
        data = api_get_datetime(page, camera_ip)
        # API 리턴값은 "MM/DD/YYYY" 문자열 그대로 올 것으로 예상
        if data.get("dateFormat") == "MM/DD/YYYY":
            print("✅ 날짜 포맷 검증 성공")
        else:
            return False, f"날짜 포맷 실패 ({data.get('dateFormat')})"

    # 복구 (YYYY/MM/DD)
    select_jquery_dropdown(page, "#date-format-button", "(YYYY/MM/DD)")
    ui_save(page)

    return True, "날짜/시간 통합 테스트 완료"