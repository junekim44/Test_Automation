import os
import time
from playwright.sync_api import Page

# -----------------------------------------------------------
# ⚙️ 1. 설정 내보내기 및 검증 모듈
# -----------------------------------------------------------
def export_and_verify_settings(page: Page, save_as="registry.dat"):
    """
    카메라 설정 페이지에서 '설정 내보내기'를 수행하고,
    파일이 정상적으로 다운로드되었는지 검증합니다.
    """
    
    print(f"\n--- [모듈] 설정 내보내기 작업 시작 ---")
    
    if os.path.exists(save_as):
        os.remove(save_as)
        print(f"[모듈] 기존 파일 '{save_as}' 삭제 완료.")

    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500) 
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)

        print(f"[모듈] 다운로드({save_as}) 대기 시작...")
        with page.expect_download() as download_info:
            print("[모듈] '설정 내보내기'(#reg-export) 클릭...")
            page.locator("#reg-export").click()
        
        download = download_info.value
        download.save_as(save_as)
        print(f"[모듈] 파일 저장 완료: {save_as}")

        if os.path.exists(save_as) and os.path.getsize(save_as) > 0:
            file_size = os.path.getsize(save_as)
            print(f"✅ [모듈] 검증 성공! (크기: {file_size} bytes)")
            return True, save_as
        else:
            print(f"❌ [모듈] 검증 실패! (파일이 없거나 크기가 0임)")
            return False, "파일이 없거나 크기가 0입니다."

    except Exception as e:
        print(f"❌ [모듈] 내보내기 오류: {e}")
        return False, str(e)

# -----------------------------------------------------------
# ⚙️ 2. 설정 불러오기 모듈 (expect_file_chooser 사용)
# -----------------------------------------------------------
def import_settings_and_reboot(page: Page, file_path="registry.dat"):
    """
    '설정 불러오기' 버튼 클릭 시 나타나는 "파일 선택창" 이벤트를 감지,
    파일을 주입하고, "네트워크 설정" 팝업에서 '아니오'를 클릭합니다.
    """
    
    # ⭐️ '설정 불러오기' 버튼 ID
    IMPORT_BUTTON_SELECTOR = "#reg-import"
    
    # os.path.abspath() : 파일의 '절대 경로'를 가져옵니다.
    # 파일 선택창은 상대 경로를 인식하지 못할 수 있으므로 절대 경로가 안전합니다.
    absolute_file_path = os.path.abspath(file_path)
    print(f"파일 절대 경로: {absolute_file_path}")
    
    print(f"\n--- [모듈] 설정 불러오기 작업 시작 ---")
    
    try:
        # 1. '시스템' -> '일반' 메뉴 이동
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        # 2. "파일 선택창"이 열릴 것을 미리 대기합니다.
        #    이 코드는 반드시 '클릭'보다 *먼저* 실행되어야 합니다.
        print(f"[모듈] '파일 선택창' 열기 이벤트 대기...")
        with page.expect_file_chooser() as fc_info:
            
            # 3. '설정 불러오기' 버튼을 클릭 (이때 파일 선택창이 열림)
            print(f"[모듈] '{IMPORT_BUTTON_SELECTOR}' 버튼 클릭 (파일창 열기)...")
            page.locator(IMPORT_BUTTON_SELECTOR).click() 
        
        # 4. (실제 창은 안 뜸) Playwright가 감지한 파일 선택창에
        #    파일의 '절대 경로'를 설정(선택)합니다.
        print(f"[모듈] 감지된 파일 선택창에 '{absolute_file_path}' 경로 주입...")
        file_chooser = fc_info.value
        file_chooser.set_files(absolute_file_path)
        
        # ----------------------------------------------------

        # 5. (파일이 선택됨) "네트워크 설정 포함?" 팝업이 뜰 때까지 대기
        print("[모듈] '네트워크 설정 포함?' 팝업창 대기 중...")
        page.wait_for_selector("text=네트워크 설정 포함?", timeout=5000)
        
        # 6. 팝업창의 '아니오' 버튼 클릭
        print("[모듈] 팝업창의 '아니오' 버튼 클릭...")
        page.get_by_role("button", name="아니오").click()
        
        print("✅ [모듈] 불러오기 명령 전송됨.")
        return True, "설정 불러오기 완료"

    except Exception as e:
        print(f"❌ [모듈] 불러오기 중 오류: {e}")
        return False, str(e)

