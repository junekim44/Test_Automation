"""
시스템 테스트 모듈
- 초기화 및 복구 테스트
- 설정 내보내기/불러오기 테스트
- 간결한 출력 및 명확한 진행 상황 표시
"""

import os
import time
from typing import Optional, Tuple
from playwright.sync_api import Page
from common_actions import handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS
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

def navigate_to_system_general(page: Page) -> bool:
    """시스템 > 일반 메뉴로 이동"""
    try:
        page.locator("#Page200_id").click()
        page.locator("#Page201_id").click()
        page.wait_for_timeout(TIMEOUTS.get("ui_navigation", 500))
        return True
    except Exception as e:
        print_error(f"메뉴 이동 실패: {e}")
        return False

# ===========================================================
# ⚙️ [내부 액션 함수] 시스템 테스트 전용 (개선됨)
# ===========================================================

def api_get_note(api_client: CameraApiClient, max_retries: int = None, silent: bool = False) -> Optional[str]:
    """API로 'Note' 값 조회 (재시도 로직 포함)"""
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    
    for attempt in range(max_retries):
        data = api_client.get_system_info()
        
        if data:
            val = data.get("note", "") or ""
            if not silent:
                print_success(f"Note='{val}'")
            return val
        
        if attempt < max_retries - 1:
            if not silent:
                print_warning(f"조회 실패 ({attempt + 1}/{max_retries}), 재시도 중...")
            time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    if not silent:
        print_error("Note 조회 최종 실패")
    return None

def verify_note_value(api_client: CameraApiClient, expected_value: str, 
                     max_retries: int = None, timeout: float = None) -> bool:
    """Note 값 검증 (재시도 포함)"""
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    if timeout is None:
        timeout = TIMEOUTS.get("api_request", 10) * max_retries
    
    start_time = time.time()
    print_action(f"검증 중: 기대값='{expected_value}'")
    
    for attempt in range(max_retries):
        if time.time() - start_time > timeout:
            print_error(f"타임아웃 ({timeout}초 초과)")
            return False
        
        val = api_get_note(api_client, max_retries=1, silent=True)
        
        if val == expected_value:
            print_success("검증 성공")
            return True
        
        if attempt < max_retries - 1:
            print_warning(f"불일치 (실제: '{val}'), 재시도 {attempt + 1}/{max_retries}")
            time.sleep(TIMEOUTS.get("retry_delay", 2))
        else:
            print_error(f"검증 실패: 기대='{expected_value}', 실제='{val}'")
    
    return False

def ui_set_note(page: Page, new_note_value: str) -> bool:
    """UI에서 'Note' 값 변경"""
    print_action(f"Note 변경: '{new_note_value}'")
    
    try:
        if not navigate_to_system_general(page):
            return False
        
        input_el = page.locator("#note")
        input_el.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        current_val = input_el.input_value()
        
        if current_val == new_note_value:
            print_success("값이 이미 설정되어 있음")
            return True

        input_el.fill(new_note_value)
        input_el.dispatch_event("input")
        input_el.dispatch_event("change")
        
        save_btn = page.locator("#setup-apply")
        save_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        save_btn.click()
        
        if handle_popup(page, timeout=TIMEOUTS.get("popup", 5000)):
            try:
                save_btn.wait_for(state="disabled", timeout=TIMEOUTS.get("popup", 5000))
            except:
                pass
            print_success("저장 완료")
            return True
        else:
            print_error("저장 실패 (팝업 없음)")
            return False
            
    except Exception as e:
        print_error(f"UI 변경 실패: {e}")
        return False

def export_settings(page: Page, save_as: str = "registry.dat") -> bool:
    """설정 내보내기"""
    print_action(f"설정 내보내기: {save_as}")
    
    if os.path.exists(save_as):
        try:
            os.remove(save_as)
        except Exception as e:
            print_warning(f"기존 파일 삭제 실패: {e}")

    try:
        if not navigate_to_system_general(page):
            return False

        export_btn = page.locator("#reg-export")
        export_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        with page.expect_download(timeout=TIMEOUTS.get("api_request", 10) * 1000) as download_info:
            export_btn.click()
        
        download = download_info.value
        download.save_as(save_as)
        
        if os.path.exists(save_as) and os.path.getsize(save_as) > 0:
            file_size = os.path.getsize(save_as)
            print_success(f"내보내기 완료 ({file_size} bytes)")
            return True
        else:
            print_error("파일 저장 실패")
            return False
            
    except Exception as e:
        print_error(f"내보내기 실패: {e}")
        return False

def import_settings(page: Page, file_path: str = "registry.dat", 
                   include_network: bool = False) -> bool:
    """설정 불러오기"""
    if not os.path.exists(file_path):
        print_error(f"파일 없음: {file_path}")
        return False
    
    file_path = os.path.abspath(file_path)
    print_action(f"설정 불러오기: {os.path.basename(file_path)}")
    
    try:
        if not navigate_to_system_general(page):
            return False

        import_btn = page.locator("#reg-import")
        import_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        with page.expect_file_chooser(timeout=TIMEOUTS.get("popup", 5000)) as fc_info:
            import_btn.click()
        
        fc_info.value.set_files(file_path)

        confirm = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-import-setup-diag"))
        confirm.wait_for(state="visible", timeout=TIMEOUTS.get("popup", 5000))
        
        network_chk = confirm.locator("#include-network-setup")
        if network_chk.is_visible():
            if include_network and not network_chk.is_checked():
                network_chk.check()
            elif not include_network and network_chk.is_checked():
                network_chk.uncheck()
        
        btns = confirm.locator(DIALOG_BUTTONS)
        if btns.count() > 1:
            btns.nth(0 if include_network else 1).click()
        else:
            btns.first.click()
        
        page.reload()
        page.wait_for_selector("#Page200_id", timeout=TIMEOUTS.get("page_load", 15000))
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        print_success("불러오기 완료")
        return True
        
    except Exception as e:
        print_error(f"불러오기 실패: {e}")
        return False

