from playwright.sync_api import Page

# 1. 'common_actions.py' 파일에서 필요한 헬퍼 함수들을 import
try:
    from common_actions import (
        export_and_verify_settings, 
        import_settings_and_reboot, 
        api_get_note, 
        ui_set_note,
        load_default_settings
    )
except ImportError:
    print("오류: 'common_actions.py' 파일이 같은 폴더에 있는지 확인하세요.")
    exit()

# ===========================================================
# 
# ⚙️ '시스템' 메뉴 테스트 시나리오
# 
# ===========================================================

# -----------------------------------------------------------
# ⚙️ 테스트 케이스 1: 설정 내보내기/불러오기 Round-Trip
# -----------------------------------------------------------
def run_setup_roundtrip_test(page: Page, camera_ip: str):
    """
    '설명' 필드 값 변경을 통해 설정 내보내기/불러오기 기능이
    정상 동작하는지 검증하는 E2E 테스트 시나리오.
    """
    
    EXPORT_FILE = "registry_test.dat"
    TEST_NOTE_VALUE = "AUTOMATION_TEST_VALUE_12345"
    CONTAMINATE_VALUE = "DIRTY_VALUE_999"
    
    print("\n--- [TC 1] 설정 내보내기/불러오기 테스트 시작 ---")
    
    try:
        # 1. (준비) 테스트 값으로 설정 변경 (헬퍼 함수 호출)
        print("[TC 1.1] '설명' 값을 테스트 값으로 변경합니다...")
        if not ui_set_note(page, TEST_NOTE_VALUE):
            raise Exception("'설명' 값 설정(UI) 실패")
        
        # 2. (내보내기) 이 설정이 담긴 파일 내보내기 (헬퍼 함수 호출)
        print(f"[TC 1.2] '{TEST_NOTE_VALUE}' 값이 담긴 설정을 내보냅니다...")
        success, msg = export_and_verify_settings(page, EXPORT_FILE)
        if not success:
            raise Exception(f"'설정 내보내기' 실패: {msg}")
        print(f"✅ [TC 1.2] 설정 파일 '{EXPORT_FILE}' 내보내기 성공.")
        
        # 3. (오염) 값을 엉뚱한 값으로 다시 변경 (헬퍼 함수 호출)
        print("[TC 1.3] '설명' 값을 '오염' 값으로 덮어씁니다...")
        if not ui_set_note(page, CONTAMINATE_VALUE):
            raise Exception("'설명' 값 오염(UI) 실패")
        
        # API로 오염되었는지 확인 (헬퍼 함수 호출)
        note_check = api_get_note(page, camera_ip) 
        if note_check != CONTAMINATE_VALUE:
             raise Exception(f"값 오염 실패! (현재 값: {note_check})")
        print(f"✅ [TC 1.3] 값 오염 완료 (현재 'note' = {CONTAMINATE_VALUE})")

        # 4. (불러오기) 2번에서 내보낸 파일 불러오기 (헬퍼 함수 호출)
        print(f"[TC 1.4] '{EXPORT_FILE}' 파일을 '불러오기' 합니다...")
        success, msg = import_settings_and_reboot(page, EXPORT_FILE)
        if not success:
            raise Exception(f"'설정 불러오기' 실패: {msg}")
        print("✅ [TC 1.4] 설정 불러오기 완료.")
        
        # 5. (최종 검증)
        print("[TC 1.5] API로 최종 'note' 값을 검증합니다...")
        final_note_value = api_get_note(page, camera_ip) # (헬퍼 함수 호출)
        
        if final_note_value == TEST_NOTE_VALUE:
            print(f"✅ [TC 1.5] 검증 성공! 'note' 값이 '{TEST_NOTE_VALUE}'로 복원됨.")
            return True, "설정 Round-Trip 테스트 성공"
        else:
            print(f"🔥 [TC 1.5] 검증 실패! (예상: {TEST_NOTE_VALUE}, 실제: {final_note_value})")
            return False, f"최종 검증 실패 (예상: {TEST_NOTE_VALUE}, 실제: {final_note_value})"

    except Exception as e:
        print(f"🔥 [TC 1] 테스트 중 심각한 오류 발생: {e}")
        return False, str(e)