# -----------------------------------------------------------
# ⚙️ 3. API로 '설명' 값 가져오기 모듈
# -----------------------------------------------------------
def api_get_note(page: Page, ip: str):
    """
    Playwright의 page.evaluate를 사용해 브라우저 내부의 fetch로 API를 호출합니다.
    이 방식은 requests 라이브러리 없이, 이미 인증된 브라우저 세션을 사용합니다.
    
    :param page: (필수) 이미 로그인된 Playwright의 Page 객체
    :param ip: (필수) 카메라 IP
    """
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=systemInfo&mode=1"
    print(f"[API] 브라우저 세션으로 API 'note' 값 확인 시도: {api_url}")
    
    try:
        # page.evaluate를 사용해 브라우저 컨텍스트에서 JavaScript fetch 실행
        response_text = page.evaluate(
            """
            async (url) => {
                try {
                    // 브라우저에 내장된 fetch는 이미 인증된 세션을 사용
                    const response = await fetch(url); 
                    if (!response.ok) {
                        // 401 오류 등을 여기서 잡아서 Python으로 반환
                        return `Error: ${response.status} ${response.statusText}`;
                    }
                    return await response.text();
                } catch (e) {
                    return `Error: ${e.message}`;
                }
            }
            """, 
            api_url # 'url' 파라미터로 이 값을 전달
        )

        if response_text.startswith("Error:"):
            print(f"[API] 'note' 값 확인 실패 (fetch): {response_text}")
            return None

        # 'note=' 값 파싱 (기존 로직과 동일)
        for line in response_text.split('&'):
            if line.startswith("note="):
                note_value = line.split('=', 1)[1] 
                print(f"[API] 현재 'note' 값 확인: {note_value}")
                return note_value
        return "" # 'note='는 있지만 값이 없는 경우

    except Exception as e:
        print(f"[API] 'note' 값 확인 실패 (evaluate): {e}")
        return None

# -----------------------------------------------------------
# ⚙️ 4. UI로 '설명' 값 변경하기 모듈 (ID 적용 완료)
# -----------------------------------------------------------
def ui_set_note(page: Page, new_note_value: str):
    """
    UI에서 '설명' 필드 값을 변경하고 저장합니다.
    """
    # ⭐️ HTML에서 찾은 ID 적용
    NOTE_INPUT_SELECTOR = "#note"
    SAVE_BUTTON_SELECTOR = "#setup-apply"
    
    print(f"\n--- [모듈] UI '설명' 값 변경 시작 ---")
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        # .fill() 대신 .clear() 후 .type()으로 변경
        print(f"[모듈] '설명' 필드를 비웁니다...")
        page.locator(NOTE_INPUT_SELECTOR).clear()
        
        print(f"[모듈] '설명' 필드에 '{new_note_value}'를 (타이핑) 입력합니다...")
        page.locator(NOTE_INPUT_SELECTOR).type(new_note_value)

        # '저장' 버튼이 '활성화' 상태가 될 때까지 최대 5초간 기다립니다.
        print("[모듈] '저장' 버튼이 활성화되기를 대기 중...")
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}:not([disabled])", timeout=5000)

        print("[모듈] '저장' 버튼 클릭...")
        page.locator(SAVE_BUTTON_SELECTOR).click()

        # "성공" 팝업창이 뜰 때까지 대기
        print("[모듈] '성공' 팝업창 대기 중...")
        # 이미지에 보이는 "성공" 텍스트를 기다립니다.
        page.wait_for_selector("text=성공", timeout=5000)

        # 팝업창의 '확인' 버튼 클릭 (ID가 동적이므로 Role Selector 사용)
        print("[모듈] 팝업창의 '확인' 버튼 클릭...")
        page.get_by_role("button", name="확인").click()
        
        # '확인'을 누르면 '저장' 버튼이 다시 비활성화(disabled) 상태로 돌아갈 것임
        print("[모듈] '저장' 버튼이 다시 비활성화되기를 대기 중...")
        page.wait_for_selector(f"{SAVE_BUTTON_SELECTOR}[disabled]", timeout=5000)
        # ----------------------------------------------------


        print("✅ [모듈] '설명' 값 변경 및 저장 완료.")
        return True
    
    except Exception as e:
        print(f"❌ [모듈] UI '설명' 값 변경 실패: {e}")
        return False