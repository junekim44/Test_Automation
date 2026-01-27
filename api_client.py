"""
통합 API 클라이언트 모듈
모든 API 호출을 일관된 방식으로 처리합니다.
"""

import time
from typing import Optional, Dict, Any
from playwright.sync_api import Page
from common_actions import parse_api_response
from config import TIMEOUTS


class CameraApiClient:
    """
    Playwright 기반 API 클라이언트
    모든 API 호출을 통합 관리합니다.
    """
    
    def __init__(self, page: Page, camera_ip: str, base_port: str = "80"):
        self.page = page
        self.camera_ip = camera_ip
        self.base_port = base_port
        self.base_url = f"http://{camera_ip}:{base_port}/cgi-bin/webSetup.cgi"
    
    def _make_request(self, action: str, mode: str = "1", params: Optional[Dict[str, Any]] = None, 
                     method: str = "GET", retry_on_401: bool = True) -> Optional[Dict[str, Any]]:
        """
        통합 API 요청 함수
        
        Args:
            action: API 액션 이름 (예: "systemInfo", "videoEasySetting")
            mode: 모드 ("1"=읽기, "0"=쓰기, "2"=확인)
            params: POST 요청 시 파라미터 딕셔너리
            method: HTTP 메서드 ("GET" 또는 "POST")
            retry_on_401: 401 에러 시 재시도 여부
        
        Returns:
            파싱된 응답 딕셔너리 또는 None
        """
        max_retries = TIMEOUTS["max_retries"]
        
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    api_url = f"{self.base_url}?action={action}&mode={mode}"
                    if params:
                        query_str = "&".join([f"{k}={v}" for k, v in params.items()])
                        api_url += f"&{query_str}"
                else:  # POST
                    if params:
                        query_str = "&".join([f"{k}={v}" for k, v in params.items()])
                        api_url = f"{self.base_url}?action={action}&mode={mode}&{query_str}"
                    else:
                        api_url = f"{self.base_url}?action={action}&mode={mode}"
                
                response_text = self.page.evaluate("""async (url, method) => {
                    try {
                        const options = method === 'POST' ? { method: 'POST' } : {};
                        const response = await fetch(url, options);
                        if (!response.ok) return `Error: ${response.status}`;
                        return await response.text();
                    } catch (e) { return `Error: ${e.message}`; }
                }""", api_url, method)
                
                # 401 에러 처리
                if "Error: 401" in response_text and retry_on_401:
                    if attempt < max_retries - 1:
                        print(f"⚠️ [API] 401 Unauthorized (시도 {attempt+1}/{max_retries}). 페이지 새로고침...")
                        self.page.reload()
                        self.page.wait_for_selector("#Page200_id", timeout=TIMEOUTS["page_load"])
                        time.sleep(TIMEOUTS["retry_delay"])
                        continue
                
                # 에러 응답 처리
                if response_text and response_text.startswith("Error"):
                    print(f"⚠️ [API] 응답 오류: {response_text}")
                    if attempt < max_retries - 1:
                        time.sleep(TIMEOUTS["retry_delay"])
                        continue
                    return None
                
                # 성공 응답 파싱
                if response_text:
                    return parse_api_response(response_text)
                    
            except Exception as e:
                print(f"⚠️ [API] 에러 (시도 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(TIMEOUTS["retry_delay"])
                else:
                    return None
        
        return None
    
    def get(self, action: str, mode: str = "1") -> Optional[Dict[str, Any]]:
        """설정 읽기 (GET)"""
        return self._make_request(action, mode, method="GET")
    
    def set(self, action: str, params: Dict[str, Any], mode: str = "0") -> bool:
        """
        설정 쓰기 (POST)
        
        Returns:
            성공 여부 (returnCode=0 또는 returnCode=301 포함 시 True)
        """
        # returnCode 제거 (읽기 전용 필드)
        clean_params = {k: v for k, v in params.items() if k != "returnCode"}
        
        response = self._make_request(action, mode, clean_params, method="POST")
        
        if response:
            return_code = response.get("returnCode", "")
            # 0: 성공, 301: 재부팅/재접속 필요 (성공으로 간주)
            if return_code == "0" or return_code == "301":
                return True
            else:
                print(f"   ❌ [API Fail] 요청: {clean_params}")
                print(f"   ❌ [API Fail] 응답: returnCode={return_code}")
        
        return False
    
    # ===========================================================
    # 편의 메서드들 (기존 코드 호환성 유지)
    # ===========================================================
    
    def get_system_info(self) -> Optional[Dict[str, Any]]:
        """시스템 정보 조회"""
        return self.get("systemInfo")
    
    def get_note(self) -> Optional[str]:
        """설명(Note) 값 조회"""
        data = self.get_system_info()
        return data.get("note", "") if data else None
    
    def get_language(self) -> Optional[str]:
        """언어 설정 조회"""
        data = self.get_system_info()
        return data.get("language") if data else None
    
    def get_datetime(self) -> Optional[Dict[str, Any]]:
        """날짜/시간 설정 조회"""
        return self.get("dateTime")
    
    def get_group_setup(self) -> Optional[Dict[str, Any]]:
        """그룹 설정 조회"""
        return self.get("groupSetup")
    
    # Video 관련
    def get_video_easy_setting(self) -> Optional[Dict[str, Any]]:
        return self.get("videoEasySetting")
    
    def set_video_easy_setting(self, params: Dict[str, Any]) -> bool:
        return self.set("videoEasySetting", params)
    
    def get_video_image(self) -> Optional[Dict[str, Any]]:
        return self.get("videoImage")
    
    def set_video_image(self, params: Dict[str, Any]) -> bool:
        return self.set("videoImage", params)
    
    def get_video_wb(self) -> Optional[Dict[str, Any]]:
        return self.get("videoWb")
    
    def set_video_wb(self, params: Dict[str, Any]) -> bool:
        return self.set("videoWb", params)
    
    def get_video_exposure(self) -> Optional[Dict[str, Any]]:
        return self.get("videoExposure")
    
    def set_video_exposure(self, params: Dict[str, Any]) -> bool:
        return self.set("videoExposure", params)
    
    def get_video_daynight(self) -> Optional[Dict[str, Any]]:
        return self.get("videoDaynight")
    
    def set_video_daynight(self, params: Dict[str, Any]) -> bool:
        return self.set("videoDaynight", params)
    
    def get_video_misc(self) -> Optional[Dict[str, Any]]:
        return self.get("videoMisc")
    
    def set_video_misc(self, params: Dict[str, Any]) -> bool:
        return self.set("videoMisc", params)
    
    def get_video_streaming(self) -> Optional[Dict[str, Any]]:
        return self.get("videoStreaming")
    
    def set_video_streaming(self, params: Dict[str, Any]) -> bool:
        return self.set("videoStreaming", params)
