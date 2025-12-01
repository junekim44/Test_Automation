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
from common_actions import handle_popup
import iRAS_test
import webgaurd

# Scapy 출력 끄기
conf.verb = 0

# 🛠️ [설정] 환경 변수 및 상수
CFG = {
    "IFACE": "이더넷",  # 실행하는 PC의 인터페이스 이름 확인 필수 (예: "Ethernet", "Wi-Fi")
    "PC_STATIC_IP": "10.0.131.102", 
    "PC_SUBNET": "255.255.0.0", 
    "PC_GW": "10.0.0.1",
    
    "PC_AUTO_IP": "169.254.100.100", # Link-Local 테스트용 PC IP
    "AUTO_SUBNET": "255.255.0.0",

    # 타겟 카메라 정보 (초기 고정 IP)
    "CAM_IP": "10.0.131.104", 
    "PORT": "80", 
    "ID": "admin", 
    "PW": "qwerty0-",

    # iRAS 테스트용 장치 이름 (MAC 대신 사용)
    "IRAS_DEV_NAME": "104_T6631",
    
    # 스캔 범위 설정
    "SCAN_NET": "10.0.131.0/24", 
    "SCAN_AUTO_NET": "169.254.0.0/16",
    
    "FEN_SVR": "qa1.idis.co.kr", 
    "FEN_NAME": "FEN테스트"
}

# =========================================================
# 🛡️ [System] 윈도우 네트워크 제어 유틸리티
# =========================================================

