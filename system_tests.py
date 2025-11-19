import os
import time
from playwright.sync_api import Page
from common_actions import parse_api_response, handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS

# ===========================================================
# ⚙️ [내부 액션 함수] 시스템 테스트 전용
# ===========================================================

def api_get_note(page: Page, ip: str):
    """API로 '설명(Note)' 값 조회 (재시도 로직 포함)"""
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=systemInfo&mode=1"
    print(f"[API] 'Note' 값 조회 시도: {api_url}")
    
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
                print(f"⚠️ [API] 401 Unauthorized (시도 {attempt+1}/{max_retries}). 페이지 새로고침...")
                page.reload()
                page.wait_for_selector("#Page200_id", timeout=15000)
                time.sleep(2)
                continue

            if response_text and not response_text.startswith("Error"):
                val = parse_api_response(response_text).get("note", "")
                if val is None: val = ""
                print(f"[API] 조회 성공: note='{val}'")
                return val
            else:
                print(f"⚠️ [API] 응답 오류: {response_text}")
        except Exception as e:
            print(f"⚠️ [API] 에러: {e}")
            time.sleep(2)
    
    print("❌ [API] 최종 실패")
    return None

def ui_set_note(page: Page, new_note_value: str):
    """UI에서 '설명' 값 변경"""
    print(f"[UI] '설명' 값 변경 시도 -> '{new_note_value}'")
    try:
        page.locator("#Page200_id").click() # 시스템
        page.locator("#Page201_id").click() # 일반
        page.wait_for_timeout(500)
        
        input_el = page.locator("#note")
        current_val = input_el.input_value()
        
        if current_val == new_note_value:
            print(f"[UI] 이미 값이 '{new_note_value}'입니다. 변경 스킵.")
            return True

        print(f"[UI] 값 입력 및 저장...")
        input_el.fill(new_note_value)
        input_el.dispatch_event("input")
        input_el.dispatch_event("change")
        
        page.locator("#setup-apply").click()
        if handle_popup(page): # 성공 팝업 처리
            print("[UI] 저장 완료 (팝업 확인됨).")
            return True
        else:
            print("❌ [UI] 저장 실패 (팝업 안뜸).")
            return False
    except Exception as e:
        print(f"❌ [UI] 에러: {e}")
        return False

def export_settings(page: Page, save_as="registry.dat"):
    """설정 내보내기"""
    print(f"[Action] 설정 내보내기 시작 -> {save_as}")
    if os.path.exists(save_as): 
        os.remove(save_as)
        print(f"[Action] 기존 파일 삭제됨.")

    try:
        page.locator("#Page200_id").click()
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        print("[Action] 다운로드 버튼 클릭...")
        with page.expect_download() as download_info:
            page.locator("#reg-export").click()
        
        download_info.value.save_as(save_as)
        
        if os.path.exists(save_as) and os.path.getsize(save_as) > 0:
            print(f"[Action] 파일 저장 성공 ({os.path.getsize(save_as)} bytes).")
            return True
        else:
            print("❌ [Action] 파일 저장 실패 (크기 0 또는 없음).")
            return False
    except Exception as e:
        print(f"❌ [Action] 내보내기 에러: {e}")
        return False

def import_settings(page: Page, file_path="registry.dat"):
    """설정 불러오기"""
    if not os.path.exists(file_path): 
        print(f"❌ [Action] 파일 없음: {file_path}")
        return False
    
    file_path = os.path.abspath(file_path)
    print(f"[Action] 설정 불러오기 시작 -> {file_path}")
    
    try:
        page.locator("#Page200_id").click()
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        print("[Action] 파일 선택창 열기...")
        with page.expect_file_chooser() as fc_info:
            page.locator("#reg-import").click()
        fc_info.value.set_files(file_path)

        print("[Action] 네트워크 설정 팝업 처리 (No)...")
        confirm = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-import-setup-diag"))
        confirm.wait_for(state="visible", timeout=5000)
        btns = confirm.locator(DIALOG_BUTTONS)
        if btns.count() > 1: btns.nth(1).click() 
        else: btns.first.click()
        
        print("[Action] 세션 갱신 (새로고침)...")
        page.reload() 
        page.wait_for_selector("#Page200_id", timeout=15000)
        print("✅ [Action] 불러오기 완료.")
        return True
    except Exception as e:
        print(f"❌ [Action] 불러오기 에러: {e}")
        return False

