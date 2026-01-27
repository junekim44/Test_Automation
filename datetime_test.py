"""
개선된 날짜/시간 테스트 모듈
- config.py를 사용한 설정값 관리
- api_client.py를 사용한 통합 API 호출
- 중복 코드 제거 및 로직 개선
"""

import time
from typing import Optional, Tuple, Dict, Any
from playwright.sync_api import Page
from common_actions import handle_popup
from config import TIMEOUTS
from api_client import CameraApiClient

# ===========================================================
# ⚙️ [공통 헬퍼 함수] UI 네비게이션
# ===========================================================

def navigate_to_system_datetime(page: Page) -> bool:
    """
    시스템 > 날짜/시간 메뉴로 이동 (공통 네비게이션)
    
    Args:
        page: Playwright Page 객체
    
    Returns:
        성공 여부
    """
    try:
        page.locator("#Page200_id").click()  # 시스템
        page.locator("#Page202_id").click()  # 날짜/시간
        page.wait_for_timeout(TIMEOUTS.get("ui_navigation", 500))
        return True
    except Exception as e:
        print(f"❌ [Navigation] 메뉴 이동 실패: {e}")
        return False

# ===========================================================
# ⚙️ [내부 액션 함수] jQuery UI 드롭다운 처리기 (개선됨)
# ===========================================================

def select_jquery_dropdown(page: Page, button_selector: str, option_text: str) -> bool:
    """
    jQuery UI 드롭다운 선택 (개선판: 스크롤 및 부분 텍스트 매칭 강화)
    
    Args:
        page: Playwright Page 객체
        button_selector: 드롭다운 버튼 셀렉터 (예: "#timezone-button")
        option_text: 선택할 옵션 텍스트 (부분 일치 가능)
    
    Returns:
        성공 여부
    """
    try:
        # 1. 드롭다운 버튼 클릭
        btn = page.locator(button_selector)
        btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        btn.click()
        
        # 메뉴가 열릴 때까지 대기
        page.wait_for_timeout(TIMEOUTS.get("ui_navigation", 500))
        
        # 2. 메뉴 ID 추론 (버튼 ID '-button' -> 메뉴 ID '-menu')
        menu_id = button_selector.replace("-button", "-menu")
        
        # 3. 옵션 찾기 (부분 텍스트 매칭)
        option = page.locator(f"{menu_id} li").filter(has_text=option_text).last
        
        print(f"   [Dropdown] '{option_text}' 항목 찾는 중...")
        
        # 요소가 존재하면 스크롤 후 클릭
        if option.count() > 0:
            option.scroll_into_view_if_needed()
            option.click(force=True)  # 가려져 있어도 강제 클릭 시도
            # 선택 후 메뉴가 닫힐 때까지 대기
            page.wait_for_timeout(300)
            return True
        else:
            print(f"❌ [Dropdown] 메뉴 내에 '{option_text}' 텍스트가 없습니다.")
            return False

    except Exception as e:
        print(f"❌ 드롭다운 선택 실패 ({button_selector}): {e}")
        import traceback
        traceback.print_exc()
        return False

# ===========================================================
# ⚙️ [내부 액션 함수] API & UI 설정 (개선됨)
# ===========================================================

def api_get_datetime(api_client: CameraApiClient, max_retries: int = None) -> Optional[Dict[str, Any]]:
    """
    API로 날짜/시간 설정 조회 (개선된 버전 - 재시도 로직 포함)
    
    Args:
        api_client: CameraApiClient 인스턴스
        max_retries: 최대 재시도 횟수 (None이면 TIMEOUTS 사용)
    
    Returns:
        날짜/시간 설정 딕셔너리 또는 None
    """
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    
    for attempt in range(max_retries):
        try:
            data = api_client.get_datetime()
            
            if data:
                return data
            else:
                if attempt < max_retries - 1:
                    print(f"⚠️ [API] 날짜/시간 조회 실패 (시도 {attempt + 1}/{max_retries}). 재시도...")
                    time.sleep(TIMEOUTS.get("retry_delay", 2))
                else:
                    print("❌ [API] 날짜/시간 조회 최종 실패")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ [API] 날짜/시간 조회 에러 (시도 {attempt + 1}/{max_retries}): {e}")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
            else:
                print(f"❌ [API] 날짜/시간 조회 최종 에러: {e}")
    
    return None

