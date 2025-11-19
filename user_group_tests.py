import time
from playwright.sync_api import Page
from common_actions import parse_api_response, handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS

# ===========================================================
# ⚙️ [내부 액션 함수] 사용자/그룹 전용
# ===========================================================

def api_get_users_groups(page: Page, ip: str):
    """API로 현재 그룹 및 사용자 목록 조회"""
    group_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=groupSetup&mode=1"
    user_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=userSetup&mode=1"
    
    result = {"groups": [], "users": []}
    
    try:
        resp_text = page.evaluate(f"fetch('{group_url}').then(r => r.text())")
        data = parse_api_response(resp_text)
        cnt = int(data.get("groupCount", 0))
        for i in range(1, cnt + 1):
            result["groups"].append(data.get(f"groupName{i}"))
    except: pass

    try:
        resp_text = page.evaluate(f"fetch('{user_url}').then(r => r.text())")
        data = parse_api_response(resp_text)
        cnt = int(data.get("userCount", 0))
        for i in range(1, cnt + 1):
            result["users"].append({
                "name": data.get(f"user{i}Name"),
                "group": data.get(f"user{i}Group")
            })
    except: pass
    
    return result

def ui_add_group(page: Page, group_name: str):
    """그룹 추가 (모든 권한 해제)"""
    try:
        page.locator("#Page200_id").click() # 시스템
        page.locator("#Page203_id").click() # 사용자/그룹
        page.wait_for_timeout(1000) 

        page.locator("#add-group-btn").click()
        
        # 팝업 대기
        page.wait_for_selector("#edit-gid", state="visible", timeout=5000)

        # 그룹명 입력
        page.locator("#edit-gid").fill(group_name)
        
        # 팝업 컨테이너 찾기 (체크박스 제어를 위해)
        popup = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#edit-gid"))
        
        # 모든 체크박스 해제
        checkboxes = popup.locator("input[type='checkbox']")
        count = checkboxes.count()
        for i in range(count):
            if checkboxes.nth(i).is_checked():
                checkboxes.nth(i).uncheck()
        
        # 확인 버튼 클릭
        popup.locator(DIALOG_BUTTONS).first.click()
        
        # 팝업 닫힘 확인
        page.locator("#edit-gid").wait_for(state="hidden", timeout=3000)
        return True
    except Exception as e:
        print(f"❌ 그룹 추가 실패: {e}")
        return False

def ui_select_group_node(page: Page, group_name: str):
    """트리에서 특정 그룹 이름 클릭"""
    try:
        # 트리 노드 찾기 (a 태그 텍스트 매칭)
        node = page.locator(f"a.dynatree-title:text-is('{group_name}')")
        node.wait_for(state="visible", timeout=5000)
        
        # 강제 클릭
        node.click(force=True)
        page.wait_for_timeout(1000) 
        return True
    except Exception as e:
        print(f"❌ 그룹 선택 실패 ({group_name}): {e}")
        return False

def ui_add_user(page: Page, user_id: str, password: str):
    """사용자 추가 (수정된 ID 적용)"""
    try:
        # 사용자 추가 버튼 클릭
        print("[UI] '사용자 추가' 버튼 클릭...")
        page.locator("#add-user-btn").click()
        
        # ⭐️ [수정됨] 올바른 ID(#add-user-edit-uid)로 대기
        try:
            page.wait_for_selector("#add-user-edit-uid", state="visible", timeout=3000)
        except:
            if handle_popup(page, button_index=0):
                print("⚠️ [UI] 경고창이 떠서 닫았습니다. (그룹 미선택 등)")
                return False
            else:
                print("❌ [UI] 사용자 추가 팝업이 뜨지 않았습니다.")
                return False

        print(f"[UI] 사용자 정보 입력 ({user_id})...")
        
        # ⭐️ [수정됨] HTML 소스 기반 정확한 ID 사용
        page.locator("#add-user-edit-uid").fill(user_id)
        page.locator("#add-user-edit-passwd1").fill(password)
        page.locator("#add-user-edit-passwd2").fill(password)
        
        # 이메일 사용 안함 체크 (ID: add-email_not_use)
        page.locator("#add-email_not_use").check()
        
        # 이메일 경고 팝업 처리 (최상단 팝업 OK 클릭)
        try:
            if page.locator(VISIBLE_DIALOG).count() > 1:
                warning = page.locator(VISIBLE_DIALOG).last
                warning.locator(DIALOG_BUTTONS).first.click()
                warning.wait_for(state="hidden", timeout=2000)
        except: pass
        
        # 확인 버튼 클릭 (사용자 추가 팝업의 OK)
        # #add-user-edit-uid가 있는 팝업의 버튼을 찾음
        add_user_popup = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#add-user-edit-uid"))
        add_user_popup.locator(DIALOG_BUTTONS).first.click()
        
        # 팝업 닫힘 대기
        page.locator("#add-user-edit-uid").wait_for(state="hidden", timeout=3000)
        
        # 저장 버튼 클릭 (최종 반영)
        print("[UI] 최종 저장...")
        page.locator("#setup-apply").click()
        handle_popup(page)
        
        return True
    except Exception as e:
        print(f"❌ 사용자 추가 실패: {e}")
        return False

# ===========================================================
# ⚙️ [테스트 케이스]
# ===========================================================

def run_user_group_test(page: Page, camera_ip: str):
    GROUP_NAME = "아이디스"
    USER_ID = "admin123"
    USER_PW = "qwerty0-"
    
    print(f"\n--- [TC 5] 사용자/그룹 추가 테스트 ---")
    
    # 1. 그룹 추가
    print(f"[Step 1] 그룹 '{GROUP_NAME}' 추가 (권한 없음)...")
    if not ui_add_group(page, GROUP_NAME): return False, "그룹 추가 UI 실패"
    
    # 2. 그룹 선택
    print(f"[Step 2] 트리에서 '{GROUP_NAME}' 그룹 선택...")
    if not ui_select_group_node(page, GROUP_NAME): return False, "그룹 선택 실패"
    
    # 3. 사용자 추가
    print(f"[Step 3] 사용자 '{USER_ID}' 추가...")
    if not ui_add_user(page, USER_ID, USER_PW): return False, "사용자 추가 UI 실패"
    
    # 4. 검증 (API)
    print(f"[Step 4] API 검증...")
    time.sleep(2) # 저장 반영 대기
    data = api_get_users_groups(page, camera_ip)
    
    # 그룹 존재 확인
    if GROUP_NAME not in data["groups"]:
        return False, f"그룹 생성 안됨 (목록: {data['groups']})"
        
    # 사용자 존재 및 소속 확인
    user_found = False
    for u in data["users"]:
        if u["name"] == USER_ID and u["group"] == GROUP_NAME:
            user_found = True
            break
            
    if user_found:
        print(f"✅ 사용자/그룹 생성 검증 완료")
        return True, "사용자/그룹 테스트 성공"
    else:
        return False, f"사용자 생성 실패 또는 그룹 불일치 (목록: {data['users']})"