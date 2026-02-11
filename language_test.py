"""
언어 테스트 모듈
- 전체 언어 변경 테스트 (19개 언어)
- 간결한 출력 및 명확한 진행 상황 표시
"""

import time
from typing import Optional, Tuple, Dict, List
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
# 📚 언어 데이터
# ===========================================================
LANGUAGE_MAP: List[Dict[str, str]] = [
    {"api": "english", "value": "1", "name": "English"},
    {"api": "korean", "value": "20", "name": "한국어"},
    {"api": "japanese", "value": "21", "name": "日本語"},
    {"api": "chinese-PRC", "value": "22", "name": "简体中文"},
    {"api": "chinese-Taiwan", "value": "23", "name": "繁體中文"},
    {"api": "french", "value": "2", "name": "Français"},
    {"api": "german", "value": "3", "name": "Deutsch"},
    {"api": "italian", "value": "4", "name": "Italiano"},
    {"api": "spanish", "value": "5", "name": "Español"},
    {"api": "dutch", "value": "7", "name": "Nederlands"},
    {"api": "polish", "value": "8", "name": "Polski"},
    {"api": "portuguese", "value": "9", "name": "Português"},
    {"api": "hungarian", "value": "11", "name": "Magyar"},
    {"api": "czech", "value": "12", "name": "Čeština"},
    {"api": "russian", "value": "13", "name": "Русский"},
    {"api": "danish", "value": "6", "name": "Dansk"},
    {"api": "swedish", "value": "10", "name": "Svenska"},
    {"api": "finnish", "value": "14", "name": "Suomi"},
    {"api": "turkish", "value": "15", "name": "Türkçe"},
    {"api": "croatian", "value": "31", "name": "Hrvatski"}
]

# 한국어 값 (복구용)
KOREAN_VALUE = "20"

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
# ⚙️ [내부 함수] 언어 전용 액션들 (개선됨)
# ===========================================================

def api_get_language(api_client: CameraApiClient, max_retries: int = None, silent: bool = False) -> Optional[str]:
    """API로 현재 언어 설정 조회 (재시도 포함)"""
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    
    for attempt in range(max_retries):
        try:
            data = api_client.get_system_info()
            if data and data.get("language"):
                return data.get("language")
            
            if attempt < max_retries - 1:
                if not silent:
                    print_warning(f"언어 조회 실패 ({attempt + 1}/{max_retries}), 재시도 중...")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
        except Exception as e:
            if attempt < max_retries - 1:
                if not silent:
                    print_warning(f"언어 조회 에러 ({attempt + 1}/{max_retries}): {e}")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
    
    if not silent:
        print_error("언어 조회 최종 실패")
    return None

def verify_language_value(api_client: CameraApiClient, expected_language: str,
                         max_retries: int = None, timeout: float = None, silent: bool = False) -> bool:
    """언어 값 검증 (재시도 포함)"""
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 5)
    if timeout is None:
        timeout = TIMEOUTS.get("api_request", 10) * max_retries
    
    start_time = time.time()
    
    for attempt in range(max_retries):
        if time.time() - start_time > timeout:
            if not silent:
                print_error(f"타임아웃 ({timeout}초 초과)")
            return False
        
        current_language = api_get_language(api_client, max_retries=1, silent=True)
        
        if current_language == expected_language:
            return True
        
        if attempt < max_retries - 1:
            if not silent:
                print_warning(f"불일치 (실제: '{current_language}'), 재시도 {attempt + 1}/{max_retries}")
            time.sleep(TIMEOUTS.get("retry_delay", 2))
        else:
            if not silent:
                print_error(f"검증 실패: 기대='{expected_language}', 실제='{current_language}'")
    
    return False

def ui_set_language(page: Page, language_value: str, silent: bool = False) -> bool:
    """UI에서 언어 설정 변경"""
    try:
        if not navigate_to_system_general(page):
            return False
        
        lang_select = page.locator("#set-lang")
        lang_select.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        # 현재 선택된 값 확인
        try:
            current_value = lang_select.input_value()
            if current_value == language_value:
                if not silent:
                    print_success("이미 선택된 언어")
                return True
        except:
            pass
        
        lang_select.select_option(value=language_value)
        
        save_btn = page.locator("#setup-apply")
        save_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        if not save_btn.is_disabled():
            save_btn.click()
            
            if handle_popup(page, timeout=TIMEOUTS.get("popup", 5000)):
                try:
                    save_btn.wait_for(state="disabled", timeout=TIMEOUTS.get("popup", 5000))
                except:
                    pass
                
                if not silent:
                    print_success("언어 변경 완료")
                return True
            else:
                if not silent:
                    print_error("저장 실패 (팝업 없음)")
                return False
        else:
            if not silent:
                print_success("이미 저장됨")
            return True
            
    except Exception as e:
        if not silent:
            print_error(f"언어 변경 실패: {e}")
        return False