def verify_datetime_value(api_client: CameraApiClient, field: str, expected_value: str,
                         max_retries: int = None, timeout: float = None) -> bool:
    """
    날짜/시간 설정 값 검증 (재시도 로직 포함)
    
    Args:
        api_client: CameraApiClient 인스턴스
        field: 검증할 필드명 (예: "timeSync", "timeZone", "dateFormat")
        expected_value: 기대하는 값
        max_retries: 최대 재시도 횟수
        timeout: 전체 타임아웃 (초)
    
    Returns:
        검증 성공 여부
    """
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    if timeout is None:
        timeout = TIMEOUTS.get("api_request", 10) * max_retries
    
    start_time = time.time()
    
    for attempt in range(max_retries):
        # 타임아웃 체크
        if time.time() - start_time > timeout:
            print(f"❌ [Verify] 타임아웃 ({timeout}초 초과)")
            return False
        
        data = api_get_datetime(api_client, max_retries=1)
        
        if data:
            current_value = data.get(field, "")
            if current_value == expected_value:
                print(f"✅ [Verify] {field} 검증 성공: '{expected_value}'")
                return True
            else:
                if attempt < max_retries - 1:
                    wait_time = TIMEOUTS.get("retry_delay", 2)
                    print(f"⚠️ [Verify] {field} 불일치 (시도 {attempt + 1}/{max_retries}). "
                          f"기대: '{expected_value}', 실제: '{current_value}'. {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ [Verify] {field} 최종 실패. 기대: '{expected_value}', 실제: '{current_value}'")
        else:
            if attempt < max_retries - 1:
                time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    return False

