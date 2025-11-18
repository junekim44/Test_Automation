from playwright.sync_api import Page

# 1. 'common_actions.py' 파일에서 언어 관련 헬퍼 함수 2개를 import
try:
    from common_actions import (
        api_get_language, 
        ui_set_language
    )
except ImportError:
    print("오류: 'common_actions.py' 파일이 같은 폴더에 있는지 확인하세요.")
    exit()

# -----------------------------------------------------------
# 📚 테스트 데이터: API 값과 <option>의 value 속성 매핑 (⭐️수정됨⭐️)
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
# 
# ⚙️ '시스템/언어' 메뉴 테스트 시나리오
# 
# ===========================================================

# -----------------------------------------------------------
# ⚙️ 테스트 케이스: 모든 언어 변경 및 API 검증 (⭐️수정됨⭐️)
# -----------------------------------------------------------
def run_all_languages_test(page: Page, camera_ip: str):
    """
    모든 언어를 하나씩 변경하며 API 값이 올바르게 저장되는지 검증합니다.
    """
    
    print("\n--- [TC 2] 전체 언어 변경 테스트 시작 ---")
    
    failed_languages = []
    
    try:
        # 1. 20개 언어를 순회하며 테스트
        for lang in LANGUAGE_MAP:
            lang_api = lang["api"]
            lang_value = lang["value"] # 👈 "ui" 대신 "value" 사용
            
            print(f"\n[TC 2] 테스트 중: {lang_api} (value={lang_value})")
            
            # 2. UI로 언어 변경 및 저장 (label 대신 value 전달)
            if not ui_set_language(page, lang_value):
                print(f"🔥 [TC 2] UI 변경 실패: {lang_api}")
                failed_languages.append(f"{lang_api} (UI 저장 실패)")
                continue # 다음 언어로 넘어감
            
            # 3. API로 현재 설정된 언어 값 가져오기
            current_api_lang = api_get_language(page, camera_ip)
            
            # 4. 검증
            if current_api_lang == lang_api:
                print(f"✅ [TC 2] 검증 성공: {lang_api}")
            else:
                print(f"🔥 [TC 2] API 검증 실패: {lang_api} (예상: {lang_api}, 실제: {current_api_lang})")
                failed_languages.append(f"{lang_api} (API 검증 실패)")

        # 5. (필수) 테스트 후 '한국어'로 원상 복구 (value="20")
        print("\n[TC 2] 모든 테스트 완료. '한국어(value=20)'로 설정을 복구합니다...")
        ui_set_language(page, "20") # 👈 '한국어' 텍스트 대신 value '20' 사용
        
        # 6. 최종 결과 보고
        if not failed_languages:
            return True, "전체 언어 테스트 성공"
        else:
            return False, f"언어 테스트 실패: {', '.join(failed_languages)}"

    except Exception as e:
        print(f"🔥 [TC 2] 테스트 중 심각한 오류 발생: {e}")
        # 오류 발생 시에도 '한국어'로 복구 시도
        try:
            ui_set_language(page, "20")
        except:
            pass
        return False, str(e)