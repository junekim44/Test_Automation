import argparse
import time
import subprocess
import sys
import ctypes
import socket
import re
import requests
from urllib.parse import parse_qsl
from requests.auth import HTTPDigestAuth
from scapy.all import ARP, Ether, srp, sniff, conf
from playwright.sync_api import sync_playwright

# 사용자 정의 모듈
import config  # 설정 파일 Import
import iRAS_test
import webgaurd

# Scapy 출력 끄기
conf.verb = 0

# =========================================================
# 🛡️ [System] 윈도우 네트워크 제어 유틸리티
# =========================================================

def check_port_open(ip, port, timeout=3):
    """지정된 IP와 포트가 실제(Socket)로 열려있는지 확인"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((ip, int(port))) == 0

def get_local_ip():
    """현재 PC의 IP 주소를 반환"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return socket.gethostbyname(socket.gethostname())

class NetworkManager:
    @staticmethod
    def run_cmd(cmd):
        try:
            subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @staticmethod
    def set_static_ip(ip, subnet, gw=None):
        print(f"💻 [System] PC IP 고정 설정 -> {ip}")
        gw_cmd = f" {gw}" if gw else ""
        cmd = f'netsh interface ip set address name="{config.INTERFACE_NAME}" static {ip} {subnet}{gw_cmd}'
        NetworkManager.run_cmd(cmd)
        time.sleep(5)

    @staticmethod
    def set_dhcp():
        print("💻 [System] PC IP DHCP(자동) 설정 변경 중...")
        NetworkManager.run_cmd(f'netsh interface ip set address name="{config.INTERFACE_NAME}" source=dhcp')
        NetworkManager.run_cmd(f'netsh interface ip set dns name="{config.INTERFACE_NAME}" source=dhcp')
        time.sleep(3)

    @staticmethod
    def wait_for_dhcp(prefix="10.", timeout=60):
        print("💻 [System] IP 할당 대기 중...", end="")
        NetworkManager.run_cmd("ipconfig /renew")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                output = subprocess.check_output("ipconfig", shell=True, encoding='cp949', errors='ignore')
                if f": {prefix}" in output:
                    print(" 완료! ✅")
                    return True
            except: pass
            print(".", end="", flush=True)
            time.sleep(2)
        print(" 실패 ❌")
        return False

    @staticmethod
    def ping(ip, timeout=30):
        print(f"📡 [Ping] {ip} 통신 확인 중...", end="")
        start = time.time()
        while time.time() - start < timeout:
            if subprocess.call(f"ping -n 1 -w 500 {ip}", shell=True, stdout=subprocess.DEVNULL) == 0:
                print(" 연결됨! ✅")
                return True
            print(".", end="", flush=True)
            time.sleep(1)
        print(" 응답 없음 ❌")
        return False

