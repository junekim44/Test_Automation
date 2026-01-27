"""
개선된 시스템 테스트 모듈
- config.py를 사용한 설정값 관리
- api_client.py를 사용한 통합 API 호출
- 중복 코드 제거 및 로직 개선
"""

import os
import time
from typing import Optional, Tuple
from playwright.sync_api import Page
from common_actions import handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS
from config import TIMEOUTS
from api_client import CameraApiClient

# ===========================================================
# ⚙️ [공통 헬퍼 함수] UI 네비게이션
# ===========================================================

def navigate_to_system_general(page: Page) -> bool:
    """
    시스템 > 일반 메뉴로 이동 (공통 네비게이션)
    
    Returns:
        성공 여부
    """
    try:
        page.locator("#Page200_id").click()  # 시스템
        page.locator("#Page201_id").click()  # 일반
        page.wait_for_timeout(TIMEOUTS.get("ui_navigation", 500))
        return True
    except Exception as e:
        print(f"❌ [Navigation] 메뉴 이동 실패: {e}")
        return False

# ===========================================================
# ⚙️ [내부 액션 함수] 시스템 테스트 전용 (개선됨)
# ===========================================================

def api_get_note(api_client: CameraApiClient, max_retries: int = None) -> Optional[str]:
    """
    API로 '설명(Note)' 값 조회 (개선된 버전 - 재시도 로직 포함)
    
    Args:
        api_client: CameraApiClient 인스턴스
        max_retries: 최대 재시도 횟수 (None이면 TIMEOUTS 사용)
    
    Returns:
        Note 값 또는 None
    """
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    
    print(f"[API] 'Note' 값 조회 시도...")
    
    for attempt in range(max_retries):
        data = api_client.get_system_info()
        
        if data:
            val = data.get("note", "")
            if val is None:
                val = ""
            print(f"[API] 조회 성공: note='{val}'")
            return val
        else:
            if attempt < max_retries - 1:
                print(f"⚠️ [API] 조회 실패 (시도 {attempt + 1}/{max_retries}). 재시도...")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
            else:
                print("❌ [API] 최종 실패")
    
    return None

