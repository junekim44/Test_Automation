import time
from playwright.sync_api import Page
from api_client import CameraApiClient
from common_actions import handle_popup
from config import (
    TIMEOUTS,
    TEST_GROUP_A,
    TEST_GROUP_B,
    TEST_USER_ID,
    TEST_USER_PW,
    IRAS_DEVICE_NAME
)
import iRAS_test

# ===========================================================
# 📋 [설정] 상수 및 매핑
# ===========================================================

# 1. 그룹 생성 (Add) 팝업용 ID
ADD_ID_MAP = {
    "NAME_INPUT": "#edit-gid",
    "PERMS": {
        "업그레이드": "#auth-upgrade",
        "설정": "#auth-setup",
        "컬러 조정": "#auth-color",
        "PTZ 제어": "#auth-ptz",
        "알람-아웃 제어": "#auth-alarm",
        "검색": "#auth-search",
        "클립-카피": "#auth-clipcopy"
    }
}

# 2. 그룹 변경 (Edit) 팝업용 ID
EDIT_ID_MAP = {
    "NAME_INPUT": "#edit-auth-gid",
    "PERMS": {
        "업그레이드": "#edit-auth-upgrade",
        "설정": "#edit-auth-setup",
        "컬러 조정": "#edit-auth-color",
        "PTZ 제어": "#edit-auth-ptz",
        "알람-아웃 제어": "#edit-auth-alarm",
        "검색": "#edit-auth-search",
        "클립-카피": "#edit-auth-clipcopy"
    }
}

# 3. API 검증용 매핑
UI_TO_API_MAP = {
    "업그레이드": "upgrade",
    "설정": "setup",
    "컬러 조정": "color",
    "PTZ 제어": "ptz",
    "알람-아웃 제어": "alarmOut",
    "검색": "search",
    "클립-카피": "clipCopy"
}

# 그룹 생성 시 초기 권한 설정
INITIAL_PERMS = {
    "설정": True,         
    "검색": True,         
    "업그레이드": False,  
    "컬러 조정": False,   
    "PTZ 제어": False,    
    "알람-아웃 제어": False, 
    "클립-카피": False    
}

# ===========================================================
# 📡 [API] 검증 함수
# ===========================================================

def verify_permissions_via_api(page: Page, camera_ip: str, group_name: str, expected_perms: dict):
    """API를 통해 그룹 권한이 올바르게 설정되었는지 검증"""
    print(f"   📡 [API] '{group_name}' 권한 실제 적용 여부 확인 중...")
    
    api_url = f"http://{camera_ip}/cgi-bin/webSetup.cgi?action=groupSetup&mode=1"
    try:
        resp_text = page.evaluate(f"fetch('{api_url}').then(r => r.text())")
        data = dict(item.split("=", 1) for item in resp_text.strip().split("&") if "=" in item)
    except Exception as e:
        print(f"   🔥 [API] Fetch 실패: {e}")
        return False
    
    count = int(data.get("groupCount", 0))
    target_idx = -1
    for i in range(1, count + 1):
        if data.get(f"groupName{i}") == group_name:
            target_idx = i
            break
    
    if target_idx == -1:
        print(f"   ❌ [API] 그룹 '{group_name}'을 찾을 수 없습니다.")
        return False

    auth_str = data.get(f"authorities{target_idx}", "")
    current_apis = auth_str.split("|") if auth_str else []
    
    is_valid = True
    for ui_name, should_have in expected_perms.items():
        api_name = UI_TO_API_MAP.get(ui_name)
        if not api_name: continue
        
        has_perm = api_name in current_apis
        if should_have != has_perm:
            print(f"   ❌ [Mismatch] {ui_name}({api_name}) -> 기대: {should_have}, 실제: {has_perm}")
            is_valid = False
            
    if is_valid:
        print(f"   ✅ [API] 권한 검증 통과 (API: {auth_str})")
        return True
    return False