def ui_set_ntp(page: Page, use_sync: bool, server_address: str = "") -> bool:
    """
    NTP 설정 (체크박스 & 입력창) - 개선된 버전
    
    Args:
        page: Playwright Page 객체
        use_sync: NTP 동기화 사용 여부
        server_address: NTP 서버 주소 (use_sync가 True일 때 필수)
    
    Returns:
        성공 여부
    """
    try:
        # 체크박스 (#time-sync)
        chk = page.locator("#time-sync")
        chk.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        if use_sync != chk.is_checked():
            chk.click()
            page.wait_for_timeout(300)  # 상태 변경 대기
        
        if use_sync:
            if not server_address:
                print("❌ [NTP] 서버 주소가 필요합니다.")
                return False
            
            # 서버 목록 선택 (0: 수동 설정)
            server_list = page.locator("#time-server-list")
            server_list.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
            server_list.select_option(value="0")
            page.wait_for_timeout(300)
            
            # 입력창 (#time-server)
            input_el = page.locator("#time-server")
            input_el.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
            input_el.fill(server_address)
            input_el.dispatch_event("change")
            page.wait_for_timeout(300)

        return True
    except Exception as e:
        print(f"❌ [NTP] UI 설정 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def ui_save(page: Page) -> bool:
    """
    저장 버튼 클릭 및 팝업 처리 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
    
    Returns:
        성공 여부
    """
    try:
        btn = page.locator("#setup-apply")
        btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        if not btn.is_disabled():
            btn.click()
            if handle_popup(page, timeout=TIMEOUTS.get("popup", 5000)):
                # 저장 완료 후 버튼 비활성화 대기
                try:
                    btn.wait_for(state="disabled", timeout=TIMEOUTS.get("popup", 5000))
                except:
                    pass  # 비활성화 안되어도 저장은 완료될 수 있음
                return True
            else:
                print("⚠️ [Save] 팝업이 나타나지 않았습니다.")
                return False
        else:
            # 이미 저장된 상태
            print("[Save] 버튼이 비활성화되어 있습니다 (이미 저장됨).")
            return True
    except Exception as e:
        print(f"❌ [Save] 저장 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

# ===========================================================
# ⚙️ [통합 테스트 케이스] 날짜/시간 전체 테스트
# ===========================================================
def run_datetime_tests(page: Page, api_client: CameraApiClient) -> Tuple[bool, str]:
    """
    날짜/시간 관련 테스트 모음 (NTP, Timezone, Format)
    """
    print("\n===============================================")
    print("🕒 [통합 테스트] 날짜/시간 (Date/Time) 시작")
    print("===============================================")
    
    # 메뉴 진입
    if not navigate_to_system_datetime(page):
        return False, "메뉴 진입 실패"

    # --- [Step 1] NTP 설정 테스트 ---
    TEST_SERVER = "pool.ntp.org"
    print(f"\n[Step 1] NTP 서버 설정 ({TEST_SERVER})...")
    
    if not ui_set_ntp(page, True, TEST_SERVER):
        return False, "NTP UI 조작 실패"
    
    if not ui_save(page):
        return False, "NTP 설정 저장 실패"
    
    # 변경 반영 대기
    time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    # NTP 검증 (재시도 로직 포함)
    if not verify_datetime_value(api_client, "timeSync", "on", max_retries=3):
        return False, "NTP timeSync 검증 실패"
    
    if not verify_datetime_value(api_client, "timeServer", TEST_SERVER, max_retries=3):
        return False, "NTP timeServer 검증 실패"
    
    print("✅ NTP 설정 검증 성공")

    # --- [Step 2] 시간대(Timezone) 테스트 ---
    # HTML Select Button ID: #timezone-button
    # UI 검색 키워드: "Dublin" (텍스트 매칭용)
    TARGET_TZ_KEYWORD = "Dublin"
    TARGET_TZ_API = "Dublin_Edinburgh_Lisbon_London"
    
    print(f"\n[Step 2] 시간대 변경 (키워드: {TARGET_TZ_KEYWORD})...")
    
    # jQuery Dropdown 선택
    if not select_jquery_dropdown(page, "#timezone-button", TARGET_TZ_KEYWORD):
        return False, "시간대 드롭다운 선택 실패"
    
    if not ui_save(page):
        return False, "시간대 설정 저장 실패"
    
    # 변경 반영 대기
    time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    # 시간대 검증 (재시도 로직 포함)
    if not verify_datetime_value(api_client, "timeZone", TARGET_TZ_API, max_retries=5):
        return False, f"시간대 검증 실패 (기대: {TARGET_TZ_API})"
    
    # (복구) 서울로 원상 복귀
    print("\n[복구] 시간대 서울로 복귀...")
    if select_jquery_dropdown(page, "#timezone-button", "Seoul"):
        ui_save(page)
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        # 복구 검증은 선택사항 (실패해도 계속 진행)
        verify_datetime_value(api_client, "timeZone", "Asia_Seoul", max_retries=3)

    # --- [Step 3] 포맷(Format) 테스트 ---
    # HTML: #date-format-button, #time-format-button
    
    # 날짜 포맷 변경 (MM/DD/YYYY)
    TARGET_DATE_TXT = "(MM/DD/YYYY)" # 텍스트 일부 포함으로 찾기
    print(f"\n[Step 3] 날짜 포맷 변경 ({TARGET_DATE_TXT})...")
    
    TARGET_DATE_API = "MM/DD/YYYY"
    
    if not select_jquery_dropdown(page, "#date-format-button", TARGET_DATE_TXT):
        return False, "날짜 포맷 드롭다운 선택 실패"
    
    if not ui_save(page):
        return False, "날짜 포맷 설정 저장 실패"
    
    # 변경 반영 대기
    time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    # 날짜 포맷 검증 (재시도 로직 포함)
    if not verify_datetime_value(api_client, "dateFormat", TARGET_DATE_API, max_retries=5):
        return False, f"날짜 포맷 검증 실패 (기대: {TARGET_DATE_API})"

    # 복구 (YYYY/MM/DD)
    print("\n[복구] 날짜 포맷 YYYY/MM/DD로 복귀...")
    if select_jquery_dropdown(page, "#date-format-button", "(YYYY/MM/DD)"):
        ui_save(page)
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        # 복구 검증은 선택사항
        verify_datetime_value(api_client, "dateFormat", "YYYY/MM/DD", max_retries=3)

    print("\n" + "="*60)
    print("✅ 날짜/시간 통합 테스트 완료")
    print("="*60)
    return True, "날짜/시간 통합 테스트 완료"