import os
import time
from urllib.parse import parse_qsl
from playwright.sync_api import Page, expect

# 🌍 [다국어 대응] 공통 Selector 정의
VISIBLE_DIALOG = '.ui-dialog:visible'
DIALOG_BUTTONS = '.ui-dialog-buttonset button'

# -----------------------------------------------------------
# 🛠️ [유틸리티] API 응답 파서
# -----------------------------------------------------------
def parse_api_response(response_text: str) -> dict:
    return dict(parse_qsl(response_text))

# -----------------------------------------------------------
# 🛠️ [유틸리티] 범용 팝업 처리기
# -----------------------------------------------------------
def handle_popup(page: Page, button_index=0, timeout=5000):
    try:
        page.wait_for_selector(VISIBLE_DIALOG, state="visible", timeout=timeout)
        top_dialog = page.locator(VISIBLE_DIALOG).last
        button = top_dialog.locator(DIALOG_BUTTONS).nth(button_index)
        
        if button.is_visible():
            button.click()
            top_dialog.wait_for(state="hidden", timeout=3000)
            return True
        return False
    except Exception:
        return False

# -----------------------------------------------------------
# ⚙️ [헬퍼 1] 설정 내보내기
# -----------------------------------------------------------
def export_and_verify_settings(page: Page, save_as="registry.dat"):
    print(f"\n--- [액션] 설정 내보내기 작업 시작 ---")
    if os.path.exists(save_as):
        os.remove(save_as)

    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500) 
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        with page.expect_download() as download_info:
            page.locator("#reg-export").click()
        
        download = download_info.value
        download.save_as(save_as)
        print(f"[액션] 파일 저장 완료: {save_as}")

        if os.path.exists(save_as) and os.path.getsize(save_as) > 0:
            return True, save_as
        else:
            return False, "파일이 없거나 크기가 0입니다."
    except Exception as e:
        print(f"❌ [액션] 내보내기 오류: {e}")
        return False, str(e)

# -----------------------------------------------------------
# ⚙️ [헬퍼 2] 설정 불러오기
# -----------------------------------------------------------
def import_settings_and_reboot(page: Page, file_path="registry.dat"):
    IMPORT_BUTTON_SELECTOR = "#reg-import"
    if not os.path.exists(file_path):
        return False, "파일 없음"

    absolute_file_path = os.path.abspath(file_path)
    print(f"\n--- [액션] 설정 불러오기 작업 시작 ---")
    
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        with page.expect_file_chooser() as fc_info:
            page.locator(IMPORT_BUTTON_SELECTOR).click() 
        
        file_chooser = fc_info.value
        file_chooser.set_files(absolute_file_path)
        
        print("[액션] 네트워크 설정 팝업 처리 (No/아니오)...")
        confirm_dialog = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-import-setup-diag"))
        confirm_dialog.wait_for(state="visible", timeout=5000)
        
        buttons = confirm_dialog.locator(DIALOG_BUTTONS)
        if buttons.count() > 1:
            buttons.nth(1).click()
        else:
            buttons.first.click()
        
        
        print("✅ [액션] 설정 불러오기 완료.")
        
        print("[액션] 설정 적용 확인을 위해 페이지 새로고침...")
        page.reload()
        page.wait_for_selector("#Page200_id", timeout=15000)
        
        return True, "설정 불러오기 완료"
    except Exception as e:
        print(f"❌ [액션] 불러오기 중 오류: {e}")
        return False, str(e)

# -----------------------------------------------------------
# ⚙️ [헬퍼 3] API로 '설명' 값 가져오기 (원래 방식 복구 + 재시도)
# -----------------------------------------------------------
def api_get_note(page: Page, ip: str):
    """
    page.evaluate(fetch)를 사용하여 브라우저 세션으로 API를 호출합니다. (가장 확실한 방법)
    """
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=systemInfo&mode=1"
    print(f"[API] 'note' 값 조회 시도 (Browser Fetch)...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 브라우저 내부에서 fetch 실행
            response_text = page.evaluate(
                """
                async (url) => {
                    try {
                        const response = await fetch(url); 
                        if (!response.ok) {
                            return `Error: ${response.status} ${response.statusText}`;
                        }
                        return await response.text();
                    } catch (e) {
                        return `Error: ${e.message}`;
                    }
                }
                """, 
                api_url 
            )

            # 401 Unauthorized 체크
            if "Error: 401" in response_text:
                print(f"⚠️ [API] 401 Unauthorized (시도 {attempt+1}/{max_retries}). 페이지 새로고침 후 재시도...")
                page.reload()
                page.wait_for_selector("#Page200_id", timeout=15000)
                time.sleep(2)
                continue

            # 기타 에러 체크
            if response_text.startswith("Error:"):
                print(f"⚠️ [API] 호출 실패: {response_text}")
                time.sleep(2)
                continue

            # 파싱 및 반환
            data = parse_api_response(response_text)
            val = data.get("note", "")
            if val is None: val = "" # None 방어 코드
            
            print(f"[API] 조회 성공: note='{val}'")
            return val

        except Exception as e:
            print(f"⚠️ [API] 실행 중 에러: {e}")
            time.sleep(2)

    print("❌ [API] 최종 실패: 값을 가져오지 못했습니다.")
    return None

# -----------------------------------------------------------
# ⚙️ [헬퍼 4] UI로 '설명' 값 변경하기
# -----------------------------------------------------------
def ui_set_note(page: Page, new_note_value: str):
    NOTE_INPUT_SELECTOR = "#note"
    SAVE_BUTTON_SELECTOR = "#setup-apply"
    
    print(f"\n--- [액션] UI '설명' 값 변경 시작 ({new_note_value}) ---")
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        current_val = page.locator(NOTE_INPUT_SELECTOR).input_value()
        if current_val == new_note_value:
             print(f"✅ [액션] 이미 '{new_note_value}'입니다. 스킵.")
             return True

        page.locator(NOTE_INPUT_SELECTOR).fill(new_note_value)
        page.locator(NOTE_INPUT_SELECTOR).dispatch_event("input")
        page.locator(NOTE_INPUT_SELECTOR).dispatch_event("change")
        
        print("[액션] 저장 버튼 활성화 대기...")
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}:not([disabled])", timeout=5000)
        page.locator(SAVE_BUTTON_SELECTOR).click()
        
        print("[액션] 성공 팝업 처리...")
        handle_popup(page, button_index=0)
        
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}[disabled]", timeout=5000)
        print("✅ [액션] 저장 완료.")
        return True
    except Exception as e:
        print(f"❌ [액션] UI '설명' 값 변경 실패: {e}")
        return False