def verify_note_value(api_client: CameraApiClient, expected_value: str, 
                     max_retries: int = None, timeout: float = None) -> bool:
    """
    Note 값 검증 (재시도 로직 포함)
    
    Args:
        api_client: CameraApiClient 인스턴스
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
        
        val = api_get_note(api_client, max_retries=1)
        
        if val == expected_value:
            print(f"✅ [Verify] 검증 성공: '{expected_value}'")
            return True
        else:
            if attempt < max_retries - 1:
                wait_time = TIMEOUTS.get("retry_delay", 2)
                print(f"⚠️ [Verify] 불일치 (시도 {attempt + 1}/{max_retries}). "
                      f"기대: '{expected_value}', 실제: '{val}'. {wait_time}초 후 재시도...")
                time.sleep(wait_time)
            else:
                print(f"❌ [Verify] 최종 실패. 기대: '{expected_value}', 실제: '{val}'")
    
    return False

def ui_set_note(page: Page, new_note_value: str) -> bool:
    """
    UI에서 '설명' 값 변경 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        new_note_value: 설정할 Note 값
    
    Returns:
        성공 여부
    """
    print(f"[UI] '설명' 값 변경 시도 -> '{new_note_value}'")
    
    try:
        # 메뉴 이동
        if not navigate_to_system_general(page):
            return False
        
        # 현재 값 확인
        input_el = page.locator("#note")
        input_el.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        current_val = input_el.input_value()
        
        if current_val == new_note_value:
            print(f"[UI] 이미 값이 '{new_note_value}'입니다. 변경 스킵.")
            return True

        # 값 변경
        print(f"[UI] 값 입력 및 저장...")
        input_el.fill(new_note_value)
        input_el.dispatch_event("input")
        input_el.dispatch_event("change")
        
        # 저장 버튼 클릭
        save_btn = page.locator("#setup-apply")
        save_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        save_btn.click()
        
        # 팝업 처리 및 저장 완료 대기
        if handle_popup(page, timeout=TIMEOUTS.get("popup", 5000)):
            # 저장 버튼이 비활성화될 때까지 대기 (저장 완료 확인)
            try:
                save_btn.wait_for(state="disabled", timeout=TIMEOUTS.get("popup", 5000))
            except:
                pass  # 비활성화 안되어도 저장은 완료될 수 있음
            print("[UI] 저장 완료 (팝업 확인됨).")
            return True
        else:
            print("❌ [UI] 저장 실패 (팝업 안뜸).")
            return False
            
    except Exception as e:
        print(f"❌ [UI] 에러: {e}")
        import traceback
        traceback.print_exc()
        return False

def export_settings(page: Page, save_as: str = "registry.dat") -> bool:
    """
    설정 내보내기 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        save_as: 저장할 파일 경로
    
    Returns:
        성공 여부
    """
    print(f"[Action] 설정 내보내기 시작 -> {save_as}")
    
    # 기존 파일 삭제
    if os.path.exists(save_as):
        try:
            os.remove(save_as)
            print(f"[Action] 기존 파일 삭제됨.")
        except Exception as e:
            print(f"⚠️ [Action] 기존 파일 삭제 실패: {e}")

    try:
        # 메뉴 이동
        if not navigate_to_system_general(page):
            return False

        # 다운로드 버튼 클릭
        print("[Action] 다운로드 버튼 클릭...")
        export_btn = page.locator("#reg-export")
        export_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        with page.expect_download(timeout=TIMEOUTS.get("api_request", 10) * 1000) as download_info:
            export_btn.click()
        
        # 파일 저장
        download = download_info.value
        download.save_as(save_as)
        
        # 파일 검증
        if os.path.exists(save_as):
            file_size = os.path.getsize(save_as)
            if file_size > 0:
                print(f"[Action] 파일 저장 성공 ({file_size} bytes).")
                return True
            else:
                print("❌ [Action] 파일 저장 실패 (크기 0).")
                return False
        else:
            print("❌ [Action] 파일 저장 실패 (파일 없음).")
            return False
            
    except Exception as e:
        print(f"❌ [Action] 내보내기 에러: {e}")
        import traceback
        traceback.print_exc()
        return False

def import_settings(page: Page, file_path: str = "registry.dat", 
                   include_network: bool = False) -> bool:
    """
    설정 불러오기 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        file_path: 불러올 파일 경로
        include_network: 네트워크 설정 포함 여부 (기본: False)
    
    Returns:
        성공 여부
    """
    # 파일 존재 확인
    if not os.path.exists(file_path):
        print(f"❌ [Action] 파일 없음: {file_path}")
        return False
    
    file_path = os.path.abspath(file_path)
    print(f"[Action] 설정 불러오기 시작 -> {file_path}")
    
    try:
        # 메뉴 이동
        if not navigate_to_system_general(page):
            return False

        # 파일 선택창 열기
        print("[Action] 파일 선택창 열기...")
        import_btn = page.locator("#reg-import")
        import_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        with page.expect_file_chooser(timeout=TIMEOUTS.get("popup", 5000)) as fc_info:
            import_btn.click()
        
        fc_info.value.set_files(file_path)

        # 네트워크 설정 팝업 처리
        print(f"[Action] 네트워크 설정 팝업 처리 ({'Yes' if include_network else 'No'})...")
        confirm = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-import-setup-diag"))
        confirm.wait_for(state="visible", timeout=TIMEOUTS.get("popup", 5000))
        
        # 네트워크 설정 체크박스 처리
        network_chk = confirm.locator("#include-network-setup")
        if network_chk.is_visible():
            if include_network and not network_chk.is_checked():
                network_chk.check()
            elif not include_network and network_chk.is_checked():
                network_chk.uncheck()
        
        # 확인 버튼 클릭
        btns = confirm.locator(DIALOG_BUTTONS)
        if btns.count() > 1:
            # 두 번째 버튼이 "No" 또는 취소 버튼
            btns.nth(0 if include_network else 1).click()
        else:
            btns.first.click()
        
        # 세션 갱신 대기
        print("[Action] 세션 갱신 (새로고침)...")
        page.reload()
        page.wait_for_selector("#Page200_id", timeout=TIMEOUTS.get("page_load", 15000))
        
        # 안정화 대기
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        print("✅ [Action] 불러오기 완료.")
        return True
        
    except Exception as e:
        print(f"❌ [Action] 불러오기 에러: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_default_settings(page: Page, password: str = "qwerty0-", 
                         include_network: bool = False) -> bool:
    """
    기본 설정 불러오기 (초기화) - 개선된 버전
    
    Args:
        page: Playwright Page 객체
        password: 재설정할 비밀번호
        include_network: 네트워크 설정 포함 여부 (기본: False)
    
    Returns:
        성공 여부
    """
    print("[Action] 기본 설정(초기화) 시작...")
    
    try:
        # 메뉴 이동
        if not navigate_to_system_general(page):
            return False
        
        # 초기화 버튼 클릭
        print("[Action] 초기화 버튼 클릭...")
        default_btn = page.locator("#set-default")
        default_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        default_btn.click()

        # 확인 팝업 처리
        print(f"[Action] 확인 팝업 (네트워크 {'포함' if include_network else '제외'})...")
        confirm = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-default-setup-diag"))
        confirm.wait_for(state="visible", timeout=TIMEOUTS.get("popup", 5000))

        # 네트워크 설정 체크박스 처리
        chk = confirm.locator("#include-network-setup")
        if chk.is_visible():
            if include_network and not chk.is_checked():
                chk.check()
                print("[Action] 네트워크 체크 설정함.")
            elif not include_network and chk.is_checked():
                chk.uncheck()
                print("[Action] 네트워크 체크 해제함.")
        
        # 확인 버튼 클릭
        confirm.locator(DIALOG_BUTTONS).first.click()

        # Warning 팝업 처리
        print("[Action] Warning 팝업 처리...")
        handle_popup(page, timeout=TIMEOUTS.get("popup", 5000))

        # 비밀번호 재설정
        print("[Action] 비밀번호 재설정...")
        edit_user = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#edit-user-diag"))
        edit_user.wait_for(state="visible", timeout=TIMEOUTS.get("popup", 5000))
        
        # 비밀번호 입력
        pwd1 = edit_user.locator("#edit-user-edit-passwd1")
        pwd2 = edit_user.locator("#edit-user-edit-passwd2")
        pwd1.fill(password)
        pwd2.fill(password)
        
        # 이메일 미사용 체크
        email_chk = edit_user.locator("#edit-email_not_use")
        if email_chk.is_visible():
            email_chk.check()
        
        # 이메일 경고 팝업 처리 (있는 경우)
        try:
            if page.locator(VISIBLE_DIALOG).count() > 1:
                page.locator(VISIBLE_DIALOG).last.locator(DIALOG_BUTTONS).first.click()
                print("[Action] 이메일 경고 처리됨.")
        except:
            pass

        # 설정 완료
        print("[Action] 설정 완료 (OK)...")
        edit_user.locator(DIALOG_BUTTONS).first.click()

        # 최종 완료 팝업 대기
        print("[Action] 최종 완료 팝업 대기...")
        if handle_popup(page, timeout=TIMEOUTS.get("page_load", 15000)):
            print("[Action] 최종 팝업 확인됨.")
        
        # 세션 갱신
        print("[Action] 세션 갱신 (새로고침)...")
        page.reload()
        page.wait_for_selector("#Page200_id", timeout=TIMEOUTS.get("page_load", 15000))
        
        # 안정화 대기
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        print("✅ [Action] 초기화 완료.")
        return True
        
    except Exception as e:
        print(f"❌ [Action] 초기화 에러: {e}")
        import traceback
        traceback.print_exc()
        return False

# ===========================================================
# ⚙️ [테스트 케이스] (개선됨)
# ===========================================================

def run_default_setup_test(page: Page, api_client: CameraApiClient) -> Tuple[bool, str]:
    """
    기본 설정(초기화) 및 복구 테스트 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        api_client: CameraApiClient 인스턴스
    
    Returns:
        (성공 여부, 메시지) 튜플
    """
    print("\n" + "="*60)
    print("--- [TC 3] 기본 설정(초기화) 및 복구 테스트 ---")
    print("="*60)
    
    test_value = "DIRTY_BEFORE_RESET"
    backup_file = "backup.dat"
    
    try:
        # 1. 오염
        print(f"\n[Step 1] 설정 오염 시도 (값: '{test_value}')...")
        if not ui_set_note(page, test_value):
            raise Exception("설정 변경 실패")
        
        # 변경 반영 대기
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # 2. 백업
        print(f"\n[Step 2] 현재 상태 백업 -> {backup_file}...")
        if not export_settings(page, backup_file):
            raise Exception("백업 실패")
        
        # 3. 초기화
        print("\n[Step 3] 초기화 실행...")
        if not load_default_settings(page):
            raise Exception("초기화 실패")
        
        # 4. 초기화 검증 (재시도 로직 포함)
        print("\n[Step 4] 초기화 검증 (API - 재시도 포함)...")
        if not verify_note_value(api_client, "", max_retries=5):
            raise Exception("초기화 검증 실패 (값이 비어있지 않음)")
        
        # 5. 복구
        print(f"\n[Step 5] 백업 파일로 복구 -> {backup_file}...")
        if not import_settings(page, backup_file):
            raise Exception("복구 실패")
        
        # 복구 반영 대기
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # 6. 복구 검증 (재시도 로직 포함)
        print(f"\n[Step 6] 복구 검증 (API - 재시도 포함)...")
        if not verify_note_value(api_client, test_value, max_retries=5):
            raise Exception(f"복구 검증 실패 (값이 '{test_value}'가 아님)")
        
        print("\n" + "="*60)
        print("✅ [TC 3] 초기화 및 복구 성공")
        print("="*60)
        return True, "초기화 및 복구 성공"
        
    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ [TC 3] 테스트 실패: {e}")
        print("="*60)
        return False, str(e)

def run_setup_roundtrip_test(page: Page, api_client: CameraApiClient) -> Tuple[bool, str]:
    """
    설정 내보내기/불러오기 테스트 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        api_client: CameraApiClient 인스턴스
    
    Returns:
        (성공 여부, 메시지) 튜플
    """
    print("\n" + "="*60)
    print("--- [TC 1] 설정 내보내기/불러오기 테스트 ---")
    print("="*60)
    
    test_value = "TEST_VALUE_123"
    trash_value = "TRASH_VALUE"
    export_file = "test_conf.dat"
    
    try:
        # 1. 테스트값 설정
        print(f"\n[Step 1] 테스트 값 설정 (값: '{test_value}')...")
        if not ui_set_note(page, test_value):
            raise Exception("설정 실패")
        
        # 변경 반영 대기
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # 초기값 검증
        if not verify_note_value(api_client, test_value, max_retries=3):
            raise Exception(f"초기값 검증 실패 (값이 '{test_value}'가 아님)")
        
        # 2. 내보내기
        print(f"\n[Step 2] 설정 내보내기 -> {export_file}...")
        if not export_settings(page, export_file):
            raise Exception("내보내기 실패")
        
        # 3. 값 오염
        print(f"\n[Step 3] 값 오염 시키기 (값: '{trash_value}')...")
        if not ui_set_note(page, trash_value):
            raise Exception("오염 실패")
        
        # 오염 확인
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        if not verify_note_value(api_client, trash_value, max_retries=3):
            print("⚠️ 오염 값이 반영되지 않았지만 계속 진행...")
        
        # 4. 불러오기
        print(f"\n[Step 4] 설정 불러오기 <- {export_file}...")
        if not import_settings(page, export_file):
            raise Exception("불러오기 실패")
        
        # 불러오기 반영 대기
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # 5. 최종 검증 (재시도 로직 포함)
        print(f"\n[Step 5] 최종 검증 (API - 재시도 포함)...")
        if not verify_note_value(api_client, test_value, max_retries=5):
            raise Exception(f"검증 실패 (값이 '{test_value}'가 아님)")
        
        print("\n" + "="*60)
        print("✅ [TC 1] Round-Trip 성공")
        print("="*60)
        return True, "Round-Trip 성공"
        
    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ [TC 1] 테스트 실패: {e}")
        print("="*60)
        return False, str(e)
