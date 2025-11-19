import time
from playwright.sync_api import Page
# common_actions에 있는 로직을 활용하는 것이 좋습니다.
from common_actions import parse_api_response, handle_popup

# -----------------------------------------------------------
# 📚 언어 데이터
# -----------------------------------------------------------
LANGUAGE_MAP = [
    {"api": "english", "value": "1"},
    {"api": "korean", "value": "20"},
    {"api": "japanese", "value": "21"},
    {"api": "chinese-PRC", "value": "22"},
    {"api": "chinese-Taiwan", "value": "23"},
    {"api": "french", "value": "2"},
    {"api": "german", "value": "3"},
    {"api": "italian", "value": "4"},
    {"api": "spanish", "value": "5"},
    {"api": "dutch", "value": "7"},
    {"api": "polish", "value": "8"},
    {"api": "portuguese", "value": "9"},
    {"api": "hungarian", "value": "11"},
    {"api": "czech", "value": "12"},
    {"api": "russian", "value": "13"},
    {"api": "danish", "value": "6"},
    {"api": "swedish", "value": "10"},
    {"api": "finnish", "value": "14"},
    {"api": "turkish", "value": "15"},
    {"api": "croatian", "value": "31"}
]

# ===========================================================
# ⚙️ [내부 함수] 언어 전용 액션들
# ===========================================================
def api_get_language(page: Page, ip: str):
    """
    API로 현재 언어 설정 조회 (재시도 로직 포함)
    """
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=systemInfo&mode=1"
    
    # API 호출 자체가 실패할 경우를 대비해 내부 재시도 추가
    for _ in range(3):
        try:
            response_text = page.evaluate("""async (url) => {
                try {
                    const response = await fetch(url);
                    if (!response.ok) return `Error`;
                    return await response.text();
                } catch (e) { return `Error`; }
            }""", api_url)
            
            if "Error" not in response_text:
                return parse_api_response(response_text).get("language")
        except:
            pass
        time.sleep(1)
        
    return None

def ui_set_language(page: Page, language_value: str):
    try:
        page.locator("#Page200_id").click()
        page.locator("#Page201_id").click()
        page.wait_for_timeout(500)
        
        # 값 선택
        page.locator("#set-lang").select_option(value=language_value)
        
        # 저장 버튼 처리
        save_btn = page.locator("#setup-apply")
        try:
            # 버튼이 활성화될 때까지 잠시 대기
            save_btn.wait_for(state="visible", timeout=2000)
            
            # 버튼이 활성화(disabled가 아님) 상태라면 클릭
            if not save_btn.is_disabled():
                save_btn.click()
                # 팝업 처리
                handle_popup(page)
                
                # ⭐️ 중요: 저장 후 처리가 완료될 시간을 줌
                save_btn.wait_for(state="disabled", timeout=5000)
        except:
            # 이미 해당 언어라 버튼이 비활성화된 경우 등
            pass
            
        return True
    except:
        return False

# ===========================================================
# ⚙️ [테스트 케이스]
# ===========================================================
def run_all_languages_test(page: Page, camera_ip: str):
    print("\n--- [TC 2] 전체 언어 변경 테스트 ---")
    
    failed_count = 0
    
    for lang in LANGUAGE_MAP:
        target_api_val = lang["api"]
        target_ui_val = lang["value"]
        
        # 1. UI 설정 변경
        if not ui_set_language(page, target_ui_val):
            print(f"🔥 UI 설정 실패: {target_api_val}")
            failed_count += 1
            continue
            
        # 2. API 검증 (⭐️ Retry 로직 추가: 값이 반영될 때까지 기다림)
        is_matched = False
        current_val = ""
        
        # 최대 5번 확인 (약 10초 대기)
        for i in range(5):
            current_val = api_get_language(page, camera_ip)
            
            if current_val == target_api_val:
                is_matched = True
                break # 값이 맞으면 즉시 탈출
            
            # 값이 아직 안 바뀌었으면 잠시 대기
            time.sleep(2)
            
        # 3. 결과 출력
        if is_matched:
            print(f"✅ {target_api_val} 성공")
        else:
            print(f"❌ {target_api_val} 실패 (실제: {current_val})")
            failed_count += 1
            
    # 테스트 종료 후 한국어로 복구
    print("\n[복구] 테스트 종료. 한국어로 복구합니다.")
    ui_set_language(page, "20")
    
    if failed_count == 0:
        return True, "언어 테스트 완료 (성공)"
    else:
        return False, f"언어 테스트 실패 ({failed_count}개 항목)"