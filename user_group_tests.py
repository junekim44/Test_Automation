import time
from playwright.sync_api import Page
from common_actions import handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS
import iRAS_test

# ===========================================================
# 📋 [설정] ID 및 API 매핑
# ===========================================================

# 1. 그룹 생성 (Add) 팝업용 ID (edit- 없음)
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

# 2. 그룹 변경 (Edit) 팝업용 ID (edit- 있음)
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

# 3. API 검증용 매핑 (UI한글 -> API영문)
UI_TO_API_MAP = {
    "업그레이드": "upgrade",
    "설정": "setup",
    "컬러 조정": "color",
    "PTZ 제어": "ptz",
    "알람-아웃 제어": "alarmOut",
    "검색": "search",
    "클립-카피": "clipCopy"
}

# -----------------------------------------------------------
# [초기 권한 설정]
# -----------------------------------------------------------
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
# 📡 [API] 권한 검증 함수 (복구됨)
# ===========================================================
def verify_permissions_via_api(page: Page, ip: str, group_name: str, expected_perms: dict):
    """API를 통해 실제 권한이 적용되었는지 교차 검증"""
    print(f"   📡 [API] '{group_name}' 권한 실제 적용 여부 확인 중...")
    
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=groupSetup&mode=1"
    
    try:
        # 현재 세션으로 API 호출
        resp_text = page.evaluate(f"fetch('{api_url}').then(r => r.text())")
        data = dict(item.split("=", 1) for item in resp_text.strip().split("&") if "=" in item)
        
        # 그룹 찾기
        count = int(data.get("groupCount", 0))
        target_idx = -1
        for i in range(1, count + 1):
            if data.get(f"groupName{i}") == group_name:
                target_idx = i
                break
        
        if target_idx == -1:
            print(f"   ❌ [API] 그룹 '{group_name}'을 찾을 수 없습니다.")
            return False

        # 권한 파싱 (예: setup|search|color)
        auth_str = data.get(f"authorities{target_idx}", "")
        current_apis = auth_str.split("|") if auth_str else []
        
        # 검증
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

    except Exception as e:
        print(f"   🔥 [API] 검증 중 오류: {e}")
        return False

# ===========================================================
# ⚙️ [Helper] 체크박스 제어
# ===========================================================
def toggle_permissions(popup, id_map, target_state):
    for perm_name, should_check in target_state.items():
        target_id = id_map.get(perm_name)
        if not target_id: continue

        checkbox = popup.locator(target_id)
        if checkbox.is_visible():
            if checkbox.is_checked() != should_check:
                if should_check:
                    checkbox.check()
                    print(f"   -> [체크] {perm_name}")
                else:
                    checkbox.uncheck()
                    print(f"   -> [해제] {perm_name}")
                # time.sleep(0.2) # 필요시 대기
        else:
            print(f"⚠️ 요소 안 보임: {perm_name} ({target_id})")

# ===========================================================
# ⚙️ [UI 제어 함수]
# ===========================================================

def select_group_in_tree(page: Page, group_name: str):
    try:
        node = page.locator(f"a.dynatree-title:text-is('{group_name}')")
        if node.count() == 0: return False
        node.click(force=True)
        page.wait_for_timeout(500) 
        return True
    except: return False

def create_group_and_user(page: Page, group_name: str, uid: str, upw: str):
    try:
        print(f"[UI] 계정 생성 프로세스 시작 ({group_name})...")
        page.locator("#Page200_id").click()
        page.locator("#Page203_id").click()
        page.wait_for_timeout(1500)

        # 1. 그룹 생성
        if select_group_in_tree(page, group_name):
            print(f"ℹ️ 그룹 '{group_name}' 이미 존재. 생성 스킵.")
        else:
            print(f"[UI] 새 그룹 '{group_name}' 생성...")
            page.locator("#add-group-btn").click()
            page.wait_for_selector("#edit-gid", state="visible", timeout=2000)
            page.wait_for_timeout(1000)
            
            # 팝업 특정 (입력칸 ID 기준)
            input_id = ADD_ID_MAP["NAME_INPUT"]
            group_dialog = page.locator(".ui-dialog").filter(has=page.locator(input_id))
            
            page.locator(input_id).fill(group_name)
            page.wait_for_timeout(500)
            
            # 초기 권한 설정 (ADD_ID_MAP 사용)
            print("   -> 초기 권한 적용 중...")
            toggle_permissions(group_dialog, ADD_ID_MAP["PERMS"], INITIAL_PERMS)

            # 확인
            confirm_btn = group_dialog.locator(".ui-dialog-buttonset button").first
            if confirm_btn.is_enabled():
                confirm_btn.click()
                page.locator(input_id).wait_for(state="hidden")
                page.wait_for_timeout(1000)
            else:
                print("🔥 확인 버튼 비활성화. 취소.")
                group_dialog.locator(".ui-dialog-buttonset button").last.click()
                return False

        # 2. 사용자 생성
        select_group_in_tree(page, group_name)
        print(f"[UI] 사용자 '{uid}' 생성 시도...")
        page.locator("#add-user-btn").click()
        page.wait_for_selector("#add-user-edit-uid", state="visible")
        page.wait_for_timeout(1000)
        
        user_dialog = page.locator(".ui-dialog").filter(has=page.locator("#add-user-edit-uid"))
        page.locator("#add-user-edit-uid").fill(uid)
        page.locator("#add-user-edit-passwd1").fill(upw)
        page.locator("#add-user-edit-passwd2").fill(upw)
        user_dialog.locator("#add-email_not_use").check()
        page.wait_for_timeout(1000)
        
        # 경고창 처리
        if page.locator(VISIBLE_DIALOG).count() > 1:
            top_dlg = page.locator(".ui-dialog:visible").last
            if top_dlg.locator("#add-user-edit-uid").count() == 0:
                print("   -> 경고창 닫기")
                btn = top_dlg.locator(".ui-dialog-buttonset button").first
                if btn.is_visible(): btn.click(force=True)
                else: top_dlg.locator("button").first.click(force=True)
                page.wait_for_timeout(500)

        user_confirm_btn = user_dialog.locator(".ui-dialog-buttonset button").first
        if user_confirm_btn.is_enabled():
            user_confirm_btn.click()
            page.locator("#add-user-edit-uid").wait_for(state="hidden")
        else:
            print(f"ℹ️ 사용자 중복. 취소.")
            user_dialog.locator(".ui-dialog-buttonset button").last.click()
        
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        return True

    except Exception as e:
        print(f"❌ 생성 오류: {e}")
        return False