# -----------------------------------------------------------
# ⚙️ [헬퍼 5] API로 '언어' 값 가져오기 (원래 방식 복구)
# -----------------------------------------------------------
def api_get_language(page: Page, ip: str):
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=systemInfo&mode=1"
    try:
        response_text = page.evaluate(
            """
            async (url) => {
                try {
                    const response = await fetch(url); 
                    if (!response.ok) return `Error: ${response.status}`;
                    return await response.text();
                } catch (e) { return `Error: ${e.message}`; }
            }
            """, 
            api_url 
        )
        if not response_text.startswith("Error"):
            return parse_api_response(response_text).get("language")
        return None
    except Exception:
        return None

# -----------------------------------------------------------
# ⚙️ [헬퍼 6] UI로 '언어' 값 변경하기
# -----------------------------------------------------------
def ui_set_language(page: Page, language_value: str):
    LANGUAGE_DROPDOWN_SELECTOR = "#set-lang"
    SAVE_BUTTON_SELECTOR = "#setup-apply"
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        page.locator(LANGUAGE_DROPDOWN_SELECTOR).select_option(value=language_value)
        
        try:
            page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}:not([disabled])", timeout=3000)
            page.locator(SAVE_BUTTON_SELECTOR).click()
            handle_popup(page, button_index=0)
            page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}[disabled]", timeout=5000)
        except:
            pass
        return True
    except Exception as e:
        print(f"❌ [액션] 언어 변경 실패: {e}")
        return False

# -----------------------------------------------------------
# ⚙️ [헬퍼 7] 기본 설정 불러오기 (다국어 대응 + 세션 갱신)
# -----------------------------------------------------------
def load_default_settings(page: Page, strong_password: str = "qwerty0-"):
    SET_DEFAULT_BUTTON = "#set-default"
    
    print(f"\n--- [액션] '기본 설정 불러오기' 작업 시작 ---")

    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500) 
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        print("[액션] '기본 설정 불러오기' 버튼 클릭...")
        page.locator(SET_DEFAULT_BUTTON).click()

        print("[액션] 확인 팝업 처리...")
        confirm_dialog = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#load-default-setup-diag"))
        confirm_dialog.wait_for(state="visible", timeout=5000)

        network_chk = confirm_dialog.locator("#include-network-setup")
        if network_chk.is_visible() and network_chk.is_checked():
            print("[액션] 네트워크 설정 유지 (체크 해제)...")
            network_chk.uncheck()
        
        confirm_dialog.locator(DIALOG_BUTTONS).first.click()

        print("[액션] Warning 팝업 처리...")
        handle_popup(page, button_index=0)

        print("[액션] 비밀번호 재설정...")
        edit_user_dialog = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#edit-user-diag"))
        edit_user_dialog.wait_for(state="visible", timeout=5000)
        
        edit_user_dialog.locator("#edit-user-edit-passwd1").fill(strong_password)
        edit_user_dialog.locator("#edit-user-edit-passwd2").fill(strong_password)

        print("[액션] 이메일 설정 건너뛰기...")
        edit_user_dialog.locator("#edit-email_not_use").check()
        
        print("[액션] 이메일 경고 팝업 처리...")
        try:
            if page.locator(VISIBLE_DIALOG).count() > 1:
                warning_popup = page.locator(VISIBLE_DIALOG).last
                if warning_popup.is_visible(timeout=2000):
                    warning_popup.locator(DIALOG_BUTTONS).first.click()
                    warning_popup.wait_for(state="hidden", timeout=3000)
        except Exception:
            pass

        print("[액션] 비밀번호 설정 완료 (OK 클릭)...")
        edit_user_dialog.locator(DIALOG_BUTTONS).first.click()

        print("[액션] 최종 완료 팝업 대기 및 클릭...")
        handle_popup(page, button_index=0, timeout=15000)

        print("✅ [액션] 기본 설정 불러오기 완료.")

        print("🔄 [액션] 세션 갱신을 위해 페이지를 새로고침합니다...")
        page.reload()
        print("[액션] 페이지 로드 대기 중...")
        page.wait_for_selector("#Page200_id", timeout=15000)
        print("✅ [액션] 세션 갱신 완료.")

        return True

    except Exception as e:
        print(f"❌ [액션] 기본 설정 불러오기 실패: {e}")
        return False