# =========================================================
# 🔍 [Scanner] 네트워크 장치 탐색 (최적화 버전)
# =========================================================
# =========================================================
# 🔍 [Scanner] 네트워크 장치 탐색
# =========================================================
class CameraScanner:
    @staticmethod
    def normalize_mac(mac):
        if not mac: return ""
        return mac.lower().replace("-", ":").replace(".", "")

    @staticmethod
    def scan_onvif(timeout=2):
        discovery_msg = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
            b'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
            b'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
            b'xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
            b'<e:Header>'
            b'<w:MessageID>uuid:84ede3de-7dec-11d0-c360-f01234567890</w:MessageID>'
            b'<w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
            b'<w:Action a:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>'
            b'</e:Header>'
            b'<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>'
            b'</e:Envelope>'
        )
        found_ips = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                sock.settimeout(timeout)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(discovery_msg, ('239.255.255.250', 3702))
                start = time.time()
                while time.time() - start < timeout:
                    try:
                        data, addr = sock.recvfrom(65536)
                        resp_str = data.decode('utf-8', errors='ignore')
                        ips = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', resp_str)
                        for ip in ips:
                            if ip not in ["0.0.0.0", "239.255.255.250"]:
                                found_ips.append(ip)
                        found_ips.append(addr[0]) 
                    except socket.timeout: break
        except: pass
        return list(set(found_ips))

    @staticmethod
    def scan_arp(target_mac, scan_range, timeout=2):
        if "/16" in scan_range or "/8" in scan_range: return None
        try:
            ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=scan_range), 
                         timeout=timeout, verbose=0, iface=config.INTERFACE_NAME)
            for _, rcv in ans:
                if CameraScanner.normalize_mac(rcv.hwsrc) == target_mac:
                    return rcv.psrc
        except: pass
        return None

    @staticmethod
    def sniff_target_packet(target_mac, timeout=5):
        found_ip = None
        target_mac = CameraScanner.normalize_mac(target_mac)

        def packet_handler(pkt):
            nonlocal found_ip
            if pkt.haslayer(Ether):
                src = CameraScanner.normalize_mac(pkt[Ether].src)
                if src == target_mac:
                    if pkt.haslayer(ARP):
                        found_ip = pkt[ARP].psrc
                        return True
                    elif pkt.haslayer("IP"):
                        found_ip = pkt["IP"].src
                        return True
            return False

        try:
            sniff(iface=config.INTERFACE_NAME, stop_filter=packet_handler, timeout=timeout, store=0)
        except: pass
        return found_ip

    @staticmethod
    def find_ip_combined(target_mac, scan_range, timeout=40):
        print(f"🔍 [Scanner] MAC({target_mac}) 탐색 시작 ({scan_range})...", end="", flush=True)
        target_mac = CameraScanner.normalize_mac(target_mac)
        target_mac_dash = target_mac.replace(":", "-")
        is_link_local = "169.254" in scan_range
        is_large_subnet = "/16" in scan_range
        
        start_time = time.time()
        last_cache_check = 0
        
        while time.time() - start_time < timeout:
            current_time = time.time()
            if current_time - last_cache_check > 3:
                last_cache_check = current_time
                try:
                    out = subprocess.check_output("arp -a", shell=True).decode('cp949', errors='ignore')
                    for line in out.splitlines():
                        if target_mac_dash in line.lower():
                            parts = line.split()
                            if len(parts) < 1: continue
                            ip = parts[0]
                            if ip in ["0.0.0.0", "255.255.255.255"]: continue
                            
                            if (is_link_local and not ip.startswith("169.254")) or \
                               (not is_link_local and ip.startswith("169.254")):
                                continue
                            
                            if subprocess.call(f"ping -n 1 -w 500 {ip}", shell=True, stdout=subprocess.DEVNULL) == 0:
                                print(f" (ARP Cache) ✅ {ip}")
                                return ip
                except: pass
            
            if is_large_subnet:
                found_ip = CameraScanner.sniff_target_packet(target_mac, timeout=2)
                if found_ip and found_ip != "0.0.0.0":
                    if (is_link_local and found_ip.startswith("169.254")) or \
                       (not is_link_local and not found_ip.startswith("169.254")):
                        print(f" (Sniffing) ✅ {found_ip}")
                        return found_ip
            else:
                CameraScanner.scan_onvif(timeout=1)
                found_ip = CameraScanner.scan_arp(target_mac, scan_range, timeout=2)
                if found_ip and found_ip != "0.0.0.0":
                    print(f" (Active ARP) ✅ {found_ip}")
                    return found_ip
            
            print(".", end="", flush=True)
            time.sleep(1)
        
        print(" ❌ 실패")
        return None
    

# =========================================================
# 🌐 [Web UI] Playwright 컨트롤러
# =========================================================
class WebController:
    def __init__(self, playwright_instance, ip, port, user_id, user_pw):
        self.ip = ip
        self.port = port
        self.user_id = user_id
        self.user_pw = user_pw
        self.browser = playwright_instance.chromium.launch(headless=False)
        self.context = self.browser.new_context(
            http_credentials={"username": user_id, "password": user_pw}
        )
        self.page = self.context.new_page()

    def close(self):
        self.browser.close()

    def _click_and_wait(self, selector):
        try:
            self.page.click(selector, timeout=3000)
            time.sleep(0.5)
        except: pass

    def get_mac_address(self):
        print(f"🌐 [Web] MAC 주소 추출 시도: {self.ip}")
        try:
            self.page.goto(f"http://{self.ip}:{self.port}/setup/setup.html", timeout=10000)
            self.page.wait_for_selector("#Page200_id", timeout=5000)
            self._click_and_wait("#Page200_id")
            self._click_and_wait("#Page201_id")
            mac = self.page.input_value("#mac-addressInfo", timeout=3000).strip()
            print(f"   ✅ MAC Found: {mac}")
            return mac
        except Exception as e:
            print(f"   ⚠️ Web Error: {e}")
            return None

