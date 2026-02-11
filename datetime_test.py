"""
날짜/시간 테스트 모듈
- NTP 서버 설정 테스트
- Timezone 변경 테스트
- Date/Time Format 테스트
- 간결한 출력 및 명확한 진행 상황 표시
"""

import time
from typing import Optional, Tuple, Dict, Any
from playwright.sync_api import Page
from common_actions import handle_popup
from config import TIMEOUTS
from api_client import CameraApiClient

# ===========================================================
# 🎨 출력 헬퍼 함수
# ===========================================================

def print_step(current: int, total: int, message: str):
    """단계별 진행 상황 출력"""
    print(f"\n[{current}/{total}] {message}")

def print_action(message: str):
    """액션 진행 중 메시지"""
    print(f"   → {message}")

def print_success(message: str):
    """성공 메시지"""
    print(f"   ✅ {message}")

def print_warning(message: str):
    """경고 메시지"""
    print(f"   ⚠️  {message}")

def print_error(message: str):
    """에러 메시지"""
    print(f"   ❌ {message}")

# ===========================================================
# ⚙️ [공통 헬퍼 함수] UI 네비게이션
# ===========================================================

def navigate_to_system_datetime(page: Page) -> bool:
    """시스템 > 날짜/시간 메뉴로 이동"""
    try:
        page.locator("#Page200_id").click()
        page.locator("#Page202_id").click()
        page.wait_for_timeout(TIMEOUTS.get("ui_navigation", 500))
        return True
    except Exception as e:
        print_error(f"메뉴 이동 실패: {e}")
        return False

# ===========================================================
# ⚙️ [내부 액션 함수] jQuery UI 드롭다운 처리기 (개선됨)
# ===========================================================

def select_jquery_dropdown(page: Page, button_selector: str, option_text: str, silent: bool = False) -> bool:
    """jQuery UI 드롭다운 선택 (스크롤 및 부분 텍스트 매칭)"""
    try:
        btn = page.locator(button_selector)
        btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        btn.click()
        
        page.wait_for_timeout(TIMEOUTS.get("ui_navigation", 500))
        
        menu_id = button_selector.replace("-button", "-menu")
        option = page.locator(f"{menu_id} li").filter(has_text=option_text).last
        
        if option.count() > 0:
            option.scroll_into_view_if_needed()
            option.click(force=True)
            page.wait_for_timeout(300)
            if not silent:
                print_success(f"선택: {option_text}")
            return True
        else:
            if not silent:
                print_error(f"항목 없음: {option_text}")
            return False

    except Exception as e:
        if not silent:
            print_error(f"드롭다운 선택 실패: {e}")
        return False

# ===========================================================
# ⚙️ [내부 액션 함수] API & UI 설정 (개선됨)
# ===========================================================

def api_get_datetime(api_client: CameraApiClient, max_retries: int = None, silent: bool = False) -> Optional[Dict[str, Any]]:
    """API로 날짜/시간 설정 조회 (재시도 포함)"""
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    
    for attempt in range(max_retries):
        try:
            data = api_client.get_datetime()
            if data:
                return data
            
            if attempt < max_retries - 1:
                if not silent:
                    print_warning(f"날짜/시간 조회 실패 ({attempt + 1}/{max_retries}), 재시도 중...")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
        except Exception as e:
            if attempt < max_retries - 1:
                if not silent:
                    print_warning(f"날짜/시간 조회 에러 ({attempt + 1}/{max_retries}): {e}")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    if not silent:
        print_error("날짜/시간 조회 최종 실패")
    return None

def verify_datetime_value(api_client: CameraApiClient, field: str, expected_value: str,
                         max_retries: int = None, timeout: float = None, silent: bool = False) -> bool:
    """날짜/시간 설정 값 검증 (재시도 포함)"""
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    if timeout is None:
        timeout = TIMEOUTS.get("api_request", 10) * max_retries
    
    start_time = time.time()
    
    if not silent:
        print_action(f"검증 중: {field}='{expected_value}'")
    
    for attempt in range(max_retries):
        if time.time() - start_time > timeout:
            if not silent:
                print_error(f"타임아웃 ({timeout}초 초과)")
            return False
        
        data = api_get_datetime(api_client, max_retries=1, silent=True)
        
        if data:
            current_value = data.get(field, "")
            if current_value == expected_value:
                if not silent:
                    print_success("검증 성공")
                return True
            
            if attempt < max_retries - 1:
                if not silent:
                    print_warning(f"불일치 (실제: '{current_value}'), 재시도 {attempt + 1}/{max_retries}")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
            else:
                if not silent:
                    print_error(f"검증 실패: 기대='{expected_value}', 실제='{current_value}'")
        else:
            if attempt < max_retries - 1:
                time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    return False