def verify_group_absence_via_api(page: Page, camera_ip: str, group_name: str):
    """API를 통해 그룹이 삭제되었는지 확인"""
    print(f"   📡 [API] '{group_name}' 삭제 여부 확인 중...")
    
    api_url = f"http://{camera_ip}/cgi-bin/webSetup.cgi?action=groupSetup&mode=1"
    try:
        resp_text = page.evaluate(f"fetch('{api_url}').then(r => r.text())")
        data = dict(item.split("=", 1) for item in resp_text.strip().split("&") if "=" in item)
    except Exception as e:
        print(f"   ⚠️ [API] Fetch 실패 (삭제된 것으로 간주): {e}")
        return True
    
    count = int(data.get("groupCount", 0))
    found = False
    for i in range(1, count + 1):
        if data.get(f"groupName{i}") == group_name:
            found = True
            break
            
    if found:
        print(f"   ❌ [API] 그룹 '{group_name}'이(가) 여전히 존재합니다!")
        return False
    else:
        print(f"   ✅ [API] 그룹 삭제 확인 완료 (목록에 없음)")
        return True

# ===========================================================
# ⚙️ [Helper] UI 제어 함수
# ===========================================================

def toggle_permissions(popup, id_map, target_state, page):
    """그룹 생성/수정 팝업에서 권한 체크박스 토글"""
    for perm_name, should_check in target_state.items():
        target_id = id_map.get(perm_name)
        if not target_id: continue
        checkbox = popup.locator(target_id)
        if checkbox.is_visible():
            if checkbox.is_checked() != should_check:
                page.wait_for_timeout(300) 
                if should_check:
                    checkbox.check()
                    print(f"   -> [체크] {perm_name}")
                else:
                    checkbox.uncheck()
                    print(f"   -> [해제] {perm_name}")
                page.wait_for_timeout(300)

def select_group_in_tree(page: Page, group_name: str) -> bool:
    """트리에서 그룹 선택"""
    try:
        node = page.locator(f"a.dynatree-title:text-is('{group_name}')")
        if node.count() == 0: 
            return False
        node.click(force=True)
        page.wait_for_timeout(500) 
        return True
    except: 
        return False

def select_user(page: Page, uid: str) -> bool:
    """트리 또는 리스트에서 사용자 선택"""
    user_tree_node = page.locator(f"a.dynatree-title:text-is('{uid}')")
    try:
        if user_tree_node.is_visible():
            print(f"   -> [Tree] 트리에서 사용자 '{uid}' 발견 및 클릭")
            user_tree_node.click()
            page.wait_for_timeout(300)
            return True
        
        user_cell = page.locator(f"td:text-is('{uid}')")
        if user_cell.is_visible():
            print(f"   -> [List] 리스트에서 사용자 '{uid}' 발견 및 클릭")
            user_cell.click()
            page.wait_for_timeout(300)
            return True
    except Exception as e:
        print(f"⚠️ 사용자 선택 중 예외 발생: {e}")
    return False

# ===========================================================
# 🛠️ [기능] 그룹/사용자 관리 (UI 기반)
# ===========================================================

def create_group_only(page: Page, group_name: str) -> bool:
    """UI로 그룹만 생성 (사용자 없이)"""
    if select_group_in_tree(page, group_name):
        print(f"ℹ️ 그룹 '{group_name}' 이미 존재.")
        return True
    
    print(f"   🖥️ [UI] 그룹 '{group_name}' 생성...")
    page.locator("#add-group-btn").click()
    input_id = ADD_ID_MAP["NAME_INPUT"]
    try: 
        page.wait_for_selector(input_id, state="visible", timeout=3000)
    except: 
        return False

    group_dialog = page.locator(".ui-dialog").filter(has=page.locator(input_id))
    page.locator(input_id).fill(group_name)
    toggle_permissions(group_dialog, ADD_ID_MAP["PERMS"], INITIAL_PERMS, page)

    group_dialog.locator(".ui-dialog-buttonset button").first.click()
    page.locator(input_id).wait_for(state="hidden")
    page.wait_for_timeout(1000)
    page.locator("#setup-apply").click()
    handle_popup(page)
    time.sleep(1)
    return True

