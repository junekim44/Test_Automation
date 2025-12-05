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

def get_local_ip():
    """현재 PC의 IP 주소를 반환"""
    try:
        # 실제 외부와 연결된 소켓을 통해 IP 확인
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
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

# =========================================================
# 🕵️ [API] 카메라 설정 검증기
# =========================================================
class CameraApi:
    def __init__(self, ip, port, user_id, user_pw):
        self.base_url = f"http://{ip}:{port}/cgi-bin/webSetup.cgi"
        self.session = requests.Session()
        self.session.auth = HTTPDigestAuth(user_id, user_pw)

    def _get_config(self, action):
        """설정값 읽기 (디버깅 강화 버전)"""
        try:
            url = f"{self.base_url}?action={action}&mode=1"
            res = self.session.get(url, timeout=5)
            if res.status_code == 200:
                return dict(parse_qsl(res.text))
            else:
                print(f"   ⚠️ [API Read Fail] Status: {res.status_code}, Msg: {res.text.strip()}")
        except Exception as e:
            print(f"   ⚠️ [API Read Error] {e}")
        return {}
    
    def set_link_local_api(self, enable=True):
        """API로 Link-Local 설정 변경"""
        val = "on" if enable else "off"
        print(f"📡 [API] Link-Local 설정: {val}...", end="")
        current_config = self._get_config("networkIp")
        if not current_config:
            print(" ❌ 설정 읽기 실패")
            return False
        current_config["action"] = "networkIp"
        current_config["mode"] = "0"
        current_config["linkLocalOnly"] = val
        if "returnCode" in current_config: del current_config["returnCode"]
        try:
            res = self.session.post(self.base_url, data=current_config, timeout=10)
            if "returnCode=0" in res.text or "returnCode=301" in res.text:
                print(" 성공 ✅")
                return True
            print(f" 실패 ❌ ({res.text.strip()})")
            return False
        except Exception as e:
            print(f" 오류 🔥 ({e})")
            return False
        
    def set_fen_api(self, fen_name, fen_server="qa1.idis.co.kr"):
        """
        API로 FEN 설정 및 이름 중복 검사 수행 (API 8. Network - DDNS)
        """
        print(f"📡 [API] FEN 설정 요청: {fen_name} ({fen_server})...", end="")
        
        # 1. 설정 적용 (Mode 0)
        # 🌟 [수정] port 파라미터 추가 (필수)
        payload = {
            "action": "networkDDNS",
            "mode": "0",
            "useDDNS": "on",
            "serverAddress": fen_server,
            "port": "10088",  # FEN 기본 포트 추가
            "cameraName": fen_name,
            "useNAT": "off" 
        }
        
        try:
            res = self.session.post(self.base_url, data=payload, timeout=10)
            
            # 🌟 [수정] networkDDNS에서 301은 명백한 에러(Invalid Parameter)입니다. 성공 처리 제외.
            if "returnCode=0" in res.text:
                print(" 설정 성공 ✅")
            else:
                # 에러 메시지 상세 출력
                print(f" 설정 실패 ❌ (Code: {res.text.strip()})")
                return False
            
            # 설정 반영 대기
            time.sleep(2)

            # 2. FEN 이름 확인 (Check - Mode 2)
            print("   -> FEN 이름 유효성 검사(Check)...", end="")
            check_payload = {
                "action": "networkDDNS",
                "mode": "2",
                "serverAddress": fen_server,
                "port": "10088", # Check 할 때도 포트 정보 포함 권장
                "cameraName": fen_name,
                "useNAT": "off"
            }
            res_check = self.session.post(self.base_url, data=check_payload, timeout=10)
            
            if "returnCode=0" in res_check.text:
                print(" 확인 완료 (사용 가능) ✅")
                return True
            else:
                print(f" 확인 실패 ❌: {res_check.text.strip()}")
                return False
                
        except Exception as e:
            print(f" 오류 🔥 ({e})")
            return False
        
    def verify_fen_setting(self, expected_server):
        data = self._get_config("networkDDNS")
        use_ddns = data.get("useDDNS") == "on"
        server_match = data.get("serverAddress") == expected_server
        print(f"📡 [API] FEN 검증: Use={use_ddns}, Server={data.get('serverAddress')} -> {'Pass' if use_ddns and server_match else 'Fail'}")
        return use_ddns and server_match
    
    def set_upnp_api(self, enable=True):
        """API로 UPNP 설정 변경"""
        val = "on" if enable else "off"
        print(f"📡 [API] UPNP 설정 변경 요청: {val}...", end="")
        payload = {"action": "networkPort", "mode": "0", "useUPNP": val}
        try:
            res = self.session.post(self.base_url, data=payload, timeout=15)
            if "returnCode=0" in res.text or "returnCode=301" in res.text:
                print(" 성공 ✅")
                return True
            print(f" 실패 ❌ ({res.text.strip()})")
            return False
        except Exception as e:
            print(f" 오류 🔥 ({e})")
            return False

    def set_ports_api(self, web_port=None, watch_port=None):
        """
        포트 변경 및 검증 함수 (세션 초기화 로직 적용)
        """
        current_ip = self.base_url.split("://")[1].split(":")[0]
        
        changes = []
        if web_port: changes.append(f"HTTP={web_port}")
        if watch_port: changes.append(f"Service(Admin/Watch/Search)={watch_port}")
        print(f"📡 [API] 포트 변경 요청: {', '.join(changes)}...", end="")

        # 1. 현재 설정 읽기
        cfg = self._get_config("networkPort")
        if not cfg:
            print(" (설정 읽기 실패, 강제 진행)...", end="")
            cfg = {}

        # 2. 파라미터 구성 (모든 서비스 포트 동기화)
        target_service_port = str(watch_port) if watch_port else cfg.get("watchPort", "8016")
        target_web_port = str(web_port) if web_port else cfg.get("webPort", "80")

        payload = {
            "action": "networkPort",
            "mode": "0",
            "useWeb": cfg.get("useWeb", "on"),
            "useRtsp": cfg.get("useRtsp", "on"),
            "useUPNP": cfg.get("useUPNP", "off"),
            "useHTTPS": cfg.get("useHTTPS", "off"),
            
            "webPort": target_web_port,
            "adminPort": target_service_port,
            "watchPort": target_service_port,
            "searchPort": target_service_port,
            "remotePort": target_service_port,
            
            "rtspPort": cfg.get("rtspPort", "554"),
            "recordPort": cfg.get("recordPort", "8017"),
        }

        # 3. 명령 전송 (기존 세션 사용)
        try:
            self.session.post(self.base_url, data=payload, timeout=3)
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            pass # 끊김 허용
        except Exception as e:
            print(f" 전송 중 에러({e}) -> 검증 시도...", end="")

        # 4. [검증] 변경된 포트로 Read 요청 (새 세션 사용!)
        verify_url = f"http://{current_ip}:{target_web_port}/cgi-bin/webSetup.cgi"
        print(f"\n   -> 🔄 변경된 포트({target_web_port})로 검증 시도...", end="")
        
        # [핵심] 포트가 바뀌었으므로 '새로운 세션' 생성 (기존 연결 간섭 방지)
        new_session = requests.Session()
        new_session.auth = self.session.auth # ID/PW만 복사
        
        for i in range(20): # 최대 20초 대기 (충분한 시간 확보)
            try:
                time.sleep(1)
                # 타임아웃 2초로 짧게 끊어서 확인
                res = new_session.get(f"{verify_url}?action=networkPort&mode=1", timeout=2)
                
                if res.status_code == 200 and "returnCode=0" in res.text:
                    new_data = dict(parse_qsl(res.text))
                    # 값이 실제로 바뀌었는지 확인
                    if (new_data.get('webPort') == target_web_port):
                        print(" 성공 (설정값 적용 확인됨) 🎯")
                        
                        # 검증 성공 시, 메인 세션을 새 세션으로 교체 및 URL 업데이트
                        self.session = new_session
                        self.base_url = verify_url 
                        return True
            except Exception as e:
                # 에러 메시지 확인용 (너무 길면 주석 처리)
                # print(f"({e})", end="") 
                print(".", end="")
                continue
                
        print(f" 실패 ❌ (20초 응답 없음 - 수동 확인 필요)")
        return False

    def reset_ports_default(self):
        """
        포트 설정 초기화 (최신 펌웨어 기준: 8016 통합)
        - HTTP: 80
        - Admin/Watch/Search/Remote: 8016 (모두 통일)
        - UPnP: OFF
        """
        print("🚑 [API] 포트 설정을 기본값(HTTP:80, Service:8016)으로 복구 요청...", end="")
        
        payload = {
            "action": "networkPort",
            "mode": "0",
            "useWeb": "on",
            "useRtsp": "on",
            "useHTTPS": "off",
            "useUPNP": "off",          # UPnP 끔
            
            "webPort": "80",           # HTTP Default
            "rtspPort": "554",         # RTSP Default
            "recordPort": "8016",      # Record Default
            
            # [핵심] 모든 서비스 포트를 8016으로 통일
            "adminPort": "8016",       
            "watchPort": "8016",       
            "searchPort": "8016",      
            "remotePort": "8016"       
        }
        
        try:
            res = self.session.post(self.base_url, data=payload, timeout=5)
            if "returnCode=0" in res.text or "returnCode=301" in res.text:
                print(" 성공 ✅")
                time.sleep(5) 
                return True
            else:
                print(f" 실패 (응답: {res.text.strip()})")
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            print(" 성공 (연결 끊김 - 복구 명령 적용됨) ✅")
            time.sleep(5)
            return True
        except Exception as e:
            print(f" 실패 (통신오류: {e})")
        return False
    
    def set_bandwidth_limit(self, enable=True, limit_kbps=102400):
        action_str = f"{limit_kbps} Kbps" if enable else "OFF"
        print(f"📡 [API] 대역폭 제한 설정: {action_str}...", end="")
        payload = {"action": "networkBandwidth", "mode": "0", "useNetworkBandwidth": "on" if enable else "off", "networkBandwidth": str(limit_kbps)}
        try:
            res = self.session.post(self.base_url, data=payload, timeout=5)
            if "returnCode=0" in res.text:
                print(" 성공 ✅")
                return True
            print(f" 실패 ❌ (응답: {res.text.strip()})")
        except Exception as e:
            print(f" 오류 🔥 ({e})")
        return False
    
    def set_ip_filter(self, mode="off", allow_list="", deny_list=""):
        print(f"🛡️ [API] IP 필터 설정 변경: Mode={mode}, Deny={deny_list}...", end="")
        payload = {"action": "networkSecurity", "mode": "0", "filterType": mode, "allowList": allow_list, "denyList": deny_list, "useSSL": "off", "sslType": "standard"}
        try:
            res = self.session.post(self.base_url, data=payload, timeout=5)
            if "returnCode=0" in res.text:
                print(" 성공 ✅")
                return True
            print(f" 실패 ❌ ({res.text.strip()})")
        except Exception as e:
            print(f" 오류 🔥 ({e})")
        return False

    def set_ssl(self, enable=True, ssl_type="standard"):
        val = "on" if enable else "off"
        print(f"🔒 [API] SSL 설정 변경 요청: {val} (Type={ssl_type})...", end="")
        payload = {"action": "networkSecurity", "mode": "0", "useSSL": val, "sslType": ssl_type, "filterType": "off"}
        try:
            res = self.session.post(self.base_url, data=payload, timeout=10)
            if "returnCode=0" in res.text or "returnCode=301" in res.text:
                print(" 성공 ✅")
                return True
            print(f" 실패 ❌ ({res.text.strip()})")
        except Exception as e:
            print(f" 오류 🔥 ({e})")
        return False
        
    def set_ip_address_api(self, mode_type="manual", ip=None, gateway=None, subnet=None, link_local_off=False):
        """
        API로 IP 설정 변경 (Read-Modify-Write 방식 적용)
        """
        action_desc = f"{mode_type}"
        if link_local_off: action_desc += " + LinkLocal(OFF)"
        
        print(f"📡 [API] 네트워크 설정 변경: {action_desc}...", end="")
        
        # 1. 현재 설정 읽기 (Mode 1)
        current_config = self._get_config("networkIp")
        if not current_config:
            print(" ❌ 설정 읽기 실패")
            return False

        # 2. 값 수정
        current_config["action"] = "networkIp"
        current_config["mode"] = "0"  # Write 모드
        current_config["type"] = mode_type
        
        if link_local_off:
            current_config["linkLocalOnly"] = "off"

        # 수동(Static)일 경우 IP 정보 덮어쓰기
        if mode_type == "manual":
            if not (ip and gateway and subnet):
                print(f" ❌ IP 정보 부족")
                return False
            current_config["ipAddress"] = ip
            current_config["gateway"] = gateway
            current_config["subnetMask"] = subnet
            # DNS 정보가 비어있으면 기본값 채워주기 (필수일 수 있음)
            if not current_config.get("dnsServer"):
                current_config["dnsServer"] = gateway # 보통 게이트웨이를 DNS로 씀

        # 읽기 전용 필드 제거 (오류 방지)
        if "returnCode" in current_config: del current_config["returnCode"]
        if "ipv6Address" in current_config: del current_config["ipv6Address"] 

        # 3. 설정 쓰기
        try:
            try:
                res = self.session.post(self.base_url, data=current_config, timeout=10)
                
                # 301 리턴코드도 성공으로 처리 (재부팅/재접속 신호)
                if "returnCode=0" in res.text or "returnCode=301" in res.text:
                    print(" 성공 (설정 적용됨) ✅")
                    return True
                else:
                    print(f" 실패 ❌ (응답: {res.text.strip()})")
                    return False
            except requests.exceptions.ReadTimeout:
                print(" 성공 (타임아웃 - IP 변경/재부팅 예상) ✅")
                return True
            except requests.exceptions.ConnectionError:
                print(" 성공 (연결 끊김 - IP 변경 예상) ✅")
                return True
                
        except Exception as e:
            print(f" 오류 🔥 ({e})")
            return False
    