# =========================================================
# 🕵️ [API] 카메라 설정 검증기
# =========================================================
class CameraApi:
    def __init__(self, ip, port, user_id, user_pw):
        self.base_url = f"http://{ip}:{port}/cgi-bin/webSetup.cgi"
        self.session = requests.Session()
        self.session.auth = HTTPDigestAuth(user_id, user_pw)

    def _get_config(self, action):
        try:
            url = f"{self.base_url}?action={action}&mode=1"
            res = self.session.get(url, timeout=5)
            if res.status_code == 200:
                return dict(parse_qsl(res.text))
        except Exception: pass
        return {}

    def _post_config(self, payload, timeout=10):
        try:
            res = self.session.post(self.base_url, data=payload, timeout=timeout)
            if "returnCode=0" in res.text or "returnCode=301" in res.text:
                return True, res.text
            return False, res.text
        except requests.exceptions.ReadTimeout:
            return True, "Timeout (Expected)" # IP 변경 등에서 발생 가능
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            # 포트 변경 중 연결이 끊기는 것은 정상 (포트가 변경되면서 연결이 끊김)
            error_str = str(e)
            if "Connection aborted" in error_str or "Remote end closed" in error_str or "RemoteDisconnected" in error_str:
                return True, "Connection closed (Expected during port change)"
            return False, str(e)
        except Exception as e:
            return False, str(e)

    def set_link_local_api(self, enable=True):
        val = "on" if enable else "off"
        print(f"📡 [API] Link-Local 설정: {val}...", end="")
        current = self._get_config("networkIp")
        if not current: return False
        
        current.update({"action": "networkIp", "mode": "0", "linkLocalOnly": val})
        if "returnCode" in current: del current["returnCode"]
        
        success, msg = self._post_config(current)
        print(" 성공 ✅" if success else f" 실패 ❌ ({msg.strip()})")
        return success

    def set_fen_api(self, fen_name, fen_server):
        print(f"📡 [API] FEN 설정 요청: {fen_name} ({fen_server})...", end="")
        payload = {
            "action": "networkDDNS", "mode": "0", "useDDNS": "on",
            "serverAddress": fen_server, "port": str(config.FEN_PORT), 
            "cameraName": fen_name, "useNAT": "off"
        }
        success, msg = self._post_config(payload)
        if not success:
            print(f" 설정 실패 ❌ (Code: {msg.strip()})")
            return False
            
        time.sleep(2)
        print("   -> FEN 이름 유효성 검사...", end="")
        check_payload = payload.copy()
        check_payload["mode"] = "2"
        success, _ = self._post_config(check_payload)
        print(" 확인 완료 ✅" if success else " 확인 실패 ❌")
        return success

    def verify_fen_setting(self, expected_server):
        data = self._get_config("networkDDNS")
        valid = (data.get("useDDNS") == "on" and data.get("serverAddress") == expected_server)
        print(f"📡 [API] FEN 검증: {'Pass' if valid else 'Fail'}")
        return valid

    def set_upnp_api(self, enable=True):
        val = "on" if enable else "off"
        print(f"📡 [API] UPNP 설정: {val}...", end="")
        success, msg = self._post_config({"action": "networkPort", "mode": "0", "useUPNP": val})
        print(" 성공 ✅" if success else f" 실패 ❌ ({msg.strip()})")
        return success

    def set_ports_api(self, web_port=None, remote_port=None):
        current_ip = self.base_url.split("://")[1].split(":")[0]
        print(f"📡 [API] 포트 변경 요청: Web={web_port}, Service={remote_port}...", end="")
        
        cfg = self._get_config("networkPort")
        target_web = str(web_port) if web_port else cfg.get("webPort", "80")
        target_svc = str(remote_port) if remote_port else cfg.get("remotePort", "8016")

        payload = {
            "action": "networkPort", "mode": "0",
            "useWeb": cfg.get("useWeb", "on"), "useRtsp": cfg.get("useRtsp", "on"),
            "useUPNP": cfg.get("useUPNP", "off"), "useHTTPS": cfg.get("useHTTPS", "off"),
            "webPort": target_web, "adminPort": target_svc, "watchPort": target_svc,
            "searchPort": target_svc, "remotePort": target_svc,
            "rtspPort": cfg.get("rtspPort", "554"), "recordPort": cfg.get("recordPort", "8017"),
        }
        
        self._post_config(payload, timeout=3) # 끊김 허용

        # 검증 (새 세션)
        verify_url = f"http://{current_ip}:{target_web}/cgi-bin/webSetup.cgi"
        print(f"\n   -> 🔄 변경된 포트({target_web})로 검증 시도...", end="")
        
        new_session = requests.Session()
        new_session.auth = self.session.auth
        
        for _ in range(20):
            try:
                time.sleep(1)
                res = new_session.get(f"{verify_url}?action=networkPort&mode=1", timeout=2)
                if res.status_code == 200 and f"webPort={target_web}" in res.text:
                    print(" 성공 🎯")
                    self.session = new_session
                    self.base_url = verify_url
                    return True
            except: print(".", end="")
        print(" 실패 ❌")
        return False

    def reset_ports_default(self):
        print("🚑 [API] 포트 기본값 복구 요청...", end="")
        current_ip = self.base_url.split("://")[1].split(":")[0]
        current_port = self.base_url.split("://")[1].split(":")[1].split("/")[0] if ":" in self.base_url.split("://")[1] else "80"
        
        # 현재 설정을 먼저 가져와서 필요한 값들 보존
        current_cfg = self._get_config("networkPort")
        if not current_cfg:
            print(f" 실패 ❌ (현재 설정 조회 실패)")
            return False
        
        payload = {
            "action": "networkPort", "mode": "0", 
            "useWeb": current_cfg.get("useWeb", "on"), 
            "useRtsp": current_cfg.get("useRtsp", "on"),
            "useHTTPS": current_cfg.get("useHTTPS", "off"), 
            "useUPNP": current_cfg.get("useUPNP", "off"),
            "webPort": "80", "rtspPort": current_cfg.get("rtspPort", "554"), 
            "recordPort": current_cfg.get("recordPort", "8016"),
            "adminPort": "8016", "watchPort": "8016", "searchPort": "8016", "remotePort": "8016"
        }
        
        # 포트 변경 요청 (타임아웃 증가)
        success, msg = self._post_config(payload, timeout=10)
        if not success:
            print(f" 실패 ❌ ({msg.strip()})")
            # 실패해도 검증 시도 (포트가 이미 80일 수도 있음)
        else:
            # 연결 끊김은 포트 변경 중 정상적인 현상
            if "Connection closed" in msg or "Expected" in msg:
                print(" 요청 완료 ")
            else:
                print(" 요청 완료")
        
        # 포트 변경 후 연결이 끊길 수 있으므로 대기
        time.sleep(8)
        
        # 검증: 포트 80으로 접속 가능한지 확인
        verify_url = f"http://{current_ip}:80/cgi-bin/webSetup.cgi"
        print(f"\n   -> 🔄 복구된 포트(80)로 검증 시도...", end="")
        
        new_session = requests.Session()
        new_session.auth = self.session.auth
        
        for attempt in range(30):
            try:
                time.sleep(1)
                res = new_session.get(f"{verify_url}?action=networkPort&mode=1", timeout=3)
                if res.status_code == 200:
                    # webPort=80 확인
                    if "webPort=80" in res.text:
                        print(" 성공 🎯")
                        self.session = new_session
                        self.base_url = verify_url
                        return True
                    # 이미 80이 아닐 수도 있으므로 현재 값 확인
                    elif "webPort=" in res.text:
                        match = re.search(r'webPort=(\d+)', res.text)
                        if match:
                            actual_port = match.group(1)
                            if actual_port == "80":
                                print(" 성공 🎯")
                                self.session = new_session
                                self.base_url = verify_url
                                return True
            except Exception as e:
                if attempt < 5:  # 처음 5번만 출력
                    print(".", end="")
        
        print(" 실패 ❌")
        return False

    def set_bandwidth_limit(self, enable=True, limit_kbps=102400):
        print(f"📡 [API] 대역폭 제한: {'ON' if enable else 'OFF'}...", end="")
        payload = {"action": "networkBandwidth", "mode": "0", 
                   "useNetworkBandwidth": "on" if enable else "off", "networkBandwidth": str(limit_kbps)}
        success, msg = self._post_config(payload)
        print(" 성공 ✅" if success else f" 실패 ❌ ({msg.strip()})")
        return success

    def set_ip_filter(self, mode="off", allow_list="", deny_list=""):
        print(f"🛡️ [API] IP 필터: {mode}...", end="")
        payload = {"action": "networkSecurity", "mode": "0", "filterType": mode, 
                   "allowList": allow_list, "denyList": deny_list, "useSSL": "off"}
        success, msg = self._post_config(payload)
        print(" 성공 ✅" if success else f" 실패 ❌ ({msg.strip()})")
        return success

    def set_ssl(self, enable=True, ssl_type="standard"):
        val = "on" if enable else "off"
        print(f"🔒 [API] SSL 설정: {val} ({ssl_type})...", end="")
        payload = {"action": "networkSecurity", "mode": "0", "useSSL": val, "sslType": ssl_type, "filterType": "off"}
        success, msg = self._post_config(payload)
        print(" 성공 ✅" if success else f" 실패 ❌ ({msg.strip()})")
        return success

    def set_ip_address_api(self, mode_type="manual", ip=None, gateway=None, subnet=None, link_local_off=False):
        print(f"📡 [API] 네트워크 변경: {mode_type}...", end="")
        current = self._get_config("networkIp")
        if not current: return False
        
        current.update({"action": "networkIp", "mode": "0", "type": mode_type})
        if link_local_off: current["linkLocalOnly"] = "off"
        if mode_type == "manual":
            current.update({"ipAddress": ip, "gateway": gateway, "subnetMask": subnet})
            if not current.get("dnsServer"): current["dnsServer"] = gateway

        if "returnCode" in current: del current["returnCode"]
        if "ipv6Address" in current: del current["ipv6Address"]

        success, msg = self._post_config(current, timeout=10)
        print(" 성공 ✅" if success else f" 실패 ❌ ({msg.strip()})")
        return success
    