# -----------------------------------------------------------
# ⚙️ 테스트 케이스 2: 기본 설정 불러오기 및 복구 테스트
# -----------------------------------------------------------
def run_default_setup_test(page: Page, camera_ip: str):
    """
    1. 설정 변경 (오염)
    2. 변경된 설정 백업 (내보내기)
    3. 기본 설정 불러오기 (초기화) -> 초기화 되었는지 API 검증
    4. 백업 파일 불러오기 (복구) -> 복구 되었는지 API 검증
    """
    
    BACKUP_FILE = "backup_before_reset.dat"
    TEST_VALUE_BEFORE_RESET = "SETUP_TO_BE_RESET_123" 
    DEFAULT_NOTE_VALUE = "" 
    RESET_PASSWORD = "qwerty0-" # 대문자/소문자/숫자/특수문자 포함 8자 이상
    
    print("\n--- [TC 3] 기본 설정 불러오기 및 복구 테스트 시작 ---")
    
    try:
        # 1. [준비] 설정을 특정한 값으로 변경 (오염)
        print("[TC 3.1] 테스트를 위해 '설명' 값을 변경합니다...")
        if not ui_set_note(page, TEST_VALUE_BEFORE_RESET):
            raise Exception("초기 설정 변경 실패")
            
        # 2. [백업] 현재 상태(오염된 상태)를 파일로 저장
        print(f"[TC 3.2] 현재 설정('{TEST_VALUE_BEFORE_RESET}')을 백업합니다...")
        success, msg = export_and_verify_settings(page, BACKUP_FILE)
        if not success:
            raise Exception(f"설정 백업 실패: {msg}")
        print(f"✅ [TC 3.2] 백업 완료: {BACKUP_FILE}")
        
        # 3. [초기화] 기본 설정 불러오기 실행
        print("[TC 3.3] '기본 설정 불러오기'를 실행합니다...")
        if not load_default_settings(page, RESET_PASSWORD): # 👈 비밀번호 전달
            raise Exception("기본 설정 불러오기 동작 실패")
            
        # 4. [검증 1] 정말로 초기화 되었는지 API로 확인
        print("[TC 3.4] API로 초기화 여부('설명' 필드 공란) 확인...")
        current_note = api_get_note(page, camera_ip)
        
        if current_note == DEFAULT_NOTE_VALUE:
            print(f"✅ [TC 3.4] 초기화 검증 성공! (현재 값: '{current_note}')")
        else:
            raise Exception(f"초기화 검증 실패! (예상: 공란, 실제: '{current_note}')")
            
        # 5. [복구] 아까 백업해둔 파일 불러오기
        print(f"[TC 3.5] 백업 파일('{BACKUP_FILE}')로 설정을 복구합니다...")
        success, msg = import_settings_and_reboot(page, BACKUP_FILE)
        if not success:
            raise Exception(f"설정 복구 실패: {msg}")
            
        # 6. [검증 2] 복구가 제대로 되었는지 API로 확인
        print("[TC 3.6] API로 설정 복구 여부 확인...")
        final_note = api_get_note(page, camera_ip)
        
        if final_note == TEST_VALUE_BEFORE_RESET:
            print(f"✅ [TC 3.6] 복구 검증 성공! ('{TEST_VALUE_BEFORE_RESET}' 로 복원됨)")
            return True, "기본 설정 및 복구 테스트 성공"
        else:
            return False, f"복구 값 불일치 (예상: {TEST_VALUE_BEFORE_RESET}, 실제: {final_note})"

    except Exception as e:
        print(f"🔥 [TC 3] 테스트 중 오류 발생: {e}")
        return False, str(e)