def load_default_settings(page: Page, password="qwerty0-"):
    """기본 설정 불러오기 (초기화)"""
    print("[Action] 기본 설정(초기화) 시작...")
    try:
        page.locator("#Page200_id").click()
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        print("[Action] 초기화 버튼 클릭...")
        page.locator("#set-default").click()

        print("[Action] 확인 팝업 (네트워크 유지 해제)...")
        confirm = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-default-setup-diag"))
        confirm.wait_for(state="visible")
        
        chk = confirm.locator("#include-network-setup")
        if chk.is_visible() and chk.is_checked(): 
            chk.uncheck()
            print("[Action] 네트워크 체크 해제함.")
        
        confirm.locator(DIALOG_BUTTONS).first.click()

        print("[Action] Warning 팝업 처리...")
        handle_popup(page)

        print("[Action] 비밀번호 재설정...")
        edit_user = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#edit-user-diag"))
        edit_user.wait_for(state="visible")
        edit_user.locator("#edit-user-edit-passwd1").fill(password)
        edit_user.locator("#edit-user-edit-passwd2").fill(password)
        
        edit_user.locator("#edit-email_not_use").check()
        
        try:
            if page.locator(VISIBLE_DIALOG).count() > 1:
                page.locator(VISIBLE_DIALOG).last.locator(DIALOG_BUTTONS).first.click()
                print("[Action] 이메일 경고 처리됨.")
        except: pass

        print("[Action] 설정 완료 (OK)...")
        edit_user.locator(DIALOG_BUTTONS).first.click()

        print("[Action] 최종 완료 팝업 대기...")
        if handle_popup(page, timeout=15000):
            print("[Action] 최종 팝업 확인됨.")
        
        print("[Action] 세션 갱신 (새로고침)...")
        page.reload()
        page.wait_for_selector("#Page200_id", timeout=15000)
        print("✅ [Action] 초기화 완료.")
        return True
    except Exception as e:
        print(f"❌ [Action] 초기화 에러: {e}")
        return False

# ===========================================================
# ⚙️ [테스트 케이스]
# ===========================================================

def run_default_setup_test(page: Page, camera_ip: str):
    print("\n--- [TC 3] 기본 설정(초기화) 및 복구 테스트 ---")
    try:
        # 1. 오염
        print("\n[Step 1] 설정 오염 시도...")
        if not ui_set_note(page, "DIRTY_BEFORE_RESET"): raise Exception("설정 변경 실패")
        
        # 2. 백업
        print("\n[Step 2] 현재 상태 백업...")
        if not export_settings(page, "backup.dat"): raise Exception("백업 실패")
        
        # 3. 초기화
        print("\n[Step 3] 초기화 실행...")
        if not load_default_settings(page): raise Exception("초기화 실패")
        
        # 4. 초기화 검증
        print("\n[Step 4] 초기화 검증 (API)...")
        val = api_get_note(page, camera_ip)
        if val != "": raise Exception(f"초기화 안됨 (값: '{val}')")
        print("✅ 초기화 검증 통과 (값이 비어있음).")
        
        # 5. 복구
        print("\n[Step 5] 백업 파일로 복구...")
        if not import_settings(page, "backup.dat"): raise Exception("복구 실패")
        
        # 6. 복구 검증
        print("\n[Step 6] 복구 검증 (API)...")
        val = api_get_note(page, camera_ip)
        if val != "DIRTY_BEFORE_RESET": raise Exception(f"복구 안됨 (값: '{val}')")
        print(f"✅ 복구 검증 통과 (값: {val}).")
        
        return True, "초기화 및 복구 성공"
    except Exception as e:
        return False, str(e)

def run_setup_roundtrip_test(page: Page, camera_ip: str):
    print("\n--- [TC 1] 설정 내보내기/불러오기 테스트 ---")
    try:
        # 1. 테스트값 설정
        print("\n[Step 1] 테스트 값 설정...")
        if not ui_set_note(page, "TEST_VALUE_123"): raise Exception("설정 실패")
        
        # 2. 내보내기
        print("\n[Step 2] 설정 내보내기...")
        if not export_settings(page, "test_conf.dat"): raise Exception("내보내기 실패")
        
        # 3. 값 오염
        print("\n[Step 3] 값 오염 시키기...")
        if not ui_set_note(page, "TRASH_VALUE"): raise Exception("오염 실패")
        
        # 4. 불러오기
        print("\n[Step 4] 설정 불러오기...")
        if not import_settings(page, "test_conf.dat"): raise Exception("불러오기 실패")
        
        # 5. 검증
        print("\n[Step 5] 최종 검증 (API)...")
        val = api_get_note(page, camera_ip)
        if val != "TEST_VALUE_123": raise Exception(f"검증 실패 (값: '{val}')")
        print(f"✅ 최종 검증 통과 (값: {val}).")
        
        return True, "Round-Trip 성공"
    except Exception as e:
        return False, str(e)