# =========================================================
# 🚀 Main Execution Flow
# =========================================================

def _run_web_action(action_func, ctx, *args, **kwargs):
    """Playwright 실행 래퍼 (자동 종료 보장)"""
    controller = None
    try:
        with sync_playwright() as p:
            controller = WebController(p, ctx["CAM_IP"], ctx["PORT"], ctx["ID"], ctx["PW"])
            result = action_func(controller, *args, **kwargs)
            # 🔥 명시적으로 브라우저 닫기 (자동 진행 보장)
            if controller:
                controller.close()
            return result
    except Exception as e:
        print(f"🔥 Web Action Error: {e}")
        # 예외 발생 시에도 브라우저 닫기 보장
        if controller:
            try:
                controller.close()
            except: pass
        return None

def _action_get_mac(web): return web.get_mac_address()
def _action_verify_web_access(web, port):
    """Web Setup 페이지 접속 확인 (사용자 확인 대기)"""
    target_url = f"http://{web.ip}:{port}/setup/setup.html"
    print(f"   🌐 접속 시도: {target_url}")
    try:
        # Setup 페이지로 이동
        web.page.goto(target_url, timeout=15000)
        # DOM 로딩 완료 대기
        web.page.wait_for_load_state("domcontentloaded", timeout=10000)
        # 페이지 타이틀 출력
        title = web.page.title()
        print(f"   ✅ 페이지 로드 완료 (Title: {title})")
        print(f"   👀 브라우저에서 페이지를 확인하세요. 확인 후 'Enter'를 누르세요...")
        input()  # 사용자 확인 대기
        return True
    except Exception as e:
        print(f"   ❌ Web 접속 실패: {e}")
        return False

