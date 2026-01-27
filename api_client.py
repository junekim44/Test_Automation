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
                
                response_text = self.page.evaluate("""async (args) => {
                    try {
                        const { url, method } = args;
                        const options = method === 'POST' ? { method: 'POST' } : {};
                        const response = await fetch(url, options);
                        if (!response.ok) return `Error: ${response.status}`;
                        return await response.text();
                    } catch (e) { return `Error: ${e.message}`; }
                }""", {"url": api_url, "method": method})
                
                # 401 에러 처리
                if "Error: 401" in response_text and retry_on_401:
                    if attempt < max_retries - 1:
                        print(f"⚠️ [API] 401 Unauthorized (시도 {attempt+1}/{max_retries}). 페이지 새로고침...")
                        self.page.reload()
                        self.page.wait_for_selector("#Page200_id", timeout=TIMEOUTS["page_load"])
                        time.sleep(TIMEOUTS["retry_delay"])
                        continue
                
                # 403 에러 처리 (HTTPS 필요)
                if "Error: 403" in response_text:
                    if action == "userSetup":
                        print(f"   ⚠️ [API] 403 Forbidden: userSetup API는 HTTPS 또는 RSA 암호화가 필요합니다.")
                        print(f"   💡 [Tip] 사용자 관리 작업은 UI로 폴백합니다.")
                    else:
                        print(f"⚠️ [API] 403 Forbidden: {response_text}")
                    return None
                
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

    def get_action_alarmout(self) -> Optional[Dict[str, Any]]:
        """알람 아웃 설정 조회 (actionAlarmout)"""
        return self.get("actionAlarmout")
    
    def set_group_setup(self, group_write_mode: str, group_name: str = None, 
                       authorities: str = None, allow_anonymous_login: str = None,
                       allow_anonymous_ptz: str = None) -> bool:
        """
        그룹 설정 변경 (생성/수정/삭제)
        
        Args:
            group_write_mode: "add" | "edit" | "remove"
            group_name: 그룹 이름 (add/edit 시 필수)
            authorities: 권한 문자열 (예: "setup|search|ptz", add/edit 시 선택)
            allow_anonymous_login: "on" | "off" (선택)
            allow_anonymous_ptz: "on" | "off" (선택)
        
        Returns:
            성공 여부
        """
        params = {"groupWriteMode": group_write_mode}
        if group_name:
            params["groupName"] = group_name
        if authorities:
            params["authorities"] = authorities
        if allow_anonymous_login:
            params["allowAnonymousLogin"] = allow_anonymous_login
        if allow_anonymous_ptz:
            params["allowAnonymousPTZ"] = allow_anonymous_ptz
        
        return self.set("groupSetup", params)
    
    def get_user_setup(self) -> Optional[Dict[str, Any]]:
        """사용자 설정 조회"""
        return self.get("userSetup")
    
    def set_user_setup(self, user_write_mode: str, user_name: str = None,
                       user_password: str = None, user_group: str = None,
                       user_email: str = None, user_sms: str = None,
                       user_country: str = None) -> bool:
        """
        사용자 설정 변경 (생성/수정/삭제)
        
        ⚠️ 주의: userSetup은 HTTPS 또는 RSA 암호화가 필요할 수 있습니다.
        HTTP로 동작하지 않으면 HTTPS로 시도하거나 RSA 암호화를 구현해야 합니다.
        
        Args:
            user_write_mode: "add" | "edit" | "remove"
            user_name: 사용자 ID (필수)
            user_password: 비밀번호 (add/edit 시 필수, remove 시 불필요)
            user_group: 그룹 이름 (예: "Administrator", "User", 또는 사용자 정의 그룹)
            user_email: 이메일 (선택)
            user_sms: SMS 번호 (선택)
            user_country: 국가 코드 (선택, 예: "82" for Korea)
        
        Returns:
            성공 여부
        """
        params = {"userWriteMode": user_write_mode}
        if user_name:
            params["userName"] = user_name
        if user_password:
            params["userPassword"] = user_password
        if user_group:
            params["userGroup"] = user_group
        if user_email:
            params["userEmail"] = user_email
        if user_sms:
            params["userSms"] = user_sms
        if user_country:
            params["userCountry"] = user_country
        
        return self.set("userSetup", params)
    
    def set_group_permissions(self, group_name: str, permissions: dict, 
                              ui_to_api_map: dict) -> bool:
        """
        그룹 권한 설정 (UI 권한 딕셔너리를 API 형식으로 변환)
        
        Args:
            group_name: 그룹 이름
            permissions: UI 권한 딕셔너리 (예: {"설정": True, "검색": False, ...})
            ui_to_api_map: UI 이름 → API 이름 매핑 (예: {"설정": "setup", ...})
        
        Returns:
            성공 여부
        """
        # True인 권한만 추출하여 API 형식으로 변환
        enabled_perms = []
        for ui_name, is_enabled in permissions.items():
            if is_enabled:
                api_name = ui_to_api_map.get(ui_name)
                if api_name:
                    enabled_perms.append(api_name)
        
        # 권한 문자열 생성 (예: "setup|search|clipCopy")
        authorities = "|".join(enabled_perms) if enabled_perms else ""
        
        print(f"   📡 [API] 그룹 '{group_name}' 권한 설정: {authorities}")
        return self.set_group_setup(
            group_write_mode="edit",
            group_name=group_name,
            authorities=authorities
        )
    
    def set_action_alarmout(self, use_alarm_out: str = "on", dwell_time: str = "20", 
                            start: str = "00:00", end: str = "24:00") -> bool:
        """
        알람 출력 설정 변경
        Args:
            use_alarm_out: "on" | "off"
            dwell_time: 유지 시간 (기본 20초)
            start/end: 스케줄 시작/종료 시간
        """
        params = {
            "useAlarmOut": use_alarm_out,
            "dwellTime": dwell_time,
            "scheduleStart": start,
            "scheduleEnd": end
        }
        print(f"   📡 [API] 알람 출력 설정 변경: {use_alarm_out}")
        return self.set("actionAlarmout", params)
    
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
