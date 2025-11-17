from playwright.sync_api import Page

# 1. 👈 'common_actions.py' 파일에서 필요한 헬퍼 함수들을 import
try:
    from common_actions import (
        export_and_verify_settings, 
        import_settings_and_reboot, 
        api_get_note, 
        ui_set_note
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
    
    # 이 테스트 케이스에서만 사용할 상수 정의
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
# ⚙️ 테스트 케이스 2: (여기에 다음 '시스템' 관련 테스트 추가)
# -----------------------------------------------------------
# def run_system_led_test(page: Page, camera_ip: str):
#    ...