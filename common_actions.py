from urllib.parse import parse_qsl
from playwright.sync_api import Page

# 🌍 공통 Selector (다국어 대응)
VISIBLE_DIALOG = '.ui-dialog:visible'
DIALOG_BUTTONS = '.ui-dialog-buttonset button'

def parse_api_response(response_text: str) -> dict:
    """API 응답(Query String)을 딕셔너리로 변환"""
    return dict(parse_qsl(response_text))

def handle_popup(page: Page, button_index=0, timeout=5000):
    """
    범용 팝업 처리기
    - 화면 최상단 팝업의 n번째 버튼을 클릭하고 닫힐 때까지 대기
    - button_index: 0(첫번째, 보통 OK), 1(두번째, 보통 Cancel)
    """
    try:
        page.wait_for_selector(VISIBLE_DIALOG, state="visible", timeout=timeout)
        top_dialog = page.locator(VISIBLE_DIALOG).last
        button = top_dialog.locator(DIALOG_BUTTONS).nth(button_index)
        
        if button.is_visible():
            button.click()
            top_dialog.wait_for(state="hidden", timeout=3000)
            return True
        return False
    except Exception:
        return False