from urllib.parse import parse_qsl
from playwright.sync_api import Page

# 🌍 공통 Selector (다국어 대응)
VISIBLE_DIALOG = '.ui-dialog:visible'
DIALOG_BUTTONS = '.ui-dialog-buttonset button'

def parse_api_response(response_text: str) -> dict:
    """API 응답(Query String)을 딕셔너리로 변환"""
    if not response_text or not response_text.strip():
        return {}
    try:
        return dict(parse_qsl(response_text))
    except Exception as e:
        # 파싱 실패 시 빈 딕셔너리 반환
        return {}

def handle_popup(page: Page, button_index=0, timeout=5000):
    """
    범용 팝업 처리기 (개선판)
    """
    try:
        # 1. 팝업이 뜰 때까지 대기
        page.wait_for_selector(VISIBLE_DIALOG, state="visible", timeout=timeout)
        
        # 2. 최상단 팝업 찾기
        top_dialog = page.locator(VISIBLE_DIALOG).last
        
        # 3. 버튼 찾기 (jQuery UI 표준 구조)
        button = top_dialog.locator(DIALOG_BUTTONS).nth(button_index)
        
        if button.is_visible():
            # force=True: 가려져 있어도 강제 클릭
            button.click(force=True)
            
            # 4. 팝업이 사라질 때까지 대기
            try:
                top_dialog.wait_for(state="hidden", timeout=3000)
            except:
                pass # 닫혔으면 OK, 아니면 넘어가서 로직 진행
            return True
            
    except Exception:
        # 팝업 처리 실패 시, 엔터키로 Fallback
        try:
            page.keyboard.press("Enter")
            return True
        except: pass
        
    return False