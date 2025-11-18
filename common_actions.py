import os
import time
from playwright.sync_api import Page

VISIBLE_DIALOG_SELECTOR = 'div.ui-dialog[style*="display: block"]'

# -----------------------------------------------------------
# ⚙️ [헬퍼 1] 설정 내보내기
# -----------------------------------------------------------
def export_and_verify_settings(page: Page, save_as="registry.dat"):
    """
    카메라 설정 페이지에서 '설정 내보내기'를 수행하고,
    파일이 정상적으로 다운로드되었는지 검증합니다.
    """
    
    print(f"\n--- [액션] 설정 내보내기 작업 시작 ---")
    
    if os.path.exists(save_as):
        os.remove(save_as)
        print(f"[액션] 기존 파일 '{save_as}' 삭제 완료.")

    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500) 
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        print(f"[액션] 다운로드({save_as}) 대기 시작...")
        with page.expect_download() as download_info:
            print("[액션] '설정 내보내기'(#reg-export) 클릭...")
            page.locator("#reg-export").click()
        
        download = download_info.value
        download.save_as(save_as)
        print(f"[액션] 파일 저장 완료: {save_as}")

        if os.path.exists(save_as) and os.path.getsize(save_as) > 0:
            file_size = os.path.getsize(save_as)
            print(f"✅ [액션] 검증 성공! (크기: {file_size} bytes)")
            return True, save_as
        else:
            print(f"❌ [액션] 검증 실패! (파일이 없거나 크기가 0임)")
            return False, "파일이 없거나 크기가 0입니다."

    except Exception as e:
        print(f"❌ [액션] 내보내기 오류: {e}")
        return False, str(e)

# -----------------------------------------------------------
# ⚙️ [헬퍼 2] 설정 불러오기
# -----------------------------------------------------------
def import_settings_and_reboot(page: Page, file_path="registry.dat"):
    """
    '설정 불러오기' 버튼 클릭 시 나타나는 "파일 선택창" 이벤트를 감지,
    파일을 주입하고, "네트워크 설정" 팝업에서 '아니오'를 클릭합니다.
    """
    
    FILE_INPUT_SELECTOR = "#importFileToRead" 
    IMPORT_BUTTON_SELECTOR = "#reg-import" # ID 오타 수정 (reg-imprt -> reg-import)
    
    # os.path.abspath() : 파일의 '절대 경로'를 가져옵니다.
    absolute_file_path = os.path.abspath(file_path)
    print(f"파일 절대 경로: {absolute_file_path}")
    
    print(f"\n--- [액션] 설정 불러오기 작업 시작 ---")
    
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        # 1. "파일 선택창"이 열릴 것을 미리 대기합니다.
        print(f"[액션] '파일 선택창' 열기 이벤트 대기...")
        with page.expect_file_chooser() as fc_info:
            
            # 2. '설정 불러오기' 버튼을 클릭 (이때 파일 선택창이 열림)
            print(f"[액션] '{IMPORT_BUTTON_SELECTOR}' 버튼 클릭 (파일창 열기)...")
            page.locator(IMPORT_BUTTON_SELECTOR).click() 
        
        # 3. Playwright가 감지한 파일 선택창에 파일의 '절대 경로'를 설정
        print(f"[액션] 감지된 파일 선택창에 '{absolute_file_path}' 경로 주입...")
        file_chooser = fc_info.value
        file_chooser.set_files(absolute_file_path)
        
        # 4. "네트워크 설정 포함?" 팝업이 뜰 때까지 대기
        print("[액션] '네트워크 설정 포함?' 팝업창 대기 중...")
        page.wait_for_selector("text=네트워크 설정 포함?", timeout=5000)
        
        # 5. 팝업창의 '아니오' 버튼 클릭
        print("[액션] 팝업창의 '아니오' 버튼 클릭...")
        page.get_by_role("button", name="아니오").click()
        
        print("✅ [액션] 불러오기 명령 전송됨.")
        return True, "설정 불러오기 완료"

    except Exception as e:
        print(f"❌ [액션] 불러오기 중 오류: {e}")
        return False, str(e)

# -----------------------------------------------------------
# ⚙️ [헬퍼 3] API로 '설명' 값 가져오기
# -----------------------------------------------------------
def api_get_note(page: Page, ip: str):
    """
    Playwright의 page.evaluate를 사용해 브라우저 내부의 fetch로 API를 호출합니다.
    """
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=systemInfo&mode=1"
    print(f"[API] 브라우저 세션으로 API 'note' 값 확인 시도: {api_url}")
    
    try:
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

        if response_text.startswith("Error:"):
            print(f"[API] 'note' 값 확인 실패 (fetch): {response_text}")
            return None

        for line in response_text.split('&'):
            if line.startswith("note="):
                note_value = line.split('=', 1)[1] 
                print(f"[API] 현재 'note' 값 확인: {note_value}")
                return note_value
        return "" 

    except Exception as e:
        print(f"[API] 'note' 값 확인 실패 (evaluate): {e}")
        return None