# =========================================================
# 🚀 Main Execution Flow
# =========================================================

def _run_web_action(action_func, *args, **kwargs):
    try:
        with sync_playwright() as p:
            controller = WebController(p)
            result = action_func(controller, *args, **kwargs)
            controller.close()
            return result
    except Exception as e:
        print(f"🔥 Web Action Error: {e}")
        return None

def _action_get_mac(web, ip): return web.get_mac_address(ip)
def _action_verify_web_access(web, ip, port):
    target_url = f"http://{ip}:{port}/setup/setup.html"
    print(f"   🌐 접속 시도: {target_url}")
    
    # [수정] 최대 2회 시도
    for attempt in range(2):
        try:
            # 1. 페이지 이동 (타임아웃 30초로 증가)
            print(f"      -> 페이지 로딩 중... (시도 {attempt+1}/2)")
            web.page.goto(target_url, timeout=30000) 
            
            # 2. 로딩 완료 대기 (ID 입력창 혹은 타이틀)
            try:
                # 입력창이 뜰 때까지 최대 5초 대기
                web.page.wait_for_selector("#userid", state="visible", timeout=5000)
                print("   ✅ 로그인 화면(ID 입력창) 확인됨")
                return True
            except:
                # 입력창이 안 뜨면 타이틀 확인
                title = web.page.title()
                print(f"      -> 현재 페이지 타이틀: '{title}'")
                if "IDIS" in title or "Camera" in title or "setup" in title:
                    print(f"   ✅ 페이지 타이틀로 접속 확인 성공")
                    return True
                else:
                    print("      ⚠️ 타이틀이나 입력창을 찾을 수 없음")
                    
        except Exception as e:
            print(f"      ⚠️ 접속 에러 ({attempt+1}차): {e}")
            time.sleep(3) # 3초 쉬고 재시도

    # 실패 시 스크린샷 저장 (디버깅용)
    try:
        web.page.screenshot(path="error_screenshot.png")
        print("   📸 실패 화면 저장됨: error_screenshot.png")
    except: pass
    
    return False