def ui_set_ntp(page: Page, use_sync: bool, server_address: str = "") -> bool:
    """NTP 설정 (체크박스 & 입력창)"""
    try:
        chk = page.locator("#time-sync")
        chk.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        if use_sync != chk.is_checked():
            chk.click()
            page.wait_for_timeout(300)
        
        if use_sync:
            if not server_address:
                print_error("NTP 서버 주소 필요")
                return False
            
            server_list = page.locator("#time-server-list")
            server_list.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
            server_list.select_option(value="0")
            page.wait_for_timeout(300)
            
            input_el = page.locator("#time-server")
            input_el.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
            input_el.fill(server_address)
            input_el.dispatch_event("change")
            page.wait_for_timeout(300)
            
            print_success(f"NTP 서버: {server_address}")

        return True
    except Exception as e:
        print_error(f"NTP 설정 실패: {e}")
        return False

def ui_save(page: Page, silent: bool = False) -> bool:
    """저장 버튼 클릭 및 팝업 처리"""
    try:
        btn = page.locator("#setup-apply")
        btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        if not btn.is_disabled():
            btn.click()
            if handle_popup(page, timeout=TIMEOUTS.get("popup", 5000)):
                try:
                    btn.wait_for(state="disabled", timeout=TIMEOUTS.get("popup", 5000))
                except:
                    pass
                if not silent:
                    print_success("저장 완료")
                return True
            else:
                if not silent:
                    print_warning("팝업 없음")
                return False
        else:
            if not silent:
                print_success("이미 저장됨")
            return True
    except Exception as e:
        if not silent:
            print_error(f"저장 실패: {e}")
        return False

# ===========================================================
# ⚙️ [통합 테스트 케이스] 날짜/시간 전체 테스트
# ===========================================================
def run_datetime_tests(page: Page, api_client: CameraApiClient) -> Tuple[bool, str]:
    """날짜/시간 테스트 (NTP, Timezone, Format)"""
    total_steps = 3
    
    # 메뉴 진입
    if not navigate_to_system_datetime(page):
        return False, "메뉴 진입 실패"

    try:
        # Step 1: NTP 설정
        TEST_SERVER = "pool.ntp.org"
        print_step(1, total_steps, f"NTP 서버 설정 ({TEST_SERVER})")
        
        print_action("NTP 설정 중...")
        if not ui_set_ntp(page, True, TEST_SERVER):
            raise Exception("NTP UI 조작 실패")
        
        if not ui_save(page):
            raise Exception("저장 실패")
        
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # NTP 검증
        if not verify_datetime_value(api_client, "timeSync", "on", max_retries=3):
            raise Exception("NTP timeSync 검증 실패")
        
        if not verify_datetime_value(api_client, "timeServer", TEST_SERVER, max_retries=3):
            raise Exception("NTP timeServer 검증 실패")

        # Step 2: Timezone 변경
        TARGET_TZ_KEYWORD = "Dublin"
        TARGET_TZ_API = "Dublin_Edinburgh_Lisbon_London"
        
        print_step(2, total_steps, f"Timezone 변경 ({TARGET_TZ_KEYWORD})")
        
        print_action("Timezone 선택 중...")
        if not select_jquery_dropdown(page, "#timezone-button", TARGET_TZ_KEYWORD):
            raise Exception("Timezone 선택 실패")
        
        if not ui_save(page):
            raise Exception("저장 실패")
        
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        if not verify_datetime_value(api_client, "timeZone", TARGET_TZ_API, max_retries=5):
            raise Exception("Timezone 검증 실패")
        
        # Timezone 복구
        print(f"\n{'='*60}")
        print("🔄 Timezone 복구 (Seoul)")
        print(f"{'='*60}")
        if select_jquery_dropdown(page, "#timezone-button", "Seoul", silent=True):
            ui_save(page, silent=True)
            time.sleep(TIMEOUTS.get("retry_delay", 2))
            verify_datetime_value(api_client, "timeZone", "Asia_Seoul", max_retries=3, silent=True)
            print_success("복구 완료")

        # Step 3: Date Format 변경
        TARGET_DATE_TXT = "(MM/DD/YYYY)"
        TARGET_DATE_API = "MM/DD/YYYY"
        
        print_step(3, total_steps, f"Date Format 변경 ({TARGET_DATE_API})")
        
        print_action("Date Format 선택 중...")
        if not select_jquery_dropdown(page, "#date-format-button", TARGET_DATE_TXT):
            raise Exception("Date Format 선택 실패")
        
        if not ui_save(page):
            raise Exception("저장 실패")
        
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        if not verify_datetime_value(api_client, "dateFormat", TARGET_DATE_API, max_retries=5):
            raise Exception("Date Format 검증 실패")

        # Date Format 복구
        print(f"\n{'='*60}")
        print("🔄 Date Format 복구 (YYYY/MM/DD)")
        print(f"{'='*60}")
        if select_jquery_dropdown(page, "#date-format-button", "(YYYY/MM/DD)", silent=True):
            ui_save(page, silent=True)
            time.sleep(TIMEOUTS.get("retry_delay", 2))
            verify_datetime_value(api_client, "dateFormat", "YYYY/MM/DD", max_retries=3, silent=True)
            print_success("복구 완료")

        return True, "날짜/시간 테스트 완료"
        
    except Exception as e:
        return False, str(e)