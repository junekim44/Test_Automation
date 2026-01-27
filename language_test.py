"""
개선된 언어 테스트 모듈
- config.py를 사용한 설정값 관리
- api_client.py를 사용한 통합 API 호출
- 중복 코드 제거 및 로직 개선
"""

import time
from typing import Optional, Tuple, Dict, List
from playwright.sync_api import Page
from common_actions import handle_popup
from config import TIMEOUTS
from api_client import CameraApiClient

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
    """
    시스템 > 일반 메뉴로 이동 (공통 네비게이션)
    
    Args:
        page: Playwright Page 객체
    
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
# ⚙️ [내부 함수] 언어 전용 액션들 (개선됨)
# ===========================================================

def api_get_language(api_client: CameraApiClient, max_retries: int = None) -> Optional[str]:
    """
    API로 현재 언어 설정 조회 (개선된 버전 - 재시도 로직 포함)
    
    Args:
        api_client: CameraApiClient 인스턴스
        max_retries: 최대 재시도 횟수 (None이면 TIMEOUTS 사용)
    
    Returns:
        언어 값 (예: "korean", "english") 또는 None
    """
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 3)
    
    for attempt in range(max_retries):
        try:
            data = api_client.get_system_info()
            
            if data:
                language = data.get("language")
                if language:
                    return language
            else:
                if attempt < max_retries - 1:
                    print(f"⚠️ [API] 언어 조회 실패 (시도 {attempt + 1}/{max_retries}). 재시도...")
                    time.sleep(TIMEOUTS.get("retry_delay", 2))
                else:
                    print("❌ [API] 언어 조회 최종 실패")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ [API] 언어 조회 에러 (시도 {attempt + 1}/{max_retries}): {e}")
                time.sleep(TIMEOUTS.get("retry_delay", 2))
            else:
                print(f"❌ [API] 언어 조회 최종 에러: {e}")
    
    return None

def verify_language_value(api_client: CameraApiClient, expected_language: str,
                         max_retries: int = None, timeout: float = None) -> bool:
    """
    언어 값 검증 (재시도 로직 포함)
    
    Args:
        api_client: CameraApiClient 인스턴스
        expected_language: 기대하는 언어 값 (예: "korean", "english")
        max_retries: 최대 재시도 횟수
        timeout: 전체 타임아웃 (초)
    
    Returns:
        검증 성공 여부
    """
    if max_retries is None:
        max_retries = TIMEOUTS.get("max_retries", 5)  # 언어 변경은 시간이 더 걸릴 수 있음
    if timeout is None:
        timeout = TIMEOUTS.get("api_request", 10) * max_retries
    
    start_time = time.time()
    
    for attempt in range(max_retries):
        # 타임아웃 체크
        if time.time() - start_time > timeout:
            print(f"❌ [Verify] 타임아웃 ({timeout}초 초과)")
            return False
        
        current_language = api_get_language(api_client, max_retries=1)
        
        if current_language == expected_language:
            return True
        else:
            if attempt < max_retries - 1:
                wait_time = TIMEOUTS.get("retry_delay", 2)
                print(f"⚠️ [Verify] 불일치 (시도 {attempt + 1}/{max_retries}). "
                      f"기대: '{expected_language}', 실제: '{current_language}'. {wait_time}초 후 재시도...")
                time.sleep(wait_time)
            else:
                print(f"❌ [Verify] 최종 실패. 기대: '{expected_language}', 실제: '{current_language}'")
    
    return False

def ui_set_language(page: Page, language_value: str) -> bool:
    """
    UI에서 언어 설정 변경 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        language_value: 언어 값 (예: "20" = 한국어)
    
    Returns:
        성공 여부
    """
    try:
        # 메뉴 이동
        if not navigate_to_system_general(page):
            return False
        
        # 언어 선택 드롭다운 찾기
        lang_select = page.locator("#set-lang")
        lang_select.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        # 현재 선택된 값 확인
        try:
            current_value = lang_select.input_value()
            if current_value == language_value:
                print(f"[UI] 이미 선택된 언어입니다. 변경 스킵.")
                return True
        except:
            pass  # 현재 값 확인 실패해도 계속 진행
        
        # 언어 선택
        print(f"[UI] 언어 변경: {language_value}")
        lang_select.select_option(value=language_value)
        
        # 저장 버튼 처리
        save_btn = page.locator("#setup-apply")
        save_btn.wait_for(state="visible", timeout=TIMEOUTS.get("selector", 10000))
        
        # 버튼이 활성화되어 있으면 클릭
        if not save_btn.is_disabled():
            save_btn.click()
            
            # 팝업 처리
            if handle_popup(page, timeout=TIMEOUTS.get("popup", 5000)):
                # 저장 완료 대기 (버튼이 비활성화될 때까지)
                try:
                    save_btn.wait_for(state="disabled", timeout=TIMEOUTS.get("popup", 5000))
                except:
                    pass  # 비활성화 안되어도 저장은 완료될 수 있음
                
                print("[UI] 언어 변경 저장 완료.")
                return True
            else:
                print("❌ [UI] 저장 실패 (팝업 안뜸).")
                return False
        else:
            # 이미 저장된 상태
            print("[UI] 버튼이 비활성화되어 있습니다 (이미 저장됨).")
            return True
            
    except Exception as e:
        print(f"❌ [UI] 언어 변경 에러: {e}")
        import traceback
        traceback.print_exc()
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
    """
    전체 언어 변경 테스트 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        api_client: CameraApiClient 인스턴스
    
    Returns:
        (성공 여부, 메시지) 튜플
    """
    print("\n" + "="*60)
    print("--- [TC 2] 전체 언어 변경 테스트 ---")
    print("="*60)
    print(f"총 {len(LANGUAGE_MAP)}개 언어 테스트 시작...\n")
    
    failed_count = 0
    failed_languages: List[str] = []
    success_count = 0
    
    for idx, lang in enumerate(LANGUAGE_MAP, 1):
        target_api_val = lang["api"]
        target_ui_val = lang["value"]
        language_name = lang["name"]
        
        print(f"[{idx}/{len(LANGUAGE_MAP)}] {language_name} ({target_api_val}) 테스트 중...")
        
        # 1. UI 설정 변경
        if not ui_set_language(page, target_ui_val):
            print(f"   ❌ UI 설정 실패: {language_name}")
            failed_count += 1
            failed_languages.append(language_name)
            continue
        
        # 언어 변경 반영 대기 (언어 변경은 페이지 리로드가 필요할 수 있음)
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # 2. API 검증 (재시도 로직 포함)
        print(f"   -> API 검증 중...")
        if verify_language_value(api_client, target_api_val, max_retries=5):
            print(f"   ✅ {language_name} 성공")
            success_count += 1
        else:
            print(f"   ❌ {language_name} 실패")
            failed_count += 1
            failed_languages.append(language_name)
        
        # 다음 언어 테스트 전 잠시 대기
        if idx < len(LANGUAGE_MAP):
            time.sleep(1)
    
    # 테스트 종료 후 한국어로 복구
    print("\n" + "-"*60)
    print("[복구] 테스트 종료. 한국어로 복구합니다...")
    if ui_set_language(page, KOREAN_VALUE):
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        if verify_language_value(api_client, "korean", max_retries=3):
            print("✅ 한국어 복구 성공")
        else:
            print("⚠️ 한국어 복구 검증 실패 (수동 확인 필요)")
    else:
        print("❌ 한국어 복구 실패 (수동 확인 필요)")
    
    # 결과 요약
    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)
    print(f"✅ 성공: {success_count}/{len(LANGUAGE_MAP)}")
    print(f"❌ 실패: {failed_count}/{len(LANGUAGE_MAP)}")
    
    if failed_languages:
        print(f"\n실패한 언어: {', '.join(failed_languages)}")
    
    print("="*60)
    
    if failed_count == 0:
        return True, f"언어 테스트 완료 (성공: {success_count}/{len(LANGUAGE_MAP)})"
    else:
        return False, f"언어 테스트 실패 (성공: {success_count}/{len(LANGUAGE_MAP)}, 실패: {failed_count})"

def run_single_language_test(page: Page, api_client: CameraApiClient, 
                            language_api_value: str) -> Tuple[bool, str]:
    """
    단일 언어 변경 테스트 (개선된 버전)
    
    Args:
        page: Playwright Page 객체
        api_client: CameraApiClient 인스턴스
        language_api_value: 테스트할 언어 API 값 (예: "korean", "english")
    
    Returns:
        (성공 여부, 메시지) 튜플
    """
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
    
    print(f"\n--- 단일 언어 테스트: {language_name} ({language_api_value}) ---")
    
    try:
        # 1. UI 설정 변경
        print(f"[Step 1] UI 언어 변경...")
        if not ui_set_language(page, target_ui_val):
            raise Exception("UI 설정 실패")
        
        # 변경 반영 대기
        time.sleep(TIMEOUTS.get("retry_delay", 2))
        
        # 2. API 검증
        print(f"[Step 2] API 검증...")
        if not verify_language_value(api_client, language_api_value, max_retries=5):
            raise Exception("API 검증 실패")
        
        print(f"✅ {language_name} 테스트 성공")
        return True, f"{language_name} 테스트 성공"
        
    except Exception as e:
        print(f"❌ {language_name} 테스트 실패: {e}")
        return False, str(e)