def _action_webguard_login(web_dummy, fen_url, user, pw):
    try:
        page = web_dummy.page
        page.goto(fen_url); time.sleep(5)
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
            target_mac = _run_web_action(_action_get_mac, target_ip) # MAC은 Web에서 가져옴
            if target_mac:
                # API로 Link Local 설정
                api = CameraApi(target_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                api.set_link_local_api(enable=True)
        else:
            return False, "초기 카메라 접속 실패"

        if not target_mac:
            return False, "MAC 주소 확보 실패"

        # [Step 2] Auto-IP 검증 및 DHCP 전환
        print("\n>>> [Step 2] 169.254 Auto-IP 검증 및 DHCP 설정")
        NetworkManager.set_static_ip(CFG["PC_AUTO_IP"], CFG["AUTO_SUBNET"])
        NetworkManager.run_cmd("arp -d *")
        
        auto_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_AUTO_NET"], timeout=40)
        
        if auto_ip and "169.254" in auto_ip:
            print(f"🎉 Auto-IP 접속 성공: {auto_ip}")
            
            api_auto = CameraApi(auto_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            
            # 🌟 [수정] Link-Local 해제와 DHCP 설정을 '한 번에' 보냄
            print("   -> [통합 명령] Link-Local 해제 + DHCP 전환 요청...")
            if api_auto.set_ip_address_api(mode_type="dhcp", link_local_off=True):
                print("   ✅ DHCP & Link-Local OFF 설정 완료")
            else:
                print("   ⚠️ 설정 실패 (재부팅 후 확인 필요)")
        else:
            print("⚠️ Auto-IP 탐색 실패 (이미 DHCP일 수 있음)")

        # [Step 4] 복구 및 FEN (API)
        NetworkManager.set_dhcp()
        
        if NetworkManager.wait_for_dhcp("10."):
            print("   -> ARP 캐시 초기화...")
            NetworkManager.run_cmd("arp -d *") # 🌟 중요: 윈도우가 기억하는 옛날 IP 삭제
            time.sleep(2)
            
            print(f"   -> DHCP 할당된 새 IP 탐색 (MAC: {target_mac})...")
            
            # 🌟 스캔 시도 (최대 60초)
            # find_ip_combined가 '10.0.131.104'를 또 찾을 수도 있으니, 
            # 만약 찾은 IP가 고정 IP(CFG["CAM_IP"])와 같다면, 
            # "이거 말고 다른거 찾아!"라고 재시도 로직을 넣거나 
            # 사용자가 DHCP 서버에서 할당받았을 법한 IP인지 확인해야 합니다.
            
            new_dhcp_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=60)
            
            # (선택) 만약 여전히 10.0.131.104라면, 정말로 DHCP가 안 먹힌 것임.
            if new_dhcp_ip == CFG["CAM_IP"]:
                print(f"   -> DHCP 할당된 새 IP 탐색 (MAC: {target_mac})...")
            
            # [수정] 반복 탐색 로직 추가: 'ARP Cache'가 옛날 IP를 반환하면 무시하고 재탐색
            start_scan = time.time()
            new_dhcp_ip = None
            
            while time.time() - start_scan < 60:  # 60초 동안 유효한 IP 찾기 시도
                temp_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=5)
                
                if temp_ip:
                    # [1] 찾은 IP가 기존 고정 IP(Static)와 같은지 확인
                    if temp_ip == CFG["CAM_IP"]:
                        print(f"   ⚠️ [Check] 기존 IP({temp_ip})가 감지됨. 실제 연결 가능한지 Ping 테스트...")
                        if NetworkManager.ping(temp_ip, timeout=2):
                            print("   -> 기존 IP로 연결됨 (DHCP 할당 실패 또는 동일 IP 할당).")
                            new_dhcp_ip = temp_ip
                            break
                        else:
                            print("   -> Ping 실패! (Stale ARP Cache). 무시하고 계속 검색합니다...")
                            NetworkManager.run_cmd("arp -d *")
                            time.sleep(2)
                            continue

                    # [2] 169.254.x.x (Link-Local) 무시 로직 추가 [핵심!]
                    elif temp_ip.startswith("169.254"):
                        print(f"   ⚠️ [Skip] Auto-IP({temp_ip}) 감지됨. DHCP IP(10.x 등)를 기다립니다...")
                        time.sleep(1)
                        continue

                    # [3] 그 외의 새로운 IP 발견 (DHCP 성공으로 간주)
                    else:
                        print(f"   ✅ 새로운 IP 발견: {temp_ip}")
                        new_dhcp_ip = temp_ip
                        break
            
            if new_dhcp_ip and NetworkManager.ping(new_dhcp_ip):
                print(f"🎉 카메라 재접속 성공: {new_dhcp_ip}")
                
                api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                # API로 FEN 설정
                api.set_fen_api(CFG["FEN_NAME"], CFG["FEN_SVR"])
                api.verify_fen_setting(CFG["FEN_SVR"])

                # [Step 5] iRAS
                print("\n>>> [Step 5] iRAS 연동 테스트 (DirectExternal)")
                if iRAS_test.run_fen_setup_process(CFG["IRAS_DEV_NAME"], CFG["FEN_NAME"]):
                    iRAS_test.wait_for_connection()
                    _refresh_session(api)
                    if iRAS_test.run_fen_verification("TcpDirectExternal"):
                        print("🎉 [Pass] TcpDirectExternal 확인")
                    else:
                        print("   ⚠️ 1차 검증 실패, 재시도...")
                        if iRAS_test.run_fen_verification("TcpDirectExternal"):
                            print("🎉 [Pass] TcpDirectExternal 확인 (재시도 성공)")

        # [Step 7] UPNP (DirectInternal)
        router_cam_ip = None 
        if new_dhcp_ip:
            print("\n>>> [Step 7] UPNP 활성화 및 DirectInternal 검증")
            print("   ℹ️  UPNP 확인을 위해 공유기 환경으로 이동합니다.")
            input("🚨 [ACTION] 카메라와 PC를 모두 '공유기'에 연결하고 Enter >> ")
            
            NetworkManager.set_dhcp(); NetworkManager.wait_for_dhcp("192.")
            print("   -> 공유기 환경에서 카메라 IP 재탐색...")
            router_cam_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=40)
            if not router_cam_ip: router_cam_ip = auto_ip 
            
            if router_cam_ip:
                print(f"   ✅ 타겟 IP 확보: {router_cam_ip}")
                api = CameraApi(router_cam_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                # API로 UPNP ON
                if not api.set_upnp_api(enable=True):
                    print("   ⚠️ API 설정 실패")
                
                iRAS_test.wait_for_connection()
                if iRAS_test.run_fen_verification("TcpDirectInternal"): print("🎉 [Pass] TcpDirectInternal 확인")
                else: print("⚠️ [Fail] TcpDirectInternal 실패")
            else:
                print("❌ 공유기 환경에서 카메라를 찾을 수 없어 Step 7~8 중단")

        # [Step 8] UDP Hole Punching
        if router_cam_ip:
            print("\n>>> [Step 8] UDP Hole Punching")
            print("   -> [설정] 카메라 UPNP 비활성화(OFF)...")
            # API로 UPNP OFF
            api.set_upnp_api(enable=False)
            time.sleep(5)
            _refresh_session(api)

            print("\n⚠️ [Move] 공유기 upnp 해제 후 PC만 사내망으로 이동합니다.")
            input("🚨 [ACTION] PC 랜선을 '사내망'으로 옮기고 Enter >> ")
            NetworkManager.set_dhcp(); NetworkManager.wait_for_dhcp("10.")
            iRAS_test.wait_for_connection()
            
            if iRAS_test.run_fen_verification("UdpHolePunching"): print("🎉 [Pass] UdpHolePunching 확인")
            else: print("⚠️ [Fail] UDP Hole Punching 실패")

        # [Step 9] FEN Relay
        if router_cam_ip:
            print("\n>>> [Step 9] FEN Relay (UDP Block)")
            input("🚨 [ACTION] 공유기 설정에서 'UDP 차단' 후 회사 망 복귀 Enter >> ")
            iRAS_test.wait_for_connection()
            if iRAS_test.run_fen_verification("Relay"): print("🎉 [Pass] FEN Relay 확인")
            else: print("⚠️ [Fail] FEN Relay 실패")

            print("\n🧹 [Restore] 카메라 사내망 복귀...")
            input("🚨 [ACTION] '카메라'를 사내망(허브)으로 연결 후 Enter >> ")
            new_dhcp_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=10)

        # [Step 10] WebGuard
        if new_dhcp_ip:
            print("\n>>> [Step 10] WebGuard Login")
            fen_url = f"http://{CFG['FEN_SVR']}/{CFG['FEN_NAME']}"
            if _run_web_action(_action_webguard_login, fen_url, CFG["ID"], CFG["PW"]):
                print("🎉 [Pass] WebGuard Login")
    
        # [Step 15] 복구 (먼저 실행하여 Static 상태로 만듦)
        if new_dhcp_ip:
            print("\n>>> [Step 15] 전체 네트워크 설정 복구 (Web & iRAS -> Static IP)")
            restore_ip = CFG["CAM_IP"]       
            restore_gw = CFG["PC_GW"]        
            restore_subnet = CFG["PC_SUBNET"]
            
            print(f"   [15-1] Web: 카메라({new_dhcp_ip})를 고정 IP({restore_ip})로 변경합니다...")
            # API로 고정 IP 설정 변경
            api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            if api.set_ip_address_api(mode_type="manual", ip=restore_ip, gateway=restore_gw, subnet=restore_subnet):
                print("   ✅ Web 설정 변경 명령 전송 완료 (대기 5초)...")
                time.sleep(5)
            else:
                print("   ⚠️ Web 설정 변경 실패")
            
            print(f"   -> 카메라 통신 확인 중 ({restore_ip})...")
            if NetworkManager.ping(restore_ip, timeout=10):
                print(f"   ✅ 카메라 통신 확인 완료")
                print(f"   [15-3] iRAS: 연결 정보를 고정 IP({restore_ip})로 수정...")
                if iRAS_test.run_restore_ip_process(CFG["IRAS_DEV_NAME"], restore_ip):
                    print("   ✅ iRAS 복구 및 저장 완료")
                    iRAS_test.wait_for_connection()
                else: print("   ⚠️ iRAS 복구 실패")
            else: print("   ❌ 카메라 통신 불가")

        # 이제부터 테스트 대상 IP는 고정 IP
        current_test_ip = CFG["CAM_IP"]
        
        # [Step 11] 포트 변경 및 검증 (Web:8080, iRAS:9200)
        if current_test_ip:
            print("\n>>> [Step 11] 임의 포트 변경 및 검증 테스트")
            print("    목표 1: HTTP 포트 80 -> 8080 변경")
            print("    목표 2: Watch(원격) 포트 8016 -> 9200 변경")
            
            # API 객체 생성 (초기 80 포트)
            api = CameraApi(current_test_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            
            test_http_port = "8080"
            test_watch_port = "9200" 
            
            try:
                print(f"\n   [11-1] 카메라 포트 변경 API 전송 및 검증...")
                
                # 1. API 호출 (내부에서 Write -> Read(8080) -> Verify 수행)
                if api.set_ports_api(web_port=test_http_port, watch_port=test_watch_port):
                    print("   -> API 검증 완료. (설정 적용됨)")
                    
                    # 성공 시 CFG 업데이트 (Teardown에서 참조용)
                    CFG["PORT"] = test_http_port
                    # api.base_url은 set_ports_api 내부에서 이미 8080으로 업데이트 되었습니다.
                else: 
                    raise Exception("API 포트 변경 실패 (새 포트 응답 없음)")

                # 2. Web 접속 테스트 (Playwright)
                print(f"\n   [11-2] Web 접속 테스트 (Target: {test_http_port})")
                if check_port_open(current_test_ip, test_http_port):
                    print(f"   ✅ Socket Check: {test_http_port} is OPEN")

                    # 웹 서비스(httpd) 로딩 대기 시간 (3초)
                    print("   -> 웹 서비스 안정화 대기 (3초)...") 
                    time.sleep(3)

                    if _run_web_action(_action_verify_web_access, current_test_ip, test_http_port):
                         print(f"   🎉 Web Access Success (페이지 로딩 확인)")
                    else: print(f"   ❌ Web Access Failed (페이지 로딩 실패)")
                else: print(f"   ❌ Socket Check: {test_http_port} is CLOSED")

                # 3. iRAS 접속 테스트
                print(f"\n   [11-3] iRAS 접속 테스트 (Target: {test_watch_port})")
                if check_port_open(current_test_ip, test_watch_port):
                    print(f"   ✅ Socket Check: {test_watch_port} is OPEN")
                    
                    print(f"   -> iRAS 설정을 {test_watch_port}로 변경...")
                    if iRAS_test.run_port_change_process(CFG["IRAS_DEV_NAME"], test_watch_port, target_ip=current_test_ip):
                        print("   -> iRAS 설정 변경 완료. 영상 연결 대기...")
                        
                        if iRAS_test.wait_for_connection(timeout=60): 
                            print(f"   🎉 iRAS Access Success (포트 {test_watch_port} 정상 동작)")
                        else: 
                            print("   ⚠️ iRAS 영상 연결 실패 (시간 초과)")
                    else: print("   ⚠️ iRAS 자동화 제어 실패")
                else: print(f"   ❌ Socket Check: {test_watch_port} is CLOSED")

            except Exception as e:
                print(f"   🔥 [Critical] Step 11 테스트 중단: {e}")

            finally:
                print("\n🧹 [Teardown] 포트 설정 초기화 및 복구")
                
                # 1. 카메라 API 복구
                print("   [1] 카메라 API 포트 복구 시도...")
                # 현재 설정된 포트(CFG)와 8080, 80을 모두 시도하여 가장 먼저 연결되는 곳에서 복구 명령 전송
                ports_to_try = [CFG["PORT"], "8080", "80"]
                # 중복 제거 및 정렬 (현재 설정된 포트 우선)
                ports_to_try = sorted(list(set(ports_to_try)), key=lambda x: 0 if x == CFG["PORT"] else 1)
                
                recovered_cam = False
                for p in ports_to_try:
                    if not p: continue
                    try:
                        print(f"   -> 접속 시도 (Port: {p})...", end="")
                        api.base_url = f"http://{current_test_ip}:{p}/cgi-bin/webSetup.cgi"
                        
                        # 복구 함수 호출 (HTTP:80, Remote:8016, UPnP:OFF)
                        if api.reset_ports_default():
                            print(" 성공 ✅")
                            recovered_cam = True
                            break
                        else: print(" 실패 (API 응답 에러)")
                    except: print(" 실패 (연결 불가)")
                
                if recovered_cam:
                    CFG["PORT"] = "80" # 전역 설정 원복
                    print("   -> 카메라 포트 복구 완료 (HTTP:80 / Remote:8016 / UPnP:OFF)")
                    print("   -> 안정화 대기 (5초)...")
                    time.sleep(5)
                else:
                    print("   🔥 카메라 포트 복구 실패! (수동 확인 필요)")

                        
        # [Step 12] 대역폭 제한 테스트
        if current_test_ip:
            print("\n>>> [Step 12] 대역폭 제한 테스트 (API 제어)")
            api = CameraApi(current_test_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            try:
                print("   [12-1] 대역폭 최대(100Mbps) 설정")
                api.set_bandwidth_limit(enable=True, limit_kbps=102400)
                time.sleep(5)
                base_ips = iRAS_test.IRASController().get_current_ips()
                print(f"   ℹ️  기준 IPS: {base_ips}")

                print("\n   [12-2] 대역폭 최소(100Kbps) 제한 설정")
                if api.set_bandwidth_limit(enable=True, limit_kbps=1024):
                    print("   -> 대역폭 제한 적용 대기 (15초)...")
                    time.sleep(15)
                    limit_ips = iRAS_test.IRASController().get_current_ips()
                    if limit_ips < base_ips * 0.5 or limit_ips < 10: print(f"   🎉 [Pass] 제한 동작 확인 (IPS: {base_ips} -> {limit_ips})")
                    else: print(f"   ⚠️ [Fail] 효과 미비 (IPS: {base_ips} -> {limit_ips})")
            except Exception as e: print(f"   🔥 테스트 오류: {e}")
            finally:
                print("\n   🧹 [Teardown] 대역폭 설정 복구")
                api.set_bandwidth_limit(enable=True, limit_kbps=102400)
        
        # [Step 13] IP 필터링 테스트
        if current_test_ip:
            print("\n>>> [Step 13] IP 필터링(Deny List) 및 복구 테스트")
            TEMP_PC_IP = "10.0.131.200"; ORIGIN_PC_IP = get_local_ip() 
            api = CameraApi(current_test_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            try:
                print(f"   [13-1] 내 IP ({ORIGIN_PC_IP}) 차단 설정")
                if api.set_ip_filter(mode="deny", deny_list=ORIGIN_PC_IP):
                    print("   -> 차단 설정 완료. 접속 불가 확인 시도...")
                    time.sleep(5)
                    try:
                        requests.get(f"http://{current_test_ip}:{CFG['PORT']}", timeout=3)
                        print("   ❌ [Fail] 차단되었는데 접속이 됩니다!")
                    except: print("   🎉 [Pass] 접속 차단 확인됨! (연결 실패)")

                    print(f"\n   [13-2] 구조 작전: PC IP 변경 -> {TEMP_PC_IP}")
                    NetworkManager.set_static_ip(TEMP_PC_IP, CFG["PC_SUBNET"], CFG["PC_GW"])
                    
                    if NetworkManager.ping(current_test_ip):
                        rescue_api = CameraApi(current_test_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
                        print("   -> Deny List 초기화 중...")
                        if rescue_api.set_ip_filter(mode="off", deny_list=""): print("   ✅ 차단 해제 성공")
                        else: print("   🔥 차단 해제 실패! (수동 복구 필요)")
                    else: print("   ❌ IP 변경 후에도 통신 불가")
            except Exception as e: print(f"   🔥 테스트 오류: {e}")
            finally:
                print("\n   🧹 [Teardown] PC IP 원래대로 복구")
                NetworkManager.set_static_ip(CFG["PC_STATIC_IP"], CFG["PC_SUBNET"], CFG["PC_GW"])
        
        # [Step 14] SSL 모드별 설정 및 iRAS 검증
        if current_test_ip:
            print("\n>>> [Step 14] SSL 모드 변경 및 iRAS 정보 검증")
            print("    (참고: API 제어는 HTTP 유지, SSL 설정은 영상/프로토콜 암호화 적용)")
            
            # API 객체 확인 (없으면 생성)
            api = CameraApi(current_test_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
            
            # SSL 모드별 기대 값 (iRAS 클립보드 정보)
            ssl_test_cases = [
                ("standard", "ExcludeMultimediaPacket"), 
                ("high", "PartiallyMultimediaPacket"), 
                ("veryHigh", "FullPacket")
            ]
            
            try:
                for mode, expected_text in ssl_test_cases:
                    print(f"\n   [Test] SSL 모드 설정: {mode}")
                    
                    # API로 SSL 설정 변경 (HTTP로 전송)
                    if api.set_ssl(enable=True, ssl_type=mode):
                        # veryhigh는 암호화 부하로 적용 시간이 더 걸릴 수 있음
                        wait_time = 20
                        print(f"   -> 설정 적용 대기 (약 {wait_time}초)...")
                        time.sleep(wait_time) 
                        
                        # iRAS에서 SSL 상태 확인 (클립보드 파싱)
                        detected_status = None
                        for i in range(3):
                            detected_status = iRAS_test.IRASController().get_current_ssl_info()
                            if detected_status: break
                            time.sleep(5)
                        
                        if detected_status:
                            clean_detected = detected_status.lower().replace(" ", "")
                            clean_expected = expected_text.lower().replace(" ", "")
                            
                            if clean_expected in clean_detected: 
                                print(f"   🎉 [Pass] {mode} 모드 확인됨 (iRAS: {detected_status})")
                            else: 
                                print(f"   ⚠️ [Check] 값 불일치? (Expected: {expected_text}, Actual: {detected_status})")
                        else: 
                            print("   ❌ [Fail] iRAS에서 SSL 정보를 읽어오지 못함")
                    else: 
                        print(f"   ❌ [Fail] API 설정 실패 ({mode})")
                        
            except Exception as e: 
                print(f"   🔥 SSL 테스트 오류: {e}")
            
            finally:
                print("\n   🧹 [Teardown] SSL 비활성화 (복구)")
                # [수정] HTTPS로 바꾸지 않고, 기존 HTTP 연결 그대로 사용하여 복구 시도
                try:
                    # API로 SSL 끄기 요청
                    if api.set_ssl(enable=False): 
                        print("   ✅ SSL 비활성화 성공")
                    else: 
                        print("   ❌ SSL 비활성화 실패 (API 응답 확인 필요)")
                except Exception as e:
                    print(f"   🔥 복구 중 통신 에러: {e}")
        
        print("\n✅ 모든 네트워크 테스트 완료.")
        return True, "네트워크 및 iRAS 테스트 완료"

    except Exception as e:
        print(f"\n🔥 네트워크 테스트 중 오류: {e}")
        return False, str(e)
    
if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    parser = argparse.ArgumentParser(description='Network Integration Test')
    parser.add_argument('--ip', type=str, default="10.0.131.104", help='Target Camera IP')
    parser.add_argument('--id', type=str, default="admin", help='Camera ID')
    parser.add_argument('--pw', type=str, default="qwerty0-", help='Camera Password')
    parser.add_argument('--iface', type=str, default="이더넷", help='Network Interface Name')
    args = parser.parse_args()

    success = False
    try:
        success, msg = run_integrated_network_test(camera_ip=args.ip, camera_id=args.id, camera_pw=args.pw, interface_name=args.iface)
        if success: print(f"\n✅ 테스트 성공: {msg}")
        else: print(f"\n❌ 테스트 실패: {msg}")
    except Exception as e:
        print(f"\n🔥 [Critical Error] 실행 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "="*60)
        input("🛑 [종료 방지] 로그를 확인하세요. 엔터(Enter) 키를 누르면 창이 닫힙니다...")
        if success: sys.exit(0)
        else: sys.exit(1)
        