def set_permissions_state(page: Page, group_name: str, target_state: dict):
    """그룹 권한 변경 (변경용 ID 사용)"""
    try:
        print(f"[UI] '{group_name}' 권한 변경 시작...")
        if not select_group_in_tree(page, group_name): return False
        page.locator("#edit-user-btn").click()
        
        try: page.wait_for_selector("#edit-group-diag", state="visible", timeout=5000)
        except:
            print("🔥 변경 팝업 미발견")
            return False

        popup = page.locator(".ui-dialog").filter(has=page.locator("#edit-group-diag"))
        page.wait_for_timeout(1000)

        # 권한 변경 (EDIT_ID_MAP 사용)
        toggle_permissions(popup, EDIT_ID_MAP["PERMS"], target_state)

        confirm_btn = popup.locator(".ui-dialog-buttonset button").first
        page.wait_for_timeout(500)
        
        if confirm_btn.is_enabled():
            confirm_btn.click()
            page.locator("#edit-group-diag").wait_for(state="hidden")
        else:
            print("⚠️ 변경사항 없음. 취소.")
            popup.locator(".ui-dialog-buttonset button").last.click()
        
        page.wait_for_timeout(1000)
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(3)
        return True

    except Exception as e:
        print(f"❌ 권한 설정 오류: {e}")
        return False

# ===========================================================
# 🚀 [메인 테스트 케이스]
# ===========================================================

def run_user_group_test(page: Page, camera_ip: str):
    GROUP = "아이디스"
    UID = "admin123"
    UPW = "qwerty0-"
    DEVICE = "105_T6831"

    print("\n=== [통합 테스트] 권한 제어 시나리오 Start ===")

    # 1. 계정 생성 (생성 시 INITIAL_PERMS 적용됨)
    if not create_group_and_user(page, GROUP, UID, UPW):
        return False, "계정 생성 실패"

    # ⭐️ [API 검증 1] 초기 권한 확인 (설정/검색 ON)
    if not verify_permissions_via_api(page, camera_ip, GROUP, INITIAL_PERMS):
        return False, "API 검증 실패 (초기 설정)"

    # 2. [Phase 1] iRAS 검증
    print("\n🖥️ [Phase 1] iRAS 검증 시작...")
    success_p1, msg_p1 = iRAS_test.run_iras_permission_check(DEVICE, UID, UPW, phase=1)
    if not success_p1: return False, f"Phase 1 iRAS 실패: {msg_p1}"
    print(f"✅ Phase 1 통과: {msg_p1}")

    # 3. [Phase 2] 권한 변경 (설정, 검색 해제)
    print("\n🌐 [Phase 2] 권한 변경 (설정/검색 OFF)...")
    phase2_perms = {
        "클립-카피": False,
        "검색": False,
        "설정": False
    }
    
    if not set_permissions_state(page, GROUP, phase2_perms):
        return False, "Phase 2 권한 설정 실패"

    # ⭐️ [API 검증 2] 변경된 권한 확인 (모두 OFF)
    # 전체 권한 상태를 만들어 검증 (초기값 복사 후 변경값 덮어쓰기)
    full_phase2_perms = INITIAL_PERMS.copy()
    full_phase2_perms.update(phase2_perms)
    
    if not verify_permissions_via_api(page, camera_ip, GROUP, full_phase2_perms):
        return False, "API 검증 실패 (Phase 2 변경)"

    # 4. [Phase 2] iRAS 검증
    success_p2, msg_p2 = iRAS_test.run_iras_permission_check(DEVICE, UID, UPW, phase=2)
    if not success_p2: return False, f"Phase 2 iRAS 실패: {msg_p2}"
    print(f"✅ Phase 2 통과: {msg_p2}")

    return True, "모든 권한 테스트 성공"