def _action_webguard_login(web_dummy, fen_url, user, pw):
    try:
        web_dummy.page.goto(fen_url); time.sleep(5)
        return webgaurd.run_login(user, pw)
    except: return False

def _refresh_session(api_obj):
    print("\n🔄 [Session Refresh] iRAS 세션 갱신 (SSL Toggle)...")
    try:
        if api_obj.set_ssl(enable=True):
            time.sleep(10)
            if api_obj.set_ssl(enable=False):
                time.sleep(10); return True
    except Exception as e:
        print(f"   🔥 세션 갱신 로직 에러: {e}")
    return False

def run_integrated_network_test(args):
    """
    통합 네트워크 테스트 실행
    """
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return False, "관리자 권한이 필요합니다."

    # Runtime Context 초기화 (Config + Args Override)
    ctx = {
        "CAM_IP": args.ip or config.CAMERA_IP,
        "PORT": config.CAMERA_PORT, # 초기 포트는 80
        "ID": args.id or config.USERNAME,
        "PW": args.pw or config.PASSWORD,
        "IFACE": args.iface or config.INTERFACE_NAME,
        "FEN_SVR": config.FEN_SERVER,
        "FEN_NAME": config.FEN_NAME
    }

    # config 모듈의 인터페이스 이름 업데이트 (Scanner 등에서 사용)
    config.INTERFACE_NAME = ctx["IFACE"]

    print("\n=== 🚀 Network & Automation Test Integrated Run ===")
    target_mac = None

    try:
        # [Step 1] PC IP 고정 및 MAC 주소 획득
        print("\n>>> [Step 1] Link-Local 활성화 준비")
        NetworkManager.set_static_ip(config.PC_STATIC_IP, config.PC_SUBNET, config.PC_GW)
        
        if NetworkManager.ping(ctx["CAM_IP"]):
            target_mac = _run_web_action(_action_get_mac, ctx)
            if target_mac:
                api = CameraApi(ctx["CAM_IP"], ctx["PORT"], ctx["ID"], ctx["PW"])
                api.set_link_local_api(enable=True)
        else: return False, "초기 카메라 접속 실패"

        if not target_mac: return False, "MAC 주소 확보 실패"

        # [Step 2] Auto-IP 검증 및 DHCP 전환
        print("\n>>> [Step 2] 169.254 Link-Local IP 검증 및 DHCP 설정")
        NetworkManager.set_static_ip(config.PC_AUTO_IP, config.AUTO_SUBNET)
        NetworkManager.run_cmd("arp -d *")
        time.sleep(3)
        
        auto_ip = CameraScanner.find_ip_combined(target_mac, config.SCAN_AUTO_NET, timeout=40)
        
        if auto_ip and "169.254" in auto_ip:
            print(f"🎉 Auto-IP 접속 성공: {auto_ip}")
            api_auto = CameraApi(auto_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
            api_auto.set_ip_address_api(mode_type="dhcp", link_local_off=True)
        else:
            print("⚠️ Auto-IP 탐색 실패")

        # [Step 4] PC DHCP 복구 및 카메라 새 IP 탐색
        print("\n>>> [Step 4] PC DHCP 복귀 및 카메라 새 IP 탐색")
        NetworkManager.set_dhcp()
        
        new_dhcp_ip = None
        if NetworkManager.wait_for_dhcp("10."):
            NetworkManager.run_cmd("arp -d *")
            time.sleep(3)
            
            start_scan = time.time()
            while time.time() - start_scan < 60:
                temp_ip = CameraScanner.find_ip_combined(target_mac, config.SCAN_NET, timeout=8)
                if temp_ip:
                    if temp_ip.startswith("169.254"):
                        NetworkManager.run_cmd("arp -d *"); time.sleep(3); continue
                    
                    if temp_ip == ctx["CAM_IP"]: # 기존 IP와 동일하면 ping 확인
                        if subprocess.call(f"ping -n 1 -w 1000 {temp_ip}", shell=True, stdout=subprocess.DEVNULL) == 0:
                            new_dhcp_ip = temp_ip; break
                        else: NetworkManager.run_cmd("arp -d *"); continue
                    
                    new_dhcp_ip = temp_ip; break
                time.sleep(3)

            # [Step 5] FEN 설정 및 iRAS 연동
            if new_dhcp_ip:
                print(f"✅ 카메라 DHCP IP: {new_dhcp_ip}")
                api = CameraApi(new_dhcp_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
                api.set_fen_api(ctx["FEN_NAME"], ctx["FEN_SVR"])
                api.verify_fen_setting(ctx["FEN_SVR"])
                
                # iRAS Setup
                if iRAS_test.run_fen_setup_process(config.IRAS_DEVICE_NAME, ctx["FEN_NAME"]):
                    iRAS_test.wait_for_connection()
                    
                    # Session Refresh (SSL Toggle)
                    api.set_ssl(True); time.sleep(10); api.set_ssl(False); time.sleep(10)

                    if iRAS_test.run_fen_verification("TcpDirectExternal"):
                        print("🎉 [Pass] TcpDirectExternal")
                    else:
                        print("⚠️ 1차 검증 실패, 재시도...")
                        if iRAS_test.run_fen_verification("TcpDirectExternal"): print("🎉 [Pass] 재시도 성공")
            else:
                return False, "DHCP IP 탐색 실패"

        # [Step 7 ~ 9] NAT/UPNP Test (공유기 이동 필요)
        router_cam_ip = None
        if new_dhcp_ip:
            print("\n>>> [Step 7] UPNP 활성화 및 DirectInternal 검증")
            input("🚨 [ACTION] 카메라와 PC를 '공유기'에 연결하고 Enter >> ")
            NetworkManager.set_dhcp(); NetworkManager.wait_for_dhcp("192.")
            
            router_cam_ip = CameraScanner.find_ip_combined(target_mac, config.SCAN_NET, timeout=40)
            if not router_cam_ip: router_cam_ip = auto_ip

            if router_cam_ip:
                print(f"✅ Router IP: {router_cam_ip}")
                api = CameraApi(router_cam_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
                api.set_upnp_api(True)
                iRAS_test.wait_for_connection()
                if iRAS_test.run_fen_verification("TcpDirectInternal"): print("🎉 [Pass] TcpDirectInternal")

                # Step 8
                print("\n>>> [Step 8] UDP Hole Punching")
                api.set_upnp_api(False); time.sleep(5)
                # Session Refresh
                api.set_ssl(True); time.sleep(5); api.set_ssl(False); time.sleep(5)

                input("🚨 [ACTION] PC만 '사내망'으로 이동하고 Enter >> ")
                NetworkManager.set_dhcp(); NetworkManager.wait_for_dhcp("10.")
                iRAS_test.wait_for_connection()
                if iRAS_test.run_fen_verification("UdpHolePunching"): print("🎉 [Pass] UdpHolePunching")

                # Step 9
                print("\n>>> [Step 9] FEN Relay")
                input("🚨 [ACTION] 공유기 'UDP 차단' 후 사내망 복귀 Enter >> ")
                iRAS_test.wait_for_connection()
                if iRAS_test.run_fen_verification("Relay"): print("🎉 [Pass] FEN Relay")

                input("🚨 [ACTION] '카메라'를 사내망으로 복귀 후 Enter >> ")

                # ARP 캐시를 미리 한 번 지워주면 더 좋습니다.
                NetworkManager.run_cmd("arp -d *")
                
                new_dhcp_ip = CameraScanner.find_ip_combined(target_mac, config.SCAN_NET, timeout=20)

                # [안전 장치 추가] 만약 여기서 IP 못 찾으면 뒤에 Step 11도 무조건 실패하므로, 갱신해줍니다.
                if new_dhcp_ip:
                    current_test_ip = new_dhcp_ip
                    ctx["CAM_IP"] = new_dhcp_ip # 컨텍스트 업데이트
                    print(f"   ✅ 사내망 복귀 완료. IP: {new_dhcp_ip}")
                else:
                    print("   ❌ 사내망 IP 탐색 실패. (Step 11 진행 불가)")
                    # 여기서 return False를 하거나, 예외를 던지는 것이 좋지만 일단 진행한다면 로그라도 남깁니다.

        # [Step 10] WebGuard
        if new_dhcp_ip:
            print("\n>>> [Step 10] WebGuard Login")
            fen_url = f"http://{ctx['FEN_SVR']}/{ctx['FEN_NAME']}"
            if _run_web_action(_action_webguard_login, ctx, fen_url, ctx["ID"], ctx["PW"]):
                print("🎉 [Pass] WebGuard Login")

        # [Step 15] 복구 (고정 IP로)
        if new_dhcp_ip:
            print("\n>>> [Step 15] 네트워크 설정 복구")
            api = CameraApi(new_dhcp_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
            if api.set_ip_address_api("manual", config.CAMERA_IP, config.PC_GW, config.PC_SUBNET):
                time.sleep(5)
                if NetworkManager.ping(config.CAMERA_IP, timeout=10):
                    if iRAS_test.run_restore_ip_process(config.IRAS_DEVICE_NAME, config.CAMERA_IP):
                        print("✅ 복구 완료")
                        iRAS_test.wait_for_connection()

        # [Step 11] 포트 변경 테스트
        current_test_ip = config.CAMERA_IP
        if current_test_ip:
            print("\n>>> [Step 11] 포트 변경 테스트 (HTTP:8080, Remote:9200)")
            
            if not NetworkManager.ping(current_test_ip, timeout=5):
                print(f"   ⚠️ 카메라({current_test_ip}) 연결 실패. Step 11 스킵")
            else:
                api = CameraApi(current_test_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
                
                try:
                    # [1] 포트 변경: HTTP 80->8080, Remote 8016->9200
                    print(f"   [1] 포트 변경 API (HTTP: 80 -> 8080, Remote: 8016 -> 9200)...")
                    if api.set_ports_api(web_port="8080", remote_port="9200"):
                        ctx["PORT"] = "8080"
                        print("   ✅ 포트 변경 성공")
                        time.sleep(3)
                        
                        # [2] 웹 접속 확인: IP:8080/setup/setup.html
                        print(f"\n   [2] 웹 접속 확인 (http://{current_test_ip}:8080/setup/setup.html)...")
                        if _run_web_action(_action_verify_web_access, ctx, "8080"):
                            print("   ✅ 웹 접속 확인 완료")
                        else:
                            print("   ⚠️ 웹 접속 실패")
                        
                        # [3] iRAS 9200포트 검색 및 확인
                        print(f"\n   [3] iRAS 9200포트 검색...")
                        if iRAS_test.run_port_change_process(config.IRAS_DEVICE_NAME, "9200", current_test_ip):
                            print("   ✅ iRAS 9200포트 검색 확인 완료")
                        else:
                            print("   ⚠️ iRAS 설정 변경 실패")
                        
                        # [4] 포트 복구: HTTP 80, Remote 8016
                        print(f"\n   [4] 포트 복구 (HTTP: 80, Remote: 8016)...")
                        recovery_api = CameraApi(current_test_ip, "8080", ctx["ID"], ctx["PW"])
                        if recovery_api.reset_ports_default():
                            print("   ✅ 포트 복구 완료")
                            ctx["PORT"] = "80"
                            time.sleep(3)
                            
                            # [5] Live 화면 연결 확인
                            print(f"\n   [5] Live 화면 연결 확인...")
                            if iRAS_test.wait_for_connection(timeout=30):
                                print("   ✅ Live 화면 연결 확인 완료")
                            else:
                                print("   ⚠️ Live 화면 연결 실패")
                        else:
                            print("   ❌ 포트 복구 실패")
                    else:
                        print("   ❌ 포트 변경 API 실패")
                        
                except Exception as e:
                    print(f"   🔥 포트 변경 테스트 중 오류: {e}")

        # [Step 12] 대역폭
        if current_test_ip:
            print("\n>>> [Step 12] 대역폭 제한 테스트")
            api = CameraApi(current_test_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
            
            # 1. 초기화: 확실한 비교를 위해 먼저 제한을 풉니다.
            api.set_bandwidth_limit(True, 102400) 
            time.sleep(3) # 설정 적용 대기

            # 2. 제한 켜기 전 IPS 측정 (Base Data)
            base_ips = iRAS_test.IRASController().get_current_ips()
            print(f"    - Base IPS: {base_ips}")

            # 3. 대역폭 제한 설정 (1024 bps)
            if api.set_bandwidth_limit(True, 1024):
                print("    - 대역폭 제한 설정(1024) 완료. 15초 대기 중...")
                time.sleep(20)  # 요청하신 15초 대기 (네트워크 버퍼 소진 및 안정화 시간)
                
                # 4. 제한 후 IPS 측정
                limit_ips = iRAS_test.IRASController().get_current_ips()
                print(f"    - Limit IPS: {limit_ips}")

                # 5. 결과 비교 (Base IPS 대비 떨어졌는지 확인)
                # 노이즈를 고려하여 Base 대비 80% 이하로 떨어지면 Pass로 간주 (비율은 필요 시 조정)
                if limit_ips < base_ips * 0.8:
                    print(f"🎉 [Pass] 제한 확인 ({base_ips} -> {limit_ips})")
                else:
                    print(f"❌ [Fail] IPS 감소 확인되지 않음 ({base_ips} -> {limit_ips})")
            
            else:
                print("❌ [Fail] 대역폭 제한 설정 실패")
            
            time.sleep(5)

            # 6. 종료 전 제한 해제 (성공/실패 여부와 관계없이 실행)
            api.set_bandwidth_limit(False)
            print("    - 대역폭 제한 해제 완료")
            time.sleep(5)

        # [Step 13] IP 필터링
        if current_test_ip:
            print("\n>>> [Step 13] IP 필터링 테스트")
            my_ip = get_local_ip()
            api = CameraApi(current_test_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
            
            if api.set_ip_filter("deny", deny_list=my_ip):
                time.sleep(5)
                try:
                    requests.get(f"http://{current_test_ip}:{ctx['PORT']}", timeout=3)
                    print("❌ [Fail] 접속됨")
                except: print("🎉 [Pass] 접속 차단됨")
                
                # 복구
                NetworkManager.set_static_ip("10.0.131.200", config.PC_SUBNET, config.PC_GW)
                if NetworkManager.ping(current_test_ip):
                    CameraApi(current_test_ip, ctx["PORT"], ctx["ID"], ctx["PW"]).set_ip_filter("off")
                NetworkManager.set_static_ip(config.PC_STATIC_IP, config.PC_SUBNET, config.PC_GW)

            time.sleep(5)

        # [Step 14] SSL
        if current_test_ip:
            print("\n>>> [Step 14] SSL 모드 검증")
            api = CameraApi(current_test_ip, ctx["PORT"], ctx["ID"], ctx["PW"])
            for mode, expected in [("standard", "ExcludeMultimedia"), ("high", "PartiallyMultimedia"), ("veryHigh", "FullPacket")]:
                if api.set_ssl(True, mode):
                    time.sleep(20)
                    status = iRAS_test.IRASController().get_current_ssl_info()
                    if status and expected.lower() in status.lower().replace(" ", ""):
                        print(f"🎉 [Pass] {mode}")
            api.set_ssl(False)

        return True, "Step 11-14 Completed"

    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', default=None)
    parser.add_argument('--id', default=None)
    parser.add_argument('--pw', default=None)
    parser.add_argument('--iface', default=None)
    parser.add_argument('--from-port', action='store_true', help='포트 변경 테스트(Step 11) 이후부터만 실행')
    args = parser.parse_args()