def create_group_and_user(page: Page, group_name: str, uid: str, upw: str) -> bool:
    """UI로 그룹과 사용자 생성"""
    try:
        print(f"\n🖥️ [UI] 계정 생성 프로세스 시작 ({group_name})...")
        create_group_only(page, group_name)
        select_group_in_tree(page, group_name)
        print(f"   🖥️ [UI] 사용자 '{uid}' 생성 시도...")
        page.locator("#add-user-btn").click()
        page.wait_for_selector("#add-user-edit-uid", state="visible", timeout=3000)
        
        user_dialog = page.locator(".ui-dialog").filter(has=page.locator("#add-user-edit-uid"))
        page.locator("#add-user-edit-uid").fill(uid)
        page.locator("#add-user-edit-passwd1").fill(upw)
        page.locator("#add-user-edit-passwd2").fill(upw)
        user_dialog.locator("#add-email_not_use").check()
        page.wait_for_timeout(1000) 
        
        blocking_msg = page.locator(".ui-dialog[aria-describedby='msg-dialog-ok']:visible")
        if blocking_msg.count() > 0:
            blocking_msg.locator(".ui-dialog-buttonset button").first.click()
            page.wait_for_timeout(500)
        elif page.locator(".ui-dialog:visible").count() > 1:
            top_dlg = page.locator(".ui-dialog:visible").last
            if top_dlg.locator("#add-user-edit-uid").count() == 0:
                btn = top_dlg.locator(".ui-dialog-buttonset button").first
                if btn.is_visible(): 
                    btn.click(force=True)
                else: 
                    top_dlg.locator("button").first.click(force=True)
                page.wait_for_timeout(500)

        user_confirm_btn = user_dialog.locator(".ui-dialog-buttonset button").first
        if user_confirm_btn.is_enabled():
            user_confirm_btn.click()
            page.locator("#add-user-edit-uid").wait_for(state="hidden")
        else:
            user_dialog.locator(".ui-dialog-buttonset button").last.click()

        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        print(f"   ✅ 계정 생성 완료")
        return True
    except Exception as e:
        print(f"   ❌ 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def move_user_to_group(page: Page, uid: str, current_group: str, target_group: str) -> bool:
    """UI로 사용자를 다른 그룹으로 이동"""
    print(f"\n📦 [UI] 사용자 '{uid}' 이동: {current_group} -> {target_group}")
    try:
        if not select_user(page, uid): 
            return False
        
        page.locator("#edit-user-btn").click()
        target_selector = "#edit-user-edit-ugroup"
        try: 
            page.wait_for_selector(target_selector, state="visible", timeout=3000)
        except: 
            return False
        
        edit_dialog = page.locator(".ui-dialog").filter(has=page.locator(target_selector))
        group_select = edit_dialog.locator(target_selector).first 
        group_select.select_option(label=target_group)
        edit_dialog.locator(".ui-dialog-buttonset button").first.click()
        page.locator(target_selector).first.wait_for(state="hidden")
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        print(f"   ✅ 사용자 이동 완료")
        return True
    except Exception as e:
        print(f"   ❌ 이동 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def modify_group_permissions(page: Page, group_name: str, target_perms: dict) -> bool:
    """UI로 그룹의 권한 수정"""
    print(f"\n🔧 [UI] 그룹 '{group_name}' 권한 변경 시도...")
    try:
        # 그룹 선택
        if not select_group_in_tree(page, group_name):
            print(f"   ❌ 그룹 '{group_name}' 선택 실패")
            return False
        
        # 수정 버튼 클릭
        page.locator("#edit-user-btn").click()
        
        # 팝업 대기
        input_id = EDIT_ID_MAP["NAME_INPUT"]
        try: 
            page.wait_for_selector(input_id, state="visible", timeout=3000)
        except:
            print("   ❌ 권한 수정 팝업 안 뜸")
            return False
            
        popup = page.locator(".ui-dialog").filter(has=page.locator(input_id))
        
        # 권한 변경 적용
        toggle_permissions(popup, EDIT_ID_MAP["PERMS"], target_perms, page)
        
        # 저장
        popup.locator(".ui-dialog-buttonset button").first.click()
        page.locator(input_id).wait_for(state="hidden")
        
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        print(f"   ✅ 권한 변경 완료")
        return True
    except Exception as e:
        print(f"   ❌ 권한 변경 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def delete_group_and_user(page: Page, group_name: str, uid: str = None) -> bool:
    """UI로 그룹 및 사용자 삭제"""
    try:
        print(f"\n🗑️ [UI] 그룹 '{group_name}' 삭제 시도...")
        if not select_group_in_tree(page, group_name): 
            return True

        if uid:
            if select_user(page, uid):
                page.locator("#remove-user-btn").click()
                handle_popup(page)
                page.wait_for_timeout(500)

        select_group_in_tree(page, group_name)
        page.locator("#remove-user-btn").click()
        handle_popup(page)
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        print(f"   ✅ 삭제 완료")
        return True
    except Exception as e:
        print(f"   ❌ 삭제 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

# ===========================================================
# 🚀 [메인 테스트 케이스]
# ===========================================================

def run_user_group_test(page: Page, camera_ip: str, admin_id: str, admin_pw: str):
    """
    그룹/사용자 관리 통합 테스트 (UI 기반)
    권한 변경만 API로 수행합니다.
    """
    GROUP_A = TEST_GROUP_A
    GROUP_B = TEST_GROUP_B
    UID = TEST_USER_ID
    UPW = TEST_USER_PW
    DEVICE = IRAS_DEVICE_NAME

    # API 클라이언트 생성
    api_client = CameraApiClient(page, camera_ip)

    # 🚨 [추가] iRAS 테스트 전 알람 출력 활성화
    print("\n[Pre-Condition] iRAS 테스트를 위해 알람 출력(Alarm Out)을 활성화합니다.")
    if not api_client.set_action_alarmout(use_alarm_out="on"):
        print("   ⚠️ 알람 출력 활성화 실패. iRAS 메뉴에 나타나지 않을 수 있습니다.")
    else:
        print("   ✅ 알람 출력 활성화 성공.")

    print("\n" + "="*60)
    print("=== [통합 테스트] 그룹/사용자 관리 및 API 검증 Start ===")
    print("="*60)
    
    # 메뉴 진입
    page.locator("#Page200_id").click()
    page.wait_for_timeout(500)
    page.locator("#Page203_id").click()
    page.wait_for_timeout(1000)

    # 1. 생성 및 이동 시나리오
    print("\n[Step 1] 그룹 및 사용자 생성...")
    if not create_group_and_user(page, GROUP_A, UID, UPW): 
        return False, "그룹A 및 사용자 생성 실패"
    
    if not create_group_only(page, GROUP_B): 
        return False, "그룹B 생성 실패"
    
    print("\n🔄 [Refresh] UI 동기화...")
    page.reload()
    page.wait_for_timeout(2000)
    try:
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page203_id").click()
        page.wait_for_timeout(1500)
    except: 
        return False, "메뉴 재진입 실패"

    print("\n[Step 2] 사용자 그룹 이동...")
    if not move_user_to_group(page, UID, GROUP_A, GROUP_B): 
        return False, "사용자 이동 실패"
    
    print("\n[Step 3] 그룹A 삭제...")
    if not delete_group_and_user(page, GROUP_A, uid=None): 
        return False, "그룹A 삭제 실패"
    
    # API 클라이언트 생성 (권한 검증용)
    api_client = CameraApiClient(page, camera_ip)
    
    if not verify_group_absence_via_api(page, camera_ip, GROUP_A):
        return False, "그룹A 삭제 검증 실패"
    
    # 2. [API] Phase 1: 설정과 검색을 제외한 모든 권한 해제
    print("\n" + "="*60)
    print("[Step 4] Phase 1: 설정과 검색을 제외한 모든 권한 해제")
    print("="*60)
    phase1_perms = {
        "설정": True,          # 유지
        "검색": True,          # 유지
        "업그레이드": False,   # 해제
        "컬러 조정": False,    # 해제
        "PTZ 제어": False,     # 해제
        "알람-아웃 제어": False, # 해제
        "클립-카피": False     # 해제
    }
    
    if not api_client.set_group_permissions(GROUP_B, phase1_perms, UI_TO_API_MAP):
        delete_group_and_user(page, GROUP_B, UID)
        return False, "Phase 1 권한 설정 실패"
    
    # API 검증
    time.sleep(TIMEOUTS.get("retry_delay", 2))
    if not verify_permissions_via_api(page, camera_ip, GROUP_B, phase1_perms):
        delete_group_and_user(page, GROUP_B, UID)
        return False, "Phase 1 권한 검증 실패"
    print("✅ Phase 1 권한 설정 완료: setup=True, search=True, 나머지=False")
    
    # 2-1. [iRAS] Phase 1: 기본 권한(클립카피 등) 확인
    print("\n🖥️ [iRAS] Phase 1 검증 (클립카피 등)...")
    success_p1, msg_p1 = iRAS_test.run_iras_permission_check(DEVICE, UID, UPW, phase=1)
    if not success_p1: 
        print(f"⚠️ Phase 1 실패: {msg_p1}")
        delete_group_and_user(page, GROUP_B, UID)
        return False, f"Phase 1 실패: {msg_p1}"
    print(f"✅ Phase 1 성공: {msg_p1}")

    # 3. [API] Phase 2: setup과 ptz도 마저 해제
    print("\n" + "="*60)
    print("[Step 5] Phase 2: setup과 ptz도 마저 해제")
    print("="*60)
    phase2_perms = {
        "설정": False,         # 추가 해제
        "검색": False,         # 추가 해제
        "업그레이드": False,   
        "컬러 조정": False,    
        "PTZ 제어": False,     # 추가 해제
        "알람-아웃 제어": False,
        "클립-카피": False     # 유지 (이미 False)
    }
    
    if not api_client.set_group_permissions(GROUP_B, phase2_perms, UI_TO_API_MAP):
        delete_group_and_user(page, GROUP_B, UID)
        return False, "Phase 2 권한 설정 실패"
    
    # API 검증
    time.sleep(TIMEOUTS.get("retry_delay", 2))
    if not verify_permissions_via_api(page, camera_ip, GROUP_B, phase2_perms):
        delete_group_and_user(page, GROUP_B, UID)
        return False, "Phase 2 권한 검증 실패"
    print("✅ Phase 2 권한 설정 완료: 모든 권한=False")

    # 3-1. [iRAS] Phase 2: 차단 확인 (재생, 설정 불가)
    print("\n🖥️ [iRAS] Phase 2 검증 (권한 차단 확인)...")
    success_p2, msg_p2 = iRAS_test.run_iras_permission_check(DEVICE, UID, UPW, phase=2)
    if not success_p2:
        print(f"⚠️ Phase 2 실패: {msg_p2}")
        delete_group_and_user(page, GROUP_B, UID)
        return False, f"Phase 2 실패: {msg_p2}"
    print(f"✅ Phase 2 성공: {msg_p2}")

    # 5. Cleanup
    print("\n" + "="*60)
    print("[Step 6] Cleanup: 데이터 정리")
    print("="*60)
    if not delete_group_and_user(page, GROUP_B, UID): 
        return False, "Cleanup 실패"

    print("\n🔄 [Final] 관리자 로그인 복구...")
    iRAS_test.restore_admin_login(DEVICE, admin_id, admin_pw)

    print("\n" + "="*60)
    print("✅ 전체 시나리오 성공!")
    print("="*60)
    return True, "전체 시나리오 성공"