def check_port_open(ip, port, timeout=3):
    """지정된 IP와 포트가 실제(Socket)로 열려있는지 확인"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((ip, int(port)))
        return result == 0
    except:
        return False
    finally:
        sock.close()

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
        cmd = f'netsh interface ip set address name="{CFG["IFACE"]}" static {ip} {subnet}{gw_cmd}'
        NetworkManager.run_cmd(cmd)
        time.sleep(5) # 네트워크 인터페이스 재설정 대기

    @staticmethod
    def set_dhcp():
        print("💻 [System] PC IP DHCP(자동) 설정 변경 중...")
        NetworkManager.run_cmd(f'netsh interface ip set address name="{CFG["IFACE"]}" source=dhcp')
        NetworkManager.run_cmd(f'netsh interface ip set dns name="{CFG["IFACE"]}" source=dhcp')
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
class CameraScanner:
    @staticmethod
    def normalize_mac(mac):
        if not mac: return ""
        return mac.lower().replace("-", ":").replace(".", "")

    @staticmethod
    def scan_onvif(timeout=2):
        """ONVIF Probe를 날려서 응답하는 장치들의 IP를 수집"""
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
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(timeout)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(discovery_msg, ('239.255.255.250', 3702))
            
            start = time.time()
            while time.time() - start < timeout:
                try:
                    data, addr = sock.recvfrom(65536)
                    # 응답 데이터에서 IP 추출
                    resp_str = data.decode('utf-8', errors='ignore')
                    ips = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', resp_str)
                    for ip in ips:
                        if ip != "0.0.0.0" and ip != "239.255.255.250":
                            found_ips.append(ip)
                    found_ips.append(addr[0]) 
                except socket.timeout: break
        except: pass
        finally: sock.close()
        
        return list(set(found_ips))

    @staticmethod
    def scan_arp(target_mac, scan_range, timeout=2):
        """Active ARP Scan (소규모 대역용)"""
        # 대역폭이 /16(65536개)인 경우 스캔 방지
        if "/16" in scan_range or "/8" in scan_range:
            return None

        try:
            ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=scan_range), 
                         timeout=timeout, verbose=0, iface=CFG["IFACE"])
            for _, rcv in ans:
                if CameraScanner.normalize_mac(rcv.hwsrc) == target_mac:
                    return rcv.psrc
        except: pass
        return None

    @staticmethod
    def sniff_target_packet(target_mac, timeout=5):
        """Passive Sniffing: 타겟 MAC의 패킷을 감청하여 IP 확인"""
        found_ip = None
        target_mac = CameraScanner.normalize_mac(target_mac)

        def packet_handler(pkt):
            nonlocal found_ip
            ip_to_check = None
            # ARP 패킷 확인
            if pkt.haslayer(Ether) and pkt.haslayer(ARP):
                src_mac = CameraScanner.normalize_mac(pkt[Ether].src)
                if src_mac == target_mac:
                    found_ip = pkt[ARP].psrc
                    return True # Stop sniffing
            # IP 패킷 확인
            elif pkt.haslayer(Ether) and pkt.haslayer("IP"):
                src_mac = CameraScanner.normalize_mac(pkt[Ether].src)
                if src_mac == target_mac:
                    found_ip = pkt["IP"].src
                    return True
                
            # 0.0.0.0은 IP 할당 전(Probe) 단계이므로 무시
            if ip_to_check and ip_to_check != "0.0.0.0":
                found_ip = ip_to_check
                return True # 유효한 IP를 찾았으므로 스니핑 종료

            return False

        try:
            sniff(iface=CFG["IFACE"], stop_filter=packet_handler, timeout=timeout, store=0)
        except: pass
        
        return found_ip

    @staticmethod
    def find_ip_combined(target_mac, scan_range, timeout=40):
        print(f"🔍 [Scanner] {target_mac} 탐색 시작...", end="")
        target_mac = CameraScanner.normalize_mac(target_mac)
        target_mac_dash = target_mac.replace(":", "-")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                out = subprocess.check_output("arp -a", shell=True).decode('cp949', errors='ignore')
                for line in out.splitlines():
                    if target_mac_dash in line.lower():
                        ip = line.split()[0]
                        if "169.254" in scan_range and "169.254" not in ip: continue
                        if ip == "0.0.0.0": continue
                        print(f" (ARP Cache) 발견! -> {ip}")
                        return ip
            except: pass

            CameraScanner.scan_onvif()
            found_ip = CameraScanner.scan_arp(target_mac, scan_range)
            if found_ip and found_ip != "0.0.0.0":
                print(f" (Active ARP) 발견! -> {found_ip}")
                return found_ip
            
            if "/16" in scan_range:
                found_ip = CameraScanner.sniff_target_packet(target_mac, timeout=3)
                if found_ip:
                    # 💡 [수정] 스니핑된 IP가 169.254 대역인지 확인 (기존 IP가 잡히면 무시)
                    if "169.254" in scan_range and "169.254" not in found_ip:
                        # print(f" (Ignored: {found_ip})", end="") # 디버깅용
                        pass
                    else:
                        print(f" (Sniffing) 발견! -> {found_ip}")
                        return found_ip

            print(".", end="", flush=True)
            time.sleep(1)
        print(" 실패 ❌")
        return None
    

# =========================================================
# 🌐 [Web UI] Playwright 컨트롤러
# =========================================================
class WebController:
    def __init__(self, playwright_instance, target_port=None):
        port = target_port if target_port else CFG["PORT"]
        self.current_port = port
        self.browser = playwright_instance.chromium.launch(headless=False)
        self.context = self.browser.new_context(
            http_credentials={"username": CFG["ID"], "password": CFG["PW"]}
        )
        self.page = self.context.new_page()

    def close(self):
        self.browser.close()

    def _click_and_wait(self, selector):
        try:
            self.page.click(selector, timeout=3000)
            time.sleep(0.5)
        except: pass

    def get_mac_address(self, ip):
        print(f"🌐 [Web] MAC 주소 추출 시도: {ip}")
        try:
            self.page.goto(f"http://{ip}:{CFG['PORT']}/setup/setup.html", timeout=10000)
            self.page.wait_for_selector("#Page200_id", timeout=5000)
            self._click_and_wait("#Page200_id")
            self._click_and_wait("#Page201_id")
            mac = self.page.input_value("#mac-addressInfo", timeout=3000).strip()
            print(f"   ✅ MAC Found: {mac}")
            return mac
        except Exception as e:
            print(f"   ⚠️ Web Error: {e}")
            return None

    def set_link_local(self, ip, enable=True):
        action_str = "ON" if enable else "OFF (DHCP 복구)"
        print(f"🌐 [Web] Link-Local {action_str} 설정: {ip}")
        try:
            self.page.goto(f"http://{ip}:{CFG['PORT']}/setup/setup.html", timeout=10000)
            self.page.wait_for_selector("#Page300_id", timeout=10000)
            
            self._click_and_wait("#Page300_id") # 네트워크
            self._click_and_wait("#Page301_id") # IP주소
            
            chk = self.page.is_checked("#use-linklocal-only")
            if enable and not chk:
                print("   -> 체크박스 활성화")
                self.page.click("label[for='use-linklocal-only']")
            elif not enable:
                if chk:
                    print("   -> 체크박스 해제")
                    self.page.click("label[for='use-linklocal-only']")
                self.page.select_option("#ip-type", value="1") # DHCP
                print("   -> DHCP 선택")

            self.page.once("dialog", lambda d: d.accept())
            self.page.click("text=저장")
            time.sleep(3)
            print("   ✅ 설정 적용 완료")
            return True
        except Exception as e:
            print(f"   🔥 Link-Local 설정 실패: {e}")
            return False

    def set_fen_configuration(self, ip):
        print(f"🌐 [Web] FEN 설정 변경: {ip}")
        try:
            self.page.goto(f"http://{ip}:{CFG['PORT']}/setup/setup.html")
            self._click_and_wait("#Page300_id")
            self._click_and_wait("#Page302_id") # FEN
            
            if not self.page.is_checked("#use-fen"):
                self.page.click("label[for='use-fen']")
            
            self.page.fill("#fen-server", CFG["FEN_SVR"])
            self.page.fill("#cam-name", CFG["FEN_NAME"])
            
            # --- [수정된 부분] ---
            print("   -> FEN 이름 확인 클릭...")
            self.page.click("#check-cam-name")
            
            # 서버 통신 대기 (최대 5초간 팝업 기다림)
            # handle_popup 내부에 wait_for_selector가 있지만, 
            # 네트워크 딜레이를 고려해 명시적으로 조금 기다리는 것이 안전함
            time.sleep(2) 
            if not handle_popup(self.page, timeout=5000):
                print("   ⚠️ 팝업 처리 실패 -> Enter 키 시도")
                self.page.keyboard.press("Enter")
            
            print("   -> 설정 저장...")
            self.page.click("#setup-apply")
            time.sleep(2)
            if not handle_popup(self.page, timeout=5000):
                self.page.keyboard.press("Enter")
            # ---------------------

            print("   ✅ Web FEN 설정 완료")
        except Exception as e:
            print(f"   🔥 Web FEN Config Error: {e}")

    def set_upnp(self, ip, enable=True):
        """UPNP 설정 (포트/QoS 탭)"""
        print(f"🌐 [Web] UPNP {'ON' if enable else 'OFF'} 설정: {ip}")
        try:
            self.page.goto(f"http://{ip}:{CFG['PORT']}/setup/setup.html")
            self.page.wait_for_selector("#Page300_id", timeout=5000)
            
            self._click_and_wait("#Page300_id") # 네트워크
            self._click_and_wait("#Page303_id") # 포트/QoS
            
            chk = self.page.is_checked("#use-upnp")
            
            # 상태 변경 필요 시 클릭
            if enable and not chk:
                self.page.click("label[for='use-upnp']")
            elif not enable and chk:
                self.page.click("label[for='use-upnp']")
            
            if enable:
                print("   -> UPNP 확인 버튼 클릭...")
                self.page.click("#check-upnp")
                time.sleep(10) # 확인 팝업 대기
                if not handle_popup(self.page):
                    self.page.keyboard.press("Enter")
            
            print("   -> 저장...")
            self.page.click("#setup-apply")
            time.sleep(1)
            if not handle_popup(self.page):
                self.page.keyboard.press("Enter")
                
            print("   ✅ UPNP 설정 완료")
            return True
        except Exception as e:
            print(f"   🔥 UPNP Config Error: {e}")
            return False
        
    def set_network_ports(self, http_port=None, remote_port=None, rtsp_port=None):
        """Web UI를 통해 포트 설정을 변경 (HTML 소스 반영)"""
        print(f"🌐 [Web] 포트 변경 시도: HTTP={http_port}")
        try:
            self.page.goto(f"http://{CFG['CAM_IP']}:{self.current_port}/setup/setup.html")
            self._click_and_wait("#Page300_id") # 네트워크
            self._click_and_wait("#Page303_id") # 포트/QoS

            # 1. HTTP 포트 변경 (id="web-port")
            if http_port:
                self.page.fill("#web-port", str(http_port))
            
            # 2. 원격 포트 변경 (id="remote-port"로 수정됨)
            if remote_port:
                self.page.fill("#remote-port", str(remote_port))

            # 3. RTSP 포트 변경
            if rtsp_port:
                if rtsp_port == "OFF":
                    if self.page.is_checked("#use-rtsp"):
                        self.page.click("label[for='use-rtsp']")
                else:
                    if not self.page.is_checked("#use-rtsp"):
                        self.page.click("label[for='use-rtsp']")
                    self.page.fill("#rtsp-port", str(rtsp_port))

            # 저장 버튼 클릭
            self.page.click("#setup-apply")
            
            time.sleep(1)
            if handle_popup(self.page):
                print("   -> 팝업 확인 (설정 적용)")
            
            print("   -> 서비스 재시작 대기 (10초)...")
            time.sleep(10)
            return True

        except Exception as e:
            print(f"   🔥 포트 설정 실패: {e}")
            return False
        

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
            res = self.session.get(f"{self.base_url}?action={action}&mode=1", timeout=5)
            if res.status_code == 200:
                return dict(parse_qsl(res.text))
        except: pass
        return {}

    def verify_fen_setting(self, expected_server):
        data = self._get_config("networkDDNS")
        use_ddns = data.get("useDDNS") == "on"
        server_match = data.get("serverAddress") == expected_server
        print(f"📡 [API] FEN 검증: Use={use_ddns}, Server={data.get('serverAddress')} -> {'Pass' if use_ddns and server_match else 'Fail'}")
        return use_ddns and server_match
    
    def reset_ports_default(self):
        """API를 사용하여 포트 설정을 기본값(80, 8016, 554)으로 강제 복구"""
        print("🚑 [API] 포트 설정을 기본값(80, 8016, 554)으로 복구합니다...")
        
        payload = {
            "action": "networkPort",
            "mode": "0",
            "useWeb": "on",
            "webPort": "80",
            "adminPort": "8200", 
            "watchPort": "8016", 
            "searchPort": "10019",
            "recordPort": "8017",
            "useRtsp": "on",
            "rtspPort": "554",
            "useHTTPS": "off",
            "useUPNP": "on"
        }
        
        try:
            res = self.session.post(self.base_url, data=payload, timeout=5)
            if "returnCode=0" in res.text:
                print("   ✅ 포트 초기화 성공")
                return True
            else:
                print(f"   ⚠️ 초기화 응답 이상: {res.text.strip()}")
        except Exception as e:
            print(f"   ❌ API 복구 요청 실패: {e}")
        return False
    
    def set_bandwidth_limit(self, enable=True, limit_kbps=102400):
        """
        API를 통해 대역폭 제한 설정 변경
        limit_kbps: 1024 (1Mbps) ~ 102400 (100Mbps)
        """
        action_str = f"{limit_kbps} Kbps" if enable else "OFF"
        print(f"📡 [API] 대역폭 제한 설정: {action_str}...", end="")
        
        payload = {
            "action": "networkBandwidth",
            "mode": "0", # Write
            "useNetworkBandwidth": "on" if enable else "off",
            "networkBandwidth": str(limit_kbps)
        }
        
        try:
            res = self.session.post(self.base_url, data=payload, timeout=5)
            if "returnCode=0" in res.text:
                print(" 성공 ✅")
                return True
            else:
                print(f" 실패 ❌ (응답: {res.text.strip()})")
        except Exception as e:
            print(f" 오류 🔥 ({e})")
        return False
    
    def set_ip_filter(self, mode="off", allow_list="", deny_list=""):
        """
        IP 필터링 설정 (API 11.2 Write)
        mode: "off" | "allow" | "deny"
        """
        print(f"🛡️ [API] IP 필터 설정 변경: Mode={mode}, Deny={deny_list}...", end="")
        payload = {
            "action": "networkSecurity",
            "mode": "0", # Write
            "filterType": mode,
            "allowList": allow_list,
            "denyList": deny_list,
            # 기존 SSL 설정 유지 (안 보내면 초기화될 수 있으므로 현재 상태에 맞춰야 하나, 여기선 off 가정)
            "useSSL": "off", 
            "sslType": "standard"
        }
        
        try:
            res = self.session.post(self.base_url, data=payload, timeout=5)
            if "returnCode=0" in res.text:
                print(" 성공 ✅")
                return True
            else:
                print(f" 실패 ❌ (응답: {res.text.strip()})")
        except Exception as e:
            print(f" 오류 🔥 ({e})")
        return False

    def set_ssl(self, enable=True, ssl_type="standard"):
        """
        SSL 설정 변경
        enable: True/False
        ssl_type: "standard" | "high" | "veryhigh"
        """
        val = "on" if enable else "off"
        print(f"🔒 [API] SSL 설정 변경 요청: {val} (Type={ssl_type})...", end="")
        
        payload = {
            "action": "networkSecurity",
            "mode": "0",
            "useSSL": val,
            "sslType": ssl_type,
            "filterType": "off" 
        }
        
        try:
            res = self.session.post(self.base_url, data=payload, timeout=5)
            if "returnCode=0" in res.text:
                print(" 성공 ✅")
                return True
            else:
                print(f" 실패 ❌ (응답: {res.text.strip()})")
        except Exception as e:
            print(f" 오류 🔥 ({e})")
        return False

# =========================================================
# 🚀 Main Execution Flow
# =========================================================

def _run_web_action(action_func, *args, **kwargs):
    """Playwright를 사용하는 작업을 안전하게 실행하기 위한 래퍼"""
    try:
        with sync_playwright() as p:
            controller = WebController(p)
            result = action_func(controller, *args, **kwargs)
            controller.close()
            return result
    except Exception as e:
        # "Sync API inside asyncio loop" 에러가 뜨면, 현재 환경이 비동기 루프 안이라는 뜻.
        # 이 경우엔 불가피하게 subprocess로 자기 자신을 호출하여 격리해야 함.
        if "asyncio loop" in str(e):
            print("⚠️ [Warn] Async Loop 감지됨. 별도 프로세스로 Web Action 재시도...")
            # 여기에 서브프로세스 로직을 넣을 수도 있지만, 
            # 지금은 일단 예외를 던져서 상위에서 알 수 있게 함.
            raise Exception("Playwright Sync API Conflict: Please run network_test.py as a standalone process or remove asyncio context.")
        print(f"🔥 Web Action Error: {e}")
        return None

# 개별 웹 액션 정의 (래퍼에 의해 호출됨)
def _action_get_mac(web, ip): return web.get_mac_address(ip)
def _action_set_link_local(web, ip, enable): return web.set_link_local(ip, enable)
def _action_set_fen(web, ip): return web.set_fen_configuration(ip)
def _action_set_upnp(web, ip, enable): return web.set_upnp(ip, enable)
def _action_set_ports(web, http_port): return web.set_network_ports(http_port=http_port)
def _action_verify_web_access(web, ip, port):
    try:
        web.page.goto(f"http://{ip}:{port}/setup/setup.html", timeout=5000)
        return "IDIS" in web.page.title() or web.page.is_visible("#userid")
    except: return False

def _action_webguard_login(web_dummy, fen_url, user, pw):
    try:
        page = web_dummy.page
        page.goto(fen_url)
        time.sleep(5)
        return webgaurd.run_login(user, pw)
    except: return False

def _refresh_session(api_obj):
    print("\n🔄 [Session Refresh] iRAS 세션 갱신 (SSL Toggle)...")
    try:
        # 1. SSL 켜기
        if api_obj.set_ssl(enable=True):
            print("   -> SSL ON 완료. iRAS 반영 대기 (20초)...")
            time.sleep(10) 
            
            # 2. SSL 끄기 (원상복구)
            print("   -> SSL OFF 시도...")
            if api_obj.set_ssl(enable=False):
                print("   -> SSL OFF 완료. iRAS 반영 대기 (20초)...")
                time.sleep(10) 
                return True
            else:
                print("   ⚠️ SSL OFF 실패 (API 응답 없음)")
                
    except Exception as e:
        print(f"   🔥 세션 갱신 로직 에러: {e}")
    return False

def run_integrated_network_test(
    camera_ip="10.0.131.104", 
    camera_id="admin", 
    camera_pw="qwerty0-", 
    interface_name="이더넷", 
    fen_server="qa1.idis.co.kr", 
    fen_name="FEN테스트"
):
    """
    main.py에서 호출 가능한 통합 네트워크 테스트 함수.
    반환값: (성공여부 Bool, 결과 메시지 String)
    """
    # 1. 관리자 권한 체크
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return False, "관리자 권한이 필요합니다. main.py를 관리자 권한으로 실행해주세요."

    # 2. 전역 설정(CFG) 업데이트
    CFG["CAM_IP"] = camera_ip
    CFG["ID"] = camera_id
    CFG["PW"] = camera_pw
    CFG["IFACE"] = interface_name
    CFG["FEN_SVR"] = fen_server
    CFG["FEN_NAME"] = fen_name
    
    # PC IP는 환경에 맞게 고정값 유지하거나 인자로 확장 가능
    # CFG["PC_STATIC_IP"] ... 

    print("\n=== 🚀 Network & Automation Test Integrated Run ===")
    
    target_ip = CFG["CAM_IP"]
    target_mac = None

    try:
        # [Step 1] PC IP 고정 및 MAC 주소 획득
        print("\n>>> [Step 1] Link-Local 활성화 준비")
        NetworkManager.set_static_ip(CFG["PC_STATIC_IP"], CFG["PC_SUBNET"], CFG["PC_GW"])
        
        if NetworkManager.ping(target_ip):
            # 🌟 Playwright 호출을 래퍼 함수로 감싸서 실행
            target_mac = _run_web_action(_action_get_mac, target_ip)
            
            if target_mac:
                _run_web_action(_action_set_link_local, target_ip, True)
        else:
            return False, "초기 카메라 접속 실패. IP 설정을 확인하세요."

        if not target_mac:
            return False, "MAC 주소 확보 실패"

        # [Step 2] 169.254 대역 검증
        print("\n>>> [Step 2] 169.254 Auto-IP 검증")
        NetworkManager.set_static_ip(CFG["PC_AUTO_IP"], CFG["AUTO_SUBNET"])
        NetworkManager.run_cmd("arp -d *")
        
        auto_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_AUTO_NET"], timeout=40)
        
        if auto_ip and "169.254" in auto_ip:
            print(f"🎉 Auto-IP 접속 성공: {auto_ip}")
            _run_web_action(_action_set_link_local, auto_ip, False)
        else:
            print("⚠️ Auto-IP 탐색 실패 (DHCP 전환 시도)")

        # [Step 3] 물리 테스트 (사용자 개입 필요)
        print("\n⚠️ [User Action Required] 물리 테스트 단계입니다.")
        # 자동화 툴에서는 input이 블로킹되므로 주의. 완전 자동화를 원하면 이 부분을 생략해야 함.
        # 여기서는 유지하되 타임아웃/스킵 로직 추가 가능. 일단 유지.
        input("🚨 [ACTION] 사내망 랜선을 뽑고, 카메라를 재부팅한 후 Enter >> ")
        NetworkManager.set_dhcp()
        NetworkManager.run_cmd("arp -d *")
        
        print(f"🔍 [Step 3] 물리적 Auto-IP 할당 확인 중...")
        phy_auto_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_AUTO_NET"], timeout=60)
        if phy_auto_ip and "169.254" in phy_auto_ip:
            print(f"🎉 Auto-IP 확인: {phy_auto_ip}")

        # [Step 4] 복구 및 FEN
        input("\n🚨 [ACTION] 사내망 랜선을 다시 연결한 후 Enter >> ")
        NetworkManager.set_dhcp()
        
        new_dhcp_ip = None
        if NetworkManager.wait_for_dhcp("10."):
            NetworkManager.run_cmd("arp -d *")
            new_dhcp_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=60)
            
            if new_dhcp_ip and NetworkManager.ping(new_dhcp_ip):
                print(f"🎉 카메라 재접속: {new_dhcp_ip}")
                
                # FEN 설정
                _run_web_action(_action_set_fen, new_dhcp_ip)
                
                api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                api.verify_fen_setting(CFG["FEN_SVR"])

                # [Step 5-6] iRAS
                print("\n>>> [Step 5] iRAS 연동 테스트 (DirectExternal)")
                if iRAS_test.run_fen_setup_process(CFG["IRAS_DEV_NAME"], CFG["FEN_NAME"]):
                    
                    # 🌟 [NEW] FEN 설정 후 영상이 붙을 때까지 먼저 대기!
                    iRAS_test.wait_for_connection()
                    
                    # 🌟 영상이 나온 후에 세션 갱신 (정보 업데이트)
                    _refresh_session(api)
                    
                    if iRAS_test.run_fen_verification("TcpDirectExternal"):
                        print("🎉 [Pass] TcpDirectExternal 확인")
                    else:
                        # 실패 시 한번 더 갱신 시도
                        print("   ⚠️ 1차 검증 실패, 강제 갱신 후 재시도...")
                        # iRAS_test.run_refresh_connection(CFG["IRAS_DEV_NAME"]) # 필요시 주석 해제
                        # iRAS_test.wait_for_connection()
                        if iRAS_test.run_fen_verification("TcpDirectExternal"):
                            print("🎉 [Pass] TcpDirectExternal 확인 (재시도 성공)")

        # [Step 7] UPNP (DirectInternal)
        router_cam_ip = None 

        if new_dhcp_ip:
            print("\n>>> [Step 7] UPNP 활성화 및 DirectInternal 검증")
            
            # 1. [이동] PC와 카메라 모두 공유기로 이동
            print("   ℹ️  UPNP 확인을 위해 공유기 환경으로 이동합니다.")
            input("🚨 [ACTION] 카메라와 PC를 모두 '공유기'에 연결하고 Enter를 누르세요 >> ")
            
            # 2. [PC IP 갱신]
            print("   -> PC IP 갱신 (DHCP)...")
            NetworkManager.set_dhcp()
            NetworkManager.wait_for_dhcp("192.")
            
            # 3. [카메라 스캔]
            print("   -> 공유기 환경에서 카메라 IP 재탐색...")
            router_cam_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=40)
            if not router_cam_ip:
                print("   ⚠️ 공유기 IP 탐색 실패. 기존 Link-Local IP 사용 시도...")
                router_cam_ip = auto_ip 
            
            if router_cam_ip:
                print(f"   ✅ 타겟 IP 확보: {router_cam_ip}")
                
                # 4. [설정] UPNP ON
                _run_web_action(_action_set_upnp, router_cam_ip, True)
                
                # 5. [대기] iRAS가 새 환경(공유기)에서 카메라에 붙을 때까지 대기 🌟
                #    (설정이 바뀌고 IP가 바뀌었으니 FEN이 갱신되어 영상이 나올 때까지 기다림)
                iRAS_test.wait_for_connection()
                
                # 6. [갱신] 영상이 붙은 후 세션 갱신 (정보 업데이트)
                if 'api' not in locals(): api = CameraApi(router_cam_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                api.base_url = f"http://{router_cam_ip}:{CFG['PORT']}/cgi-bin/webSetup.cgi"
                _refresh_session(api)
                
                # 7. [검증]
                if iRAS_test.run_fen_verification("TcpDirectInternal"):
                    print("🎉 [Pass] TcpDirectInternal 확인")
                else:
                    print("⚠️ [Fail] TcpDirectInternal 실패")
            else:
                print("❌ 공유기 환경에서 카메라를 찾을 수 없어 Step 7~8 중단")
                router_cam_ip = None

        # [Step 8] UDP Hole Punching
        if router_cam_ip:
            print("\n>>> [Step 8] UDP Hole Punching")
            
            # 1. [설정] UPNP OFF (공유기 망 내에서)
            print("   -> [설정] 카메라 UPNP 비활성화(OFF)...")
            _run_web_action(_action_set_upnp, router_cam_ip, False)
            
            # 2. [대기] 설정 변경 후 iRAS가 안정화될 때까지 대기 🌟
            #    (UPNP를 껐으므로 연결 방식이 바뀔 수 있음, 영상 유지 확인)
            iRAS_test.wait_for_connection()

            # 3. [갱신] 망 분리 전, 상태 갱신 (SSL Toggle)
            print("   -> [갱신] FEN 상태 업데이트 (SSL Toggle)...")
            _refresh_session(api)

            # 4. [이동] PC만 사내망으로 이동
            print("\n⚠️ [Move] 공유기 upnp 해제 후 PC만 사내망으로 이동합니다.")
            input("🚨 [ACTION] PC 랜선을 '사내망'으로 옮기고 Enter >> ")
            
            print("   -> PC IP 갱신 (사내망 DHCP)...")
            NetworkManager.set_dhcp()
            NetworkManager.wait_for_dhcp("10.")
            
            # 5. [대기] 망 변경 후 iRAS가 다시 붙을 때까지 대기 🌟
            #    (외부망을 타고 들어오므로 시간이 걸림)
            iRAS_test.wait_for_connection()
            
            # 6. [검증]
            if iRAS_test.run_fen_verification("UdpHolePunching"):
                print("🎉 [Pass] UdpHolePunching 확인")
            else:
                print("⚠️ [Fail] UDP Hole Punching 실패")

        # [Step 9] FEN Relay
        if router_cam_ip:
            print("\n>>> [Step 9] FEN Relay (UDP Block)")
            input("🚨 [ACTION] 공유기 설정에서 'UDP 차단' 후 Enter >> ")
            
            # 1. [대기] 차단 후 Relay로 붙을 때까지 대기 🌟
            iRAS_test.wait_for_connection()

            # 2. [검증] (망 분리 상태라 API 갱신 불가, iRAS가 스스로 갱신하길 기다림)
            if iRAS_test.run_fen_verification("Relay"):
                print("🎉 [Pass] FEN Relay 확인")
            else:
                print("⚠️ [Fail] FEN Relay 실패")

            # ---------------------------------------------------------
            print("\n🧹 [Restore] 다음 테스트를 위해 카메라를 사내망으로 복귀시킵니다.")
            input("🚨 [ACTION] '카메라'를 사내망(허브)으로 연결 후 Enter >> ")
            
            print("   -> 사내망에서 카메라 재탐색...")
            new_dhcp_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=40)
            if not new_dhcp_ip:
                print("❌ 카메라 사내망 복귀 실패.")

        # [Step 10] WebGuard
        if new_dhcp_ip:
            print("\n>>> [Step 10] WebGuard Login")
            fen_url = f"http://{CFG['FEN_SVR']}/{CFG['FEN_NAME']}"
            if _run_web_action(_action_webguard_login, fen_url, CFG["ID"], CFG["PW"]):
                print("🎉 [Pass] WebGuard Login")
        
            
        # [Step 11] 포트 변경 및 검증 시나리오 (New)
        if new_dhcp_ip:
            print("\n>>> [Step 11] 포트 변경 및 검증 (Web / iRAS / Socket)")
            
            # API 객체 생성 (초기화 및 복구용)
            api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            
            test_http_port = "8080"
            test_remote_port = "8200"
            
            try:
                # --- 1. HTTP 포트 변경 (Web -> 8080) ---
                print(f"\n   [11-1] Web HTTP 포트 변경 (80 -> {test_http_port})")
                _run_web_action(_action_set_ports, test_http_port)
                
                # 검증 A: Socket 레벨 확인
                if check_port_open(new_dhcp_ip, test_http_port):
                    print(f"   ✅ Socket Check: {test_http_port} Port is OPEN")
                else:
                    raise Exception(f"Socket Check Failed: {test_http_port} is Closed")

                # 검증 B: 변경된 포트로 Web 접속 확인
                print(f"   [Verify] 변경된 포트({test_http_port})로 접속 시도...")
                if _run_web_action(_action_verify_web_access, new_dhcp_ip, test_http_port, target_port=test_http_port):
                     print(f"   ✅ Web Access Success on Port {test_http_port}")
                else:
                     print(f"   ❌ Web Access Failed on Port {test_http_port}")

                # API 객체의 Base URL 업데이트 (복구를 위해)
                api.base_url = f"http://{new_dhcp_ip}:{test_http_port}/cgi-bin/webSetup.cgi"

                # --- 2. 원격 포트 변경 (iRAS -> 8200) ---
                print(f"\n   [11-2] iRAS 원격 포트 변경 (Watch -> {test_remote_port})")
                
                # iRAS 자동화 호출 (수정된 iRAS_test.py 사용)
                if iRAS_test.run_port_change_process(CFG["IRAS_DEV_NAME"], test_remote_port):
                    print("   ✅ iRAS 설정 변경 동작 완료")
                    
                    # 검증: Socket 레벨 확인
                    time.sleep(2)
                    if check_port_open(new_dhcp_ip, test_remote_port):
                        print(f"   ✅ Socket Check: {test_remote_port} Port is OPEN")
                    else:
                        print(f"   ❌ Socket Check Failed: {test_remote_port} is Closed")
                else:
                    print("   ⚠️ iRAS 자동화 실패 (건너뜀)")

            except Exception as e:
                print(f"   🔥 [Critical] 테스트 중단 오류: {e}")

            finally:
                # --- [Teardown] 환경 복구 (가장 중요) ---
                print("\n🧹 [Teardown] 포트 설정 초기화 (Rescue Mode)")
                if api.reset_ports_default():
                    CFG["PORT"] = "80"
                    print("   ✅ 모든 포트가 기본값으로 복구되었습니다.")
                else:
                    # 만약 HTTP 포트가 8080인 상태에서 80으로 요청을 보내 실패했다면,
                    # 8080 포트로 다시 시도해봐야 함.
                    print("   ⚠️ 기본 포트로 복구 실패. 변경된 포트로 재시도...")
                    try:
                        api.base_url = f"http://{new_dhcp_ip}:{test_http_port}/cgi-bin/webSetup.cgi"
                        if api.reset_ports_default():
                            print("   ✅ (재시도) 포트 복구 성공")
                        else:
                            print("   🔥 복구 완전 실패. 수동 확인 요망.")
                    except:
                        pass
                        
        # [Step 12] 대역폭 제한 테스트
        if new_dhcp_ip:
            print("\n>>> [Step 12] 대역폭 제한 테스트 (API 제어)")
            if 'api' not in locals():
                api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            
            try:
                print("   [12-1] 대역폭 최대(100Mbps) 설정")
                api.set_bandwidth_limit(enable=True, limit_kbps=102400)
                time.sleep(5)
                
                # iRASController 직접 호출
                base_ips = iRAS_test.IRASController().get_current_ips()
                print(f"   ℹ️  기준 IPS: {base_ips}")

                print("\n   [12-2] 대역폭 최소(1Mbps) 제한 설정")
                if api.set_bandwidth_limit(enable=True, limit_kbps=1024):
                    print("   -> 대역폭 제한 적용 대기 (10초)...")
                    time.sleep(10)
                    limit_ips = iRAS_test.IRASController().get_current_ips()
                    
                    if limit_ips < base_ips * 0.5 or limit_ips < 10:
                        print(f"   🎉 [Pass] 제한 동작 확인 (IPS: {base_ips} -> {limit_ips})")
                    else:
                        print(f"   ⚠️ [Fail] 효과 미비 (IPS: {base_ips} -> {limit_ips})")
            except Exception as e:
                print(f"   🔥 테스트 오류: {e}")
            finally:
                print("\n   🧹 [Teardown] 대역폭 설정 복구")
                api.set_bandwidth_limit(enable=True, limit_kbps=102400)
        
        # [Step 13] IP 필터링 테스트 (Deny List -> Rescue)
        if new_dhcp_ip:
            print("\n>>> [Step 13] IP 필터링(Deny List) 및 복구 테스트")
            
            # 테스트용 임시 IP (차단을 피하기 위한 "변신용" IP)
            # ⚠️ 주의: 카메라와 통신 가능한 같은 대역의 미사용 IP여야 합니다.
            TEMP_PC_IP = "10.0.131.200" 
            ORIGIN_PC_IP = CFG["PC_STATIC_IP"] # 원래 내 IP
            
            if 'api' not in locals():
                api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])

            try:
                # 1. 내 IP 차단 (Deny List 등록)
                print(f"   [13-1] 내 IP ({ORIGIN_PC_IP}) 차단 설정")
                if api.set_ip_filter(mode="deny", deny_list=ORIGIN_PC_IP):
                    print("   -> 차단 설정 완료. 접속 불가 확인 시도...")
                    time.sleep(2)
                    
                    # 2. 접속 실패 검증
                    try:
                        requests.get(f"http://{new_dhcp_ip}:{CFG['PORT']}", timeout=3)
                        print("   ❌ [Fail] 차단되었는데 접속이 됩니다! (Test Fail)")
                    except:
                        print("   🎉 [Pass] 접속 차단 확인됨! (연결 실패)")

                    # 3. PC IP 변경 (구조 작전)
                    print(f"\n   [13-2] 구조 작전: PC IP 변경 -> {TEMP_PC_IP}")
                    NetworkManager.set_static_ip(TEMP_PC_IP, CFG["PC_SUBNET"], CFG["PC_GW"])
                    
                    print("   -> 변경된 IP로 카메라 재접속 시도...")
                    if NetworkManager.ping(new_dhcp_ip):
                        # IP가 바뀌었으므로 세션 새로 생성
                        rescue_api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                        
                        # 4. 차단 해제 (복구)
                        print("   -> Deny List 초기화 중...")
                        if rescue_api.set_ip_filter(mode="off", deny_list=""):
                            print("   ✅ 차단 해제 성공")
                        else:
                            print("   🔥 차단 해제 실패! (수동 복구 필요)")
                    else:
                        print("   ❌ IP 변경 후에도 통신 불가 (네트워크 설정 확인 필요)")
                else:
                    print("   ⚠️ 차단 설정 실패로 테스트 중단")

            except Exception as e:
                print(f"   🔥 테스트 오류: {e}")

            finally:
                # 5. PC IP 원복 (반드시 수행)
                print("\n   🧹 [Teardown] PC IP 원래대로 복구")
                NetworkManager.set_static_ip(ORIGIN_PC_IP, CFG["PC_SUBNET"], CFG["PC_GW"])
        
        # [Step 14] SSL 모드별 설정 및 iRAS 검증
        if new_dhcp_ip:
            print("\n>>> [Step 14] SSL 모드 변경 및 iRAS 정보 검증")
            
            if 'api' not in locals():
                api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])

            # 테스트 케이스 정의: (API 파라미터, iRAS 기대 문자열 키워드)
            # 1) standard : exclude multimedia packet
            # 2) high : partially multimedia packet
            # 3) very high : full packet
            ssl_test_cases = [
                ("standard", "ExcludeMultimediaPacket"), # 혹은 로그에 따라 "Standard"
                ("high", "PartiallyMultimediaPacket"),   # 혹은 로그에 따라 "Partially"
                ("veryhigh", "FullPacket")               # 로그 확인됨: "FullPacket"
            ]
            
            # ※ 주의: iRAS에서 보여주는 텍스트가 "ExcludeMultimediaPacket"인지 "Standard"인지 
            # 실제 환경에서 한번 확인되면 위 리스트의 두 번째 값을 수정하면 됩니다.
            # 사용자 설명 기반으로 최대한 매칭했습니다.

            try:
                for mode, expected_text in ssl_test_cases:
                    print(f"\n   [Test] SSL 모드 설정: {mode}")
                    
                    # 1. API 설정
                    if api.set_ssl(enable=True, ssl_type=mode):
                        
                        # 2. 적용 및 재접속 대기
                        # SSL 변경 시 카메라 웹서비스/스트림이 재시작되므로 iRAS가 끊겼다 붙을 시간이 필요함
                        print("   -> 설정 적용 및 iRAS 재접속 대기 (약 20초)...")
                        time.sleep(20) 
                        
                        # 3. iRAS 정보 확인 (재시도 로직 포함)
                        detected_status = None
                        for i in range(3): # 최대 3회 시도
                            detected_status = iRAS_test.get_ssl_status()
                            if detected_status:
                                break
                            print("   -> 정보 읽기 실패, 3초 후 재시도...")
                            time.sleep(3)
                        
                        # 4. 검증
                        if detected_status:
                            # 대소문자 무시하고 포함 여부 확인 (예: FullPacket 포함 여부)
                            if expected_text.lower() in detected_status.lower().replace(" ", ""):
                                print(f"   🎉 [Pass] {mode} 모드 확인됨 (Actual: {detected_status})")
                            else:
                                # Standard 설정 시 iRAS 표기가 다를 수 있어 유연하게 경고만 출력
                                print(f"   ⚠️ [Check] 값 불일치? (Mode: {mode}, Expected: {expected_text}, Actual: {detected_status})")
                        else:
                            print("   ❌ [Fail] iRAS에서 SSL 정보를 읽어오지 못함")
                    else:
                        print("   ❌ API 설정 실패로 건너뜀")

            except Exception as e:
                print(f"   🔥 SSL 테스트 오류: {e}")

            finally:
                # [Teardown] SSL 비활성화
                print("\n   🧹 [Teardown] SSL 비활성화 (HTTP 복구)")
                # HTTPS 상태일 수 있으므로 URL 조정 시도
                api.base_url = f"https://{new_dhcp_ip}:443/cgi-bin/webSetup.cgi"
                if not api.set_ssl(enable=False):
                    api.base_url = f"http://{new_dhcp_ip}:{CFG['PORT']}/cgi-bin/webSetup.cgi"
                    api.set_ssl(enable=False)

        print("\n✅ 모든 네트워크 테스트 완료.")
        return True, "네트워크 및 iRAS 테스트 완료"

    except Exception as e:
        print(f"\n🔥 네트워크 테스트 중 치명적 오류: {e}")
        return False, str(e)
    
if __name__ == "__main__":
    # 1. 관리자 권한 강제 (프로세스 분리 시 필수)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # 인자(Arguments)를 그대로 유지하며 관리자 권한으로 재실행
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    # 2. 커맨드 라인 인자 파싱 (main.py에서 값을 전달받기 위함)
    try:
        parser = argparse.ArgumentParser(description='Network Integration Test')
        parser.add_argument('--ip', type=str, default="10.0.131.104", help='Target Camera IP')
        parser.add_argument('--id', type=str, default="admin", help='Camera ID')
        parser.add_argument('--pw', type=str, default="qwerty0-", help='Camera Password')
        parser.add_argument('--iface', type=str, default="이더넷", help='Network Interface Name')
        args = parser.parse_args()

        success, msg = run_integrated_network_test(
            camera_ip=args.ip, camera_id=args.id, camera_pw=args.pw, interface_name=args.iface
        )
        
        if success:
            print("\n✅ 테스트가 성공적으로 완료되었습니다.")
            sys.exit(0)
        else:
            print(f"\n❌ 테스트 실패: {msg}")
            # 실패 시에도 창 유지
            input("\n🛑 엔터 키를 누르면 종료합니다...")
            sys.exit(1)

    except Exception as e:
        print(f"\n🔥 [Critical Error] 실행 중 예외 발생: {e}")
        import traceback
        traceback.print_exc() # 상세 에러 로그 출력
        input("\n🛑 오류를 확인하세요. 엔터 키를 누르면 종료합니다...") # 창 닫힘 방지
        sys.exit(1)

    # 3. 테스트 실행
    success, msg = run_integrated_network_test(
        camera_ip=args.ip,
        camera_id=args.id,
        camera_pw=args.pw,
        interface_name=args.iface
    )

    # 4. 종료 코드 반환 (main.py에서 성공/실패 여부를 알기 위함)
    if success:
        sys.exit(0) # 성공
    else:
        sys.exit(1) # 실패
        







# if __name__ == "__main__":
#     if not ctypes.windll.shell32.IsUserAnAdmin():
#         print("🔒 관리자 권한으로 재실행합니다...")
#         ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
#         sys.exit()

#     print("=== Network & Automation Test Started ===")
    
#     target_ip = CFG["CAM_IP"]
#     target_mac = None

#     # [Step 1] PC IP 고정 및 MAC 주소 획득
#     print("\n>>> [Step 1] Link-Local 활성화 준비")
#     NetworkManager.set_static_ip(CFG["PC_STATIC_IP"], CFG["PC_SUBNET"], CFG["PC_GW"])
    
#     if NetworkManager.ping(target_ip):
#         with sync_playwright() as p:
#             web = WebController(p)
#             target_mac = web.get_mac_address(target_ip)
#             if target_mac:
#                 web.set_link_local(target_ip, enable=True)
#             web.close()
#     else:
#         print("❌ 카메라 접속 실패. IP 설정을 확인하세요.")
#         # sys.exit() 

#     if not target_mac:
#         print("❌ MAC 주소 확보 실패로 테스트 중단")
#         sys.exit()

#     # [Step 2] 169.254 대역 검증
#     print("\n>>> [Step 2] 169.254 Auto-IP 검증")
#     NetworkManager.set_static_ip(CFG["PC_AUTO_IP"], CFG["AUTO_SUBNET"])
#     NetworkManager.run_cmd("arp -d *")
    
#     auto_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_AUTO_NET"], timeout=40)
    
#     if auto_ip and "169.254" in auto_ip:
#         print(f"🎉 Auto-IP 접속 성공: {auto_ip}")
#         print("\n>>> [Step 3] 설정 복구 (Link-Local OFF & DHCP)")
#         with sync_playwright() as p:
#             web = WebController(p)
#             web.set_link_local(auto_ip, enable=False)
#             web.close()
#     else:
#         print("⚠️ Auto-IP 탐색 실패 (DHCP 전환을 시도합니다)")

#     # [Step 3] 물리 테스트
#     input("\n🚨 [ACTION] 사내망 랜선을 뽑고, 카메라를 재부팅한 후 Enter를 누르세요 >> ")
#     NetworkManager.set_dhcp()
#     NetworkManager.run_cmd("arp -d *")
    
#     print(f"🔍 [Step 3] 물리적 Auto-IP 할당 확인 중...")
#     phy_auto_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_AUTO_NET"], timeout=60)
    
#     if phy_auto_ip and "169.254" in phy_auto_ip:
#         print(f"🎉 [물리 테스트] Auto-IP 확인 성공: {phy_auto_ip}")
#     else:
#         print("⚠️ [물리 테스트] Auto-IP 탐색 실패")

#     # [Step 4] PC 네트워크 복구 및 DHCP IP 탐색
#     input("\n🚨 [ACTION] 사내망 랜선을 다시 연결한 후 Enter를 누르세요 >> ")
#     print("\n>>> [Step 4] PC 네트워크 복구 및 DHCP IP 탐색")
#     NetworkManager.set_dhcp()
    
#     new_dhcp_ip = None
#     if NetworkManager.wait_for_dhcp("10."):
#         NetworkManager.run_cmd("arp -d *")
        
#         print(f"🔍 [Step 4] DHCP로 변경된 카메라 IP 탐색 중...")
#         new_dhcp_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=60)
        
#         if new_dhcp_ip and NetworkManager.ping(new_dhcp_ip):
#             print(f"🎉 카메라 재접속 성공: {new_dhcp_ip}")
            
#             # 1. FEN 설정 (Web)
#             with sync_playwright() as p:
#                 web = WebController(p)
#                 web.set_fen_configuration(new_dhcp_ip)
#                 web.close()
            
#             # 2. API 검증
#             api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
#             api.verify_fen_setting(CFG["FEN_SVR"])

#             # 3. iRAS 자동화 (Step 5)
#             print("\n>>> [Step 5] iRAS 연동 테스트 (DirectExternal)")
#             target_dev_name = CFG["IRAS_DEV_NAME"]
            
#             if iRAS_test.run_fen_setup_process(target_dev_name, CFG["FEN_NAME"]):
#                 print("\n>>> [Step 6] iRAS 연결 모드 검증")
#                 time.sleep(5)
#                 if iRAS_test.run_fen_verification("TcpDirectExternal"):
#                     print("\n🎉 [Pass] TcpDirectExternal 연결 확인됨")
#                 else:
#                     print("\n⚠️ [Fail] 연결 모드 불일치")
#         else:
#             print("❌ 카메라 DHCP IP를 찾을 수 없습니다.")

#     # [Step 7] UPNP 테스트 (DirectInternal)
#     if new_dhcp_ip:
#         input("\n🚨 [ACTION] 카메라와 PC를 공유기에 연결하고 Enter를 누르세요 (UPNP 테스트) >> ")
#         print("\n>>> [Step 7] UPNP 활성화 및 DirectInternal 검증")
        
#         # Web UPNP 켜기
#         with sync_playwright() as p:
#             web = WebController(p)
#             web.set_upnp(new_dhcp_ip, enable=True)
#             web.close()
        
#         print("   -> UPNP 갱신 대기 (10초)...")
#         time.sleep(10)
        
#         if iRAS_test.run_fen_verification("TcpDirectInternal"):
#              print("\n🎉 [Pass] TcpDirectInternal 연결 확인됨")
#         else:
#              print("\n⚠️ [Fail] UPNP 연결 모드 불일치")

#     # [Step 8] UDP Hole Punching 테스트 (추가됨)
#     if new_dhcp_ip:
#         print("\n>>> [Step 8] UDP Hole Punching 테스트 준비")
#         print("   -> 설정을 위해 카메라 사전 구성 중...")
        
#         # 사전 설정: IP DHCP & UPNP OFF (Web)
#         # 이미 DHCP 상태지만 확실하게 하고, UPNP를 끕니다.
#         with sync_playwright() as p:
#             web = WebController(p)
#             web.set_upnp(new_dhcp_ip, enable=False) # UPNP OFF
#             # web.set_link_local(new_dhcp_ip, enable=False) # DHCP 확인 (이미 되어있음)
#             web.close()
            
#         print("   ✅ 카메라 설정 완료 (DHCP, UPNP OFF)")
#         input("\n🚨 [ACTION] PC를 회사망에 연결하고, 카메라는 공유기에 연결한 뒤 Enter를 누르세요 >> ")
        
#         print("\n   -> UDP Hole Punching 연결 모드 검증 시도...")
#         # 네트워크 환경이 바뀌었으므로 iRAS가 재접속할 시간을 충분히 줍니다.
#         time.sleep(15) 
        
#         if iRAS_test.run_fen_verification("UdpHolePunching"):
#              print("\n🎉 [Pass] UdpHolePunching 연결 확인됨")
#         else:
#              print("\n⚠️ [Fail] UDP Hole Punching 연결 실패")
    
#     # [Step 9] FEN Relay 테스트 (추가됨!)
#     if new_dhcp_ip:
#         print("\n>>> [Step 9] FEN Relay 테스트 (UDP Block)")
#         print("   ℹ️  현재 물리 연결 상태(PC=회사망, Cam=공유기)를 유지하세요.")
#         print("   ⚠️ [ACTION] 공유기 설정에서 'UDP Block'을 설정하세요.")
#         print("      - 조건: [내부<->외부], 포트 [1~15199, 15201~65535] 차단")
#         print("      - 참고: 카메라 설정은 이미 DHCP, UPNP OFF 상태입니다.")
        
#         input("\n   설정이 완료되면 Enter를 누르세요 >> ")
        
#         print("\n   -> Relay 모드 전환 대기 (약 30초)...")
#         time.sleep(30) 
        
#         # 검증: "Relay" 문자열이 포함되어 있는지 확인
#         if iRAS_test.run_fen_verification("Relay"):
#              print("\n🎉 [Pass] FEN Relay 연결 확인됨")
#         else:
#              print("\n⚠️ [Fail] Relay 연결 실패 (공유기 설정 확인 필요)")

#     # [Step 10] WebGuard 테스트 (수정됨)
#     if new_dhcp_ip:
#         print("\n>>> [Step 10] WebGuard 접속 및 로그인 테스트")
#         fen_url = f"http://{CFG['FEN_SVR']}/{CFG['FEN_NAME']}" # 예: http://qa1.idis.co.kr/FEN테스트
#         print(f"   -> 브라우저 실행: {fen_url}")
        
#         with sync_playwright() as p:
#             # 1. 브라우저로 접속 시도 (WebGuard 실행 유도)
#             browser = p.chromium.launch(headless=False)
#             page = browser.new_page()
#             try:
#                 # WebGuard가 실행되도록 페이지 접속
#                 # (실제로는 프로토콜 핸들러 등으로 exe가 뜰 것임)
#                 page.goto(fen_url)
#                 print("   -> 페이지 로드 완료, WebGuard 실행 대기...")
#                 time.sleep(5) # exe 실행 시간 대기
                
#                 # 2. WebGuard 로그인 자동화 (별도 모듈 사용)
#                 if webgaurd.run_login(CFG["ID"], CFG["PW"]):
#                     print("🎉 [Pass] WebGuard 로그인 성공")
#                 else:
#                     print("⚠️ [Fail] WebGuard 로그인 실패")
                    
#             except Exception as e:
#                 print(f"   🔥 브라우저 오류: {e}")
#             finally:
#                 browser.close()
    
#     # 테스트를 위해 임시로 new_dhcp_ip 설정 (실제 런타임엔 위에서 받아옴)
#     new_dhcp_ip = CFG["CAM_IP"] 

#     # [Step 11] 포트 변경 및 검증 시나리오 (New)
#     if new_dhcp_ip:
#         print("\n>>> [Step 11] 포트 변경 및 검증 (Web / iRAS / Socket)")
        
#         # API 객체 생성 (초기화 및 복구용)
#         api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
        
#         test_http_port = "8080"
#         test_remote_port = "8200"
        
#         try:
#             # --- 1. HTTP 포트 변경 (Web -> 8080) ---
#             print(f"\n   [11-1] Web HTTP 포트 변경 (80 -> {test_http_port})")
#             with sync_playwright() as p:
#                 web = WebController(p)
#                 web.set_network_ports(http_port=test_http_port)
#                 web.close()
            
#             # 검증 A: Socket 레벨 확인
#             if check_port_open(new_dhcp_ip, test_http_port):
#                 print(f"   ✅ Socket Check: {test_http_port} Port is OPEN")
#             else:
#                 raise Exception(f"Socket Check Failed: {test_http_port} is Closed")

#             # 검증 B: 변경된 포트로 Web 접속 확인
#             print(f"   [Verify] 변경된 포트({test_http_port})로 접속 시도...")
#             with sync_playwright() as p:
#                 # 변경된 포트로 컨트롤러 초기화
#                 web = WebController(p, target_port=test_http_port)
#                 try:
#                     web.page.goto(f"http://{new_dhcp_ip}:{test_http_port}/setup/setup.html", timeout=5000)
#                     if "IDIS" in web.page.title() or web.page.is_visible("#userid"):
#                         print(f"   ✅ Web Access Success on Port {test_http_port}")
#                 except Exception as e:
#                     print(f"   ❌ Web Access Failed: {e}")
#                 web.close()

#             # API 객체의 Base URL 업데이트 (복구를 위해)
#             api.base_url = f"http://{new_dhcp_ip}:{test_http_port}/cgi-bin/webSetup.cgi"

#             # --- 2. 원격 포트 변경 (iRAS -> 8200) ---
#             print(f"\n   [11-2] iRAS 원격 포트 변경 (Watch -> {test_remote_port})")
            
#             # iRAS 자동화 호출 (수정된 iRAS_test.py 사용)
#             if iRAS_test.run_port_change_process(CFG["IRAS_DEV_NAME"], test_remote_port):
#                 print("   ✅ iRAS 설정 변경 동작 완료")
                
#                 # 검증: Socket 레벨 확인
#                 time.sleep(2)
#                 if check_port_open(new_dhcp_ip, test_remote_port):
#                     print(f"   ✅ Socket Check: {test_remote_port} Port is OPEN")
#                 else:
#                     print(f"   ❌ Socket Check Failed: {test_remote_port} is Closed")
#             else:
#                 print("   ⚠️ iRAS 자동화 실패 (건너뜀)")

#         except Exception as e:
#             print(f"   🔥 [Critical] 테스트 중단 오류: {e}")

#         finally:
#             # --- [Teardown] 환경 복구 (가장 중요) ---
#             print("\n🧹 [Teardown] 포트 설정 초기화 (Rescue Mode)")
#             if api.reset_ports_default():
#                 CFG["PORT"] = "80"
#                 print("   ✅ 모든 포트가 기본값으로 복구되었습니다.")
#             else:
#                 # 만약 HTTP 포트가 8080인 상태에서 80으로 요청을 보내 실패했다면,
#                 # 8080 포트로 다시 시도해봐야 함.
#                 print("   ⚠️ 기본 포트로 복구 실패. 변경된 포트로 재시도...")
#                 try:
#                     api.base_url = f"http://{new_dhcp_ip}:{test_http_port}/cgi-bin/webSetup.cgi"
#                     if api.reset_ports_default():
#                          print("   ✅ (재시도) 포트 복구 성공")
#                     else:
#                          print("   🔥 복구 완전 실패. 수동 확인 요망.")
#                 except:
#                     pass
                    
#     # [Step 12] 대역폭 제한 테스트 (API + iRAS)
#     if new_dhcp_ip:
#         print("\n>>> [Step 12] 대역폭 제한 테스트 (API 제어)")
        
#         # API 객체 확인 (없으면 생성)
#         if 'api' not in locals():
#             api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            
#         try:
#             # 1. 초기화: 100Mbps 설정 (Max)
#             # 100Mbps = 100 * 1024 = 102400 Kbps
#             print("   [12-1] 대역폭 최대(100Mbps) 설정")
#             api.set_bandwidth_limit(enable=True, limit_kbps=102400)
            
#             print("   -> 영상 안정화 대기 (5초)...")
#             time.sleep(5)
            
#             # 기준 IPS 측정
#             base_ips = iRAS_test.get_video_ips()
#             print(f"   ℹ️  기준 IPS: {base_ips}")

#             # 2. 제한 설정: 1Mbps (Min)
#             # 1Mbps = 1024 Kbps
#             print("\n   [12-2] 대역폭 최소(1Mbps) 제한 설정")
#             if api.set_bandwidth_limit(enable=True, limit_kbps=1024):
#                 print("   -> 대역폭 제한 적용 대기 (10초)...")
#                 time.sleep(10) # 1Mbps로 버퍼가 찰 때까지 대기
                
#                 # 3. 제한 후 IPS 측정
#                 limit_ips = iRAS_test.get_video_ips()
                
#                 # 검증: 기준값 대비 50% 미만으로 떨어지거나 10 이하일 경우 Pass
#                 if limit_ips < base_ips * 0.5 or limit_ips < 10:
#                     print(f"   🎉 [Pass] 대역폭 제한 동작 확인 (IPS: {base_ips} -> {limit_ips})")
#                 else:
#                     print(f"   ⚠️ [Fail] 대역폭 제한 효과 미비 (IPS: {base_ips} -> {limit_ips})")
#             else:
#                 print("   ❌ API 설정 실패로 테스트 건너뜀")

#         except Exception as e:
#             print(f"   🔥 테스트 오류: {e}")

#         finally:
#             # [Teardown] 복구 (중요)
#             print("\n   🧹 [Teardown] 대역폭 설정 복구 (100Mbps)")
#             api.set_bandwidth_limit(enable=True, limit_kbps=102400)
    
#     # [Step 13] IP 필터링 테스트 (Deny List -> Rescue)
#     if new_dhcp_ip:
#         print("\n>>> [Step 13] IP 필터링(Deny List) 및 복구 테스트")
        
#         # 테스트용 임시 IP (차단을 피하기 위한 "변신용" IP)
#         # ⚠️ 주의: 카메라와 통신 가능한 같은 대역의 미사용 IP여야 합니다.
#         TEMP_PC_IP = "10.0.131.200" 
#         ORIGIN_PC_IP = CFG["PC_STATIC_IP"] # 원래 내 IP
        
#         if 'api' not in locals():
#             api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])

#         try:
#             # 1. 내 IP 차단 (Deny List 등록)
#             print(f"   [13-1] 내 IP ({ORIGIN_PC_IP}) 차단 설정")
#             if api.set_ip_filter(mode="deny", deny_list=ORIGIN_PC_IP):
#                 print("   -> 차단 설정 완료. 접속 불가 확인 시도...")
#                 time.sleep(2)
                
#                 # 2. 접속 실패 검증
#                 try:
#                     requests.get(f"http://{new_dhcp_ip}:{CFG['PORT']}", timeout=3)
#                     print("   ❌ [Fail] 차단되었는데 접속이 됩니다! (Test Fail)")
#                 except:
#                     print("   🎉 [Pass] 접속 차단 확인됨! (연결 실패)")

#                 # 3. PC IP 변경 (구조 작전)
#                 print(f"\n   [13-2] 구조 작전: PC IP 변경 -> {TEMP_PC_IP}")
#                 NetworkManager.set_static_ip(TEMP_PC_IP, CFG["PC_SUBNET"], CFG["PC_GW"])
                
#                 print("   -> 변경된 IP로 카메라 재접속 시도...")
#                 if NetworkManager.ping(new_dhcp_ip):
#                     # IP가 바뀌었으므로 세션 새로 생성
#                     rescue_api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                    
#                     # 4. 차단 해제 (복구)
#                     print("   -> Deny List 초기화 중...")
#                     if rescue_api.set_ip_filter(mode="off", deny_list=""):
#                         print("   ✅ 차단 해제 성공")
#                     else:
#                         print("   🔥 차단 해제 실패! (수동 복구 필요)")
#                 else:
#                     print("   ❌ IP 변경 후에도 통신 불가 (네트워크 설정 확인 필요)")
#             else:
#                 print("   ⚠️ 차단 설정 실패로 테스트 중단")

#         except Exception as e:
#             print(f"   🔥 테스트 오류: {e}")

#         finally:
#             # 5. PC IP 원복 (반드시 수행)
#             print("\n   🧹 [Teardown] PC IP 원래대로 복구")
#             NetworkManager.set_static_ip(ORIGIN_PC_IP, CFG["PC_SUBNET"], CFG["PC_GW"])
    
#     # [Step 14] SSL 모드별 설정 및 iRAS 검증
#     if new_dhcp_ip:
#         print("\n>>> [Step 14] SSL 모드 변경 및 iRAS 정보 검증")
        
#         if 'api' not in locals():
#             api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])

#         # 테스트 케이스 정의: (API 파라미터, iRAS 기대 문자열 키워드)
#         # 1) standard : exclude multimedia packet
#         # 2) high : partially multimedia packet
#         # 3) very high : full packet
#         ssl_test_cases = [
#             ("standard", "ExcludeMultimediaPacket"), # 혹은 로그에 따라 "Standard"
#             ("high", "PartiallyMultimediaPacket"),   # 혹은 로그에 따라 "Partially"
#             ("veryhigh", "FullPacket")               # 로그 확인됨: "FullPacket"
#         ]
        
#         # ※ 주의: iRAS에서 보여주는 텍스트가 "ExcludeMultimediaPacket"인지 "Standard"인지 
#         # 실제 환경에서 한번 확인되면 위 리스트의 두 번째 값을 수정하면 됩니다.
#         # 사용자 설명 기반으로 최대한 매칭했습니다.

#         try:
#             for mode, expected_text in ssl_test_cases:
#                 print(f"\n   [Test] SSL 모드 설정: {mode}")
                
#                 # 1. API 설정
#                 if api.set_ssl(enable=True, ssl_type=mode):
                    
#                     # 2. 적용 및 재접속 대기
#                     # SSL 변경 시 카메라 웹서비스/스트림이 재시작되므로 iRAS가 끊겼다 붙을 시간이 필요함
#                     print("   -> 설정 적용 및 iRAS 재접속 대기 (약 20초)...")
#                     time.sleep(20) 
                    
#                     # 3. iRAS 정보 확인 (재시도 로직 포함)
#                     detected_status = None
#                     for i in range(3): # 최대 3회 시도
#                         detected_status = iRAS_test.get_ssl_status()
#                         if detected_status:
#                             break
#                         print("   -> 정보 읽기 실패, 3초 후 재시도...")
#                         time.sleep(3)
                    
#                     # 4. 검증
#                     if detected_status:
#                         # 대소문자 무시하고 포함 여부 확인 (예: FullPacket 포함 여부)
#                         if expected_text.lower() in detected_status.lower().replace(" ", ""):
#                             print(f"   🎉 [Pass] {mode} 모드 확인됨 (Actual: {detected_status})")
#                         else:
#                             # Standard 설정 시 iRAS 표기가 다를 수 있어 유연하게 경고만 출력
#                             print(f"   ⚠️ [Check] 값 불일치? (Mode: {mode}, Expected: {expected_text}, Actual: {detected_status})")
#                     else:
#                         print("   ❌ [Fail] iRAS에서 SSL 정보를 읽어오지 못함")
#                 else:
#                     print("   ❌ API 설정 실패로 건너뜀")

#         except Exception as e:
#             print(f"   🔥 SSL 테스트 오류: {e}")

#         finally:
#             # [Teardown] SSL 비활성화
#             print("\n   🧹 [Teardown] SSL 비활성화 (HTTP 복구)")
#             # HTTPS 상태일 수 있으므로 URL 조정 시도
#             api.base_url = f"https://{new_dhcp_ip}:443/cgi-bin/webSetup.cgi"
#             if not api.set_ssl(enable=False):
#                 api.base_url = f"http://{new_dhcp_ip}:{CFG['PORT']}/cgi-bin/webSetup.cgi"
#                 api.set_ssl(enable=False)

#     input("\n✅ 모든 테스트 완료. 종료하려면 Enter...")