# -----------------------------------------------------------
# ⚙️ [헬퍼 4] UI로 '설명' 값 변경하기
# -----------------------------------------------------------
def ui_set_note(page: Page, new_note_value: str):
    """
    UI에서 '설명' 필드 값을 변경하고 저장합니다.
    """
    NOTE_INPUT_SELECTOR = "#note"
    SAVE_BUTTON_SELECTOR = "#setup-apply"
    
    print(f"\n--- [액션] UI '설명' 값 변경 시작 ---")
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        page.locator(NOTE_INPUT_SELECTOR).clear()
        page.locator(NOTE_INPUT_SELECTOR).type(new_note_value)
        page.locator(NOTE_INPUT_SELECTOR).dispatch_event("input")
        page.wait_for_timeout(100)
        page.locator(NOTE_INPUT_SELECTOR).dispatch_event("change")
        
        print("[액션] '저장' 버튼이 활성화되기를 대기 중...")
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}:not([disabled])", timeout=5000)

        print("[액션] '저장' 버튼에 'click' 이벤트를 수동으로 발생시킵니다...")
        page.locator(SAVE_BUTTON_SELECTOR).dispatch_event("click")
        
        print("[액션] '성공/Success' 팝업창(Dialog) 대기 중...")
        # 현재 활성화된(보이는) 팝업창을 찾음
        visible_dialog = page.locator(VISIBLE_DIALOG_SELECTOR)
        visible_dialog.wait_for(timeout=5000)
        
        print("[액션] 팝업창의 'OK/확인' 버튼 클릭...")
        # 그 팝업창 내부에 있는 버튼(유일한 버튼)을 클릭
        visible_dialog.get_by_role("button").click()

        print("[액션] '저장' 버튼이 다시 비활성화되기를 대기 중...")
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}[disabled]", timeout=5000)
        
        print("✅ [액션] '설명' 값 변경 및 저장 완료.")
        return True
    
    except Exception as e:
        print(f"❌ [액션] UI '설명' 값 변경 실패: {e}")
        return False

# -----------------------------------------------------------
# ⚙️ [헬퍼 5] API로 '언어' 값 가져오기
# -----------------------------------------------------------
def api_get_language(page: Page, ip: str):
    """
    systemInfo API를 호출하여 현재 'language' 값을 반환합니다.
    """
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=systemInfo&mode=1"
    print(f"[API] 브라우저 세션으로 API 'language' 값 확인 시도...")
    
    try:
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

        if response_text.startswith("Error:"):
            print(f"[API] 'language' 값 확인 실패 (fetch): {response_text}")
            return None

        for line in response_text.split('&'):
            if line.startswith("language="):
                lang_value = line.split('=', 1)[1] 
                print(f"[API] 현재 'language' 값 확인: {lang_value}")
                return lang_value
        return None 

    except Exception as e:
        print(f"[API] 'language' 값 확인 실패 (evaluate): {e}")
        return None

# -----------------------------------------------------------
# ⚙️ [헬퍼 6] UI로 '언어' 값 변경하기
# -----------------------------------------------------------
# -----------------------------------------------------------
# ⚙️ [헬퍼 6] UI로 '언어' 값 변경하기 (⭐️수정됨⭐️)
# -----------------------------------------------------------
def ui_set_language(page: Page, language_value: str):
    """
    UI에서 '언어' 드롭다운 값을 <option>의 'value' 속성을 이용해 변경하고 저장합니다.
    (이 방식은 언어와 독립적입니다)
    """
    LANGUAGE_DROPDOWN_SELECTOR = "#set-lang"
    SAVE_BUTTON_SELECTOR = "#setup-apply"
    VISIBLE_DIALOG_SELECTOR = 'div.ui-dialog[style*="display: block"]'
    
    print(f"\n--- [액션] UI '언어' 값을 'value={language_value}'로 변경 시작 ---")
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        # ⭐️ [수정] label= 대신 value= 사용
        print(f"[액션] 드롭다운에서 'value={language_value}' 선택...")
        page.locator(LANGUAGE_DROPDOWN_SELECTOR).select_option(value=language_value)
        
        print("[액션] '저장' 버튼이 활성화되기를 대기 중...")
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}:not([disabled])", timeout=5000)

        print("[액션] '저장' 버튼에 'click' 이벤트를 수동으로 발생시킵니다...")
        page.locator(SAVE_BUTTON_SELECTOR).dispatch_event("click")
        
        print("[액션] '성공/Success' 팝업창(Dialog) 대기 중...")
        visible_dialog = page.locator(VISIBLE_DIALOG_SELECTOR)
        visible_dialog.wait_for(timeout=5000)
        
        print("[액션] 팝업창의 'OK/확인' 버튼 클릭...")
        visible_dialog.get_by_role("button").click()

        print("[액션] '저장' 버튼이 다시 비활성화되기를 대기 중...")
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}[disabled]", timeout=5000)
        
        print(f"✅ [액션] '언어' 값 'value={language_value}'로 변경 및 저장 완료.")
        return True
    
    except Exception as e:
        print(f"❌ [액션] UI '언어' 값 'value={language_value}'로 변경 실패: {e}")
        return False
    
    except Exception as e:
        print(f"❌ [액션] UI '언어' 값 변경 실패: {e}")
        return False