def load_default_settings(page: Page, password: str = "qwerty0-", 
                         include_network: bool = False) -> bool:
    """기본 설정 불러오기 (초기화)"""
    print_action("기본 설정 복구 (초기화)")
    
    try:
        if not navigate_to_system_general(page):
            return False
        
        default_btn = page.locator("#set-default")
        default_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        default_btn.click()

        confirm = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-default-setup-diag"))
        confirm.wait_for(state="visible", timeout=TIMEOUTS.get("popup", 5000))

        chk = confirm.locator("#include-network-setup")
        if chk.is_visible():
            if include_network and not chk.is_checked():
                chk.check()
            elif not include_network and chk.is_checked():
                chk.uncheck()
        
        confirm.locator(DIALOG_BUTTONS).first.click()
        handle_popup(page, timeout=TIMEOUTS.get("popup", 5000))

        edit_user = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#edit-user-diag"))
        edit_user.wait_for(state="visible", timeout=TIMEOUTS.get("popup", 5000))
        
        pwd1 = edit_user.locator("#edit-user-edit-passwd1")
        pwd2 = edit_user.locator("#edit-user-edit-passwd2")
        pwd1.fill(password)
        pwd2.fill(password)
        
        email_chk = edit_user.locator("#edit-email_not_use")
        if email_chk.is_visible():
            email_chk.check()
        
        try:
            if page.locator(VISIBLE_DIALOG).count() > 1:
                page.locator(VISIBLE_DIALOG).last.locator(DIALOG_BUTTONS).first.click()
        except:
            pass

        edit_user.locator(DIALOG_BUTTONS).first.click()
        handle_popup(page, timeout=TIMEOUTS.get("page_load", 15000))
        
        page.reload()
        page.wait_for_selector("#Page200_id", timeout=TIMEOUTS.get("page_load", 15000))
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        print_success("초기화 완료")
        return True
        
    except Exception as e:
        print_error(f"초기화 실패: {e}")
        return False

# ===========================================================
# ⚙️ [테스트 케이스] (개선됨)
# ===========================================================

def run_default_setup_test(page: Page, api_client: CameraApiClient) -> Tuple[bool, str]:
    """기본 설정(초기화) 및 복구 테스트"""
    test_value = "DIRTY_BEFORE_RESET"
    backup_file = "backup.dat"
    total_steps = 6
    
    try:
        # Step 1: 설정 오염
        print_step(1, total_steps, f"설정 오염 (값='{test_value}')")
        if not ui_set_note(page, test_value):
            raise Exception("설정 변경 실패")
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # Step 2: 백업
        print_step(2, total_steps, f"현재 상태 백업 ({backup_file})")
        if not export_settings(page, backup_file):
            raise Exception("백업 실패")
        
        # Step 3: 초기화
        print_step(3, total_steps, "기본 설정 복구 (초기화)")
        if not load_default_settings(page):
            raise Exception("초기화 실패")
        
        # Step 4: 초기화 검증
        print_step(4, total_steps, "초기화 검증 (Note='')")
        if not verify_note_value(api_client, "", max_retries=5):
            raise Exception("초기화 검증 실패")
        
        # Step 5: 복구
        print_step(5, total_steps, f"백업 파일로 복구 ({backup_file})")
        if not import_settings(page, backup_file):
            raise Exception("복구 실패")
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # Step 6: 복구 검증
        print_step(6, total_steps, f"복구 검증 (Note='{test_value}')")
        if not verify_note_value(api_client, test_value, max_retries=5):
            raise Exception("복구 검증 실패")
        
        return True, "초기화 및 복구 성공"
        
    except Exception as e:
        return False, str(e)

def run_setup_roundtrip_test(page: Page, api_client: CameraApiClient) -> Tuple[bool, str]:
    """설정 내보내기/불러오기 테스트"""
    test_value = "TEST_VALUE_123"
    trash_value = "TRASH_VALUE"
    export_file = "test_conf.dat"
    total_steps = 5
    
    try:
        # Step 1: 테스트값 설정
        print_step(1, total_steps, f"테스트 값 설정 (값='{test_value}')")
        if not ui_set_note(page, test_value):
            raise Exception("설정 실패")
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        if not verify_note_value(api_client, test_value, max_retries=3):
            raise Exception("초기값 검증 실패")
        
        # Step 2: 내보내기
        print_step(2, total_steps, f"설정 내보내기 ({export_file})")
        if not export_settings(page, export_file):
            raise Exception("내보내기 실패")
        
        # Step 3: 값 오염
        print_step(3, total_steps, f"설정 오염 (값='{trash_value}')")
        if not ui_set_note(page, trash_value):
            raise Exception("오염 실패")
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        if not verify_note_value(api_client, trash_value, max_retries=3):
            print_warning("오염 값 반영 안됨 (계속 진행)")
        
        # Step 4: 불러오기
        print_step(4, total_steps, f"설정 불러오기 ({export_file})")
        if not import_settings(page, export_file):
            raise Exception("불러오기 실패")
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # Step 5: 최종 검증
        print_step(5, total_steps, f"복원 검증 (Note='{test_value}')")
        if not verify_note_value(api_client, test_value, max_retries=5):
            raise Exception("검증 실패")
        
        return True, "Round-Trip 성공"
        
    except Exception as e:
        return False, str(e)