def get_language_name(language_api_value: str) -> str:
    """
    언어 API 값을 언어 이름으로 변환
    
    Args:
        language_api_value: 언어 API 값 (예: "korean")
    
    Returns:
        언어 이름 (예: "한국어") 또는 원래 값
    """
    for lang in LANGUAGE_MAP:
        if lang["api"] == language_api_value:
            return lang["name"]
    return language_api_value

# ===========================================================
# ⚙️ [테스트 케이스] (개선됨)
# ===========================================================

def run_all_languages_test(page: Page, api_client: CameraApiClient) -> Tuple[bool, str]:
    """전체 언어 변경 테스트 (19개 언어)"""
    total = len(LANGUAGE_MAP)
    failed_count = 0
    failed_languages: List[str] = []
    success_count = 0
    
    for idx, lang in enumerate(LANGUAGE_MAP, 1):
        target_api_val = lang["api"]
        target_ui_val = lang["value"]
        language_name = lang["name"]
        
        print_step(idx, total, f"{language_name}")
        
        # UI 설정 변경
        print_action(f"언어 변경: {language_name}")
        if not ui_set_language(page, target_ui_val, silent=True):
            print_error("UI 설정 실패")
            failed_count += 1
            failed_languages.append(language_name)
            continue
        
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # API 검증
        print_action("API 검증 중...")
        if verify_language_value(api_client, target_api_val, max_retries=5, silent=True):
            print_success("성공")
            success_count += 1
        else:
            print_error("검증 실패")
            failed_count += 1
            failed_languages.append(language_name)
        
        if idx < total:
            time.sleep(1)
    
    # 한국어로 복구
    print(f"\n{'='*60}")
    print("🔄 한국어로 복구 중...")
    print(f"{'='*60}")
    
    if ui_set_language(page, KOREAN_VALUE, silent=True):
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        if verify_language_value(api_client, "korean", max_retries=3, silent=True):
            print_success("한국어 복구 완료")
        else:
            print_warning("한국어 복구 검증 실패")
    else:
        print_error("한국어 복구 실패")
    
    # 결과 요약
    print(f"\n{'='*60}")
    print("📊 테스트 결과")
    print(f"{'='*60}")
    print(f"✅ 성공: {success_count}/{total}")
    print(f"❌ 실패: {failed_count}/{total}")
    
    if failed_languages:
        print(f"\n실패한 언어: {', '.join(failed_languages)}")
    
    print(f"{'='*60}")
    
    if failed_count == 0:
        return True, f"언어 테스트 완료 ({success_count}/{total})"
    else:
        return False, f"언어 테스트 실패 ({success_count}/{total})"

def run_single_language_test(page: Page, api_client: CameraApiClient, 
                            language_api_value: str) -> Tuple[bool, str]:
    """단일 언어 변경 테스트"""
    # 언어 정보 찾기
    lang_info = None
    for lang in LANGUAGE_MAP:
        if lang["api"] == language_api_value:
            lang_info = lang
            break
    
    if not lang_info:
        return False, f"지원하지 않는 언어: {language_api_value}"
    
    language_name = lang_info["name"]
    target_ui_val = lang_info["value"]
    total_steps = 2
    
    try:
        # Step 1: UI 설정 변경
        print_step(1, total_steps, f"UI 언어 변경 → {language_name}")
        if not ui_set_language(page, target_ui_val):
            raise Exception("UI 설정 실패")
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # Step 2: API 검증
        print_step(2, total_steps, "API 검증")
        if not verify_language_value(api_client, language_api_value, max_retries=5):
            raise Exception("API 검증 실패")
        
        return True, f"{language_name} 테스트 성공"
        
    except Exception as e:
        return False, str(e)
