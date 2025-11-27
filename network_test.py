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
    def __init__(self, playwright_instance):
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
                time.sleep(2) # 확인 팝업 대기
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

# =========================================================
# 🚀 Main Execution Flow
# =========================================================
if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("🔒 관리자 권한으로 재실행합니다...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
        sys.exit()

    print("=== Network & Automation Test Started ===")
    
    target_ip = CFG["CAM_IP"]
    target_mac = None

    # # [Step 1] PC IP 고정 및 MAC 주소 획득
    # print("\n>>> [Step 1] Link-Local 활성화 준비")
    # NetworkManager.set_static_ip(CFG["PC_STATIC_IP"], CFG["PC_SUBNET"], CFG["PC_GW"])
    
    # if NetworkManager.ping(target_ip):
    #     with sync_playwright() as p:
    #         web = WebController(p)
    #         target_mac = web.get_mac_address(target_ip)
    #         if target_mac:
    #             web.set_link_local(target_ip, enable=True)
    #         web.close()
    # else:
    #     print("❌ 카메라 접속 실패. IP 설정을 확인하세요.")
    #     # sys.exit() 

    # if not target_mac:
    #     print("❌ MAC 주소 확보 실패로 테스트 중단")
    #     sys.exit()

    # # [Step 2] 169.254 대역 검증
    # print("\n>>> [Step 2] 169.254 Auto-IP 검증")
    # NetworkManager.set_static_ip(CFG["PC_AUTO_IP"], CFG["AUTO_SUBNET"])
    # NetworkManager.run_cmd("arp -d *")
    
    # auto_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_AUTO_NET"], timeout=40)
    
    # if auto_ip and "169.254" in auto_ip:
    #     print(f"🎉 Auto-IP 접속 성공: {auto_ip}")
    #     print("\n>>> [Step 3] 설정 복구 (Link-Local OFF & DHCP)")
    #     with sync_playwright() as p:
    #         web = WebController(p)
    #         web.set_link_local(auto_ip, enable=False)
    #         web.close()
    # else:
    #     print("⚠️ Auto-IP 탐색 실패 (DHCP 전환을 시도합니다)")

    # # [Step 3] 물리 테스트
    # input("\n🚨 [ACTION] 사내망 랜선을 뽑고, 카메라를 재부팅한 후 Enter를 누르세요 >> ")
    # NetworkManager.set_dhcp()
    # NetworkManager.run_cmd("arp -d *")
    
    # print(f"🔍 [Step 3] 물리적 Auto-IP 할당 확인 중...")
    # phy_auto_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_AUTO_NET"], timeout=60)
    
    # if phy_auto_ip and "169.254" in phy_auto_ip:
    #     print(f"🎉 [물리 테스트] Auto-IP 확인 성공: {phy_auto_ip}")
    # else:
    #     print("⚠️ [물리 테스트] Auto-IP 탐색 실패")

    # # [Step 4] PC 네트워크 복구 및 DHCP IP 탐색
    # input("\n🚨 [ACTION] 사내망 랜선을 다시 연결한 후 Enter를 누르세요 >> ")
    # print("\n>>> [Step 4] PC 네트워크 복구 및 DHCP IP 탐색")
    # NetworkManager.set_dhcp()
    
    # new_dhcp_ip = None
    # if NetworkManager.wait_for_dhcp("10."):
    #     NetworkManager.run_cmd("arp -d *")
        
    #     print(f"🔍 [Step 4] DHCP로 변경된 카메라 IP 탐색 중...")
    #     new_dhcp_ip = CameraScanner.find_ip_combined(target_mac, CFG["SCAN_NET"], timeout=60)
        
    #     if new_dhcp_ip and NetworkManager.ping(new_dhcp_ip):
    #         print(f"🎉 카메라 재접속 성공: {new_dhcp_ip}")
            
    #         # 1. FEN 설정 (Web)
    #         with sync_playwright() as p:
    #             web = WebController(p)
    #             web.set_fen_configuration(new_dhcp_ip)
    #             web.close()
            
    #         # 2. API 검증
    #         api = CameraApi(new_dhcp_ip, CFG["PORT"], CFG["ID"], CFG["PW"])
    #         api.verify_fen_setting(CFG["FEN_SVR"])

    #         # 3. iRAS 자동화 (Step 5)
    #         print("\n>>> [Step 5] iRAS 연동 테스트 (DirectExternal)")
    #         target_dev_name = CFG["IRAS_DEV_NAME"]
            
    #         if iRAS_test.run_fen_setup_process(target_dev_name, CFG["FEN_NAME"]):
    #             print("\n>>> [Step 6] iRAS 연결 모드 검증")
    #             time.sleep(5)
    #             if iRAS_test.run_fen_verification("TcpDirectExternal"):
    #                 print("\n🎉 [Pass] TcpDirectExternal 연결 확인됨")
    #             else:
    #                 print("\n⚠️ [Fail] 연결 모드 불일치")
    #     else:
    #         print("❌ 카메라 DHCP IP를 찾을 수 없습니다.")

    # # [Step 7] UPNP 테스트 (DirectInternal)
    # if new_dhcp_ip:
    #     input("\n🚨 [ACTION] 카메라와 PC를 공유기에 연결하고 Enter를 누르세요 (UPNP 테스트) >> ")
    #     print("\n>>> [Step 7] UPNP 활성화 및 DirectInternal 검증")
        
    #     # Web UPNP 켜기
    #     with sync_playwright() as p:
    #         web = WebController(p)
    #         web.set_upnp(new_dhcp_ip, enable=True)
    #         web.close()
        
    #     print("   -> UPNP 갱신 대기 (10초)...")
    #     time.sleep(10)
        
    #     if iRAS_test.run_fen_verification("TcpDirectInternal"):
    #          print("\n🎉 [Pass] TcpDirectInternal 연결 확인됨")
    #     else:
    #          print("\n⚠️ [Fail] UPNP 연결 모드 불일치")

    # # [Step 8] UDP Hole Punching 테스트 (추가됨)
    # if new_dhcp_ip:
    #     print("\n>>> [Step 8] UDP Hole Punching 테스트 준비")
    #     print("   -> 설정을 위해 카메라 사전 구성 중...")
        
    #     # 사전 설정: IP DHCP & UPNP OFF (Web)
    #     # 이미 DHCP 상태지만 확실하게 하고, UPNP를 끕니다.
    #     with sync_playwright() as p:
    #         web = WebController(p)
    #         web.set_upnp(new_dhcp_ip, enable=False) # UPNP OFF
    #         # web.set_link_local(new_dhcp_ip, enable=False) # DHCP 확인 (이미 되어있음)
    #         web.close()
            
    #     print("   ✅ 카메라 설정 완료 (DHCP, UPNP OFF)")
    #     input("\n🚨 [ACTION] PC를 회사망에 연결하고, 카메라는 공유기에 연결한 뒤 Enter를 누르세요 >> ")
        
    #     print("\n   -> UDP Hole Punching 연결 모드 검증 시도...")
    #     # 네트워크 환경이 바뀌었으므로 iRAS가 재접속할 시간을 충분히 줍니다.
    #     time.sleep(15) 
        
    #     if iRAS_test.run_fen_verification("UdpHolePunching"):
    #          print("\n🎉 [Pass] UdpHolePunching 연결 확인됨")
    #     else:
    #          print("\n⚠️ [Fail] UDP Hole Punching 연결 실패")
    
    # # [Step 9] FEN Relay 테스트 (추가됨!)
    # if new_dhcp_ip:
    #     print("\n>>> [Step 9] FEN Relay 테스트 (UDP Block)")
    #     print("   ℹ️  현재 물리 연결 상태(PC=회사망, Cam=공유기)를 유지하세요.")
    #     print("   ⚠️ [ACTION] 공유기 설정에서 'UDP Block'을 설정하세요.")
    #     print("      - 조건: [내부<->외부], 포트 [1~15199, 15201~65535] 차단")
    #     print("      - 참고: 카메라 설정은 이미 DHCP, UPNP OFF 상태입니다.")
        
    #     input("\n   설정이 완료되면 Enter를 누르세요 >> ")
        
    #     print("\n   -> Relay 모드 전환 대기 (약 30초)...")
    #     time.sleep(30) 
        
    #     # 검증: "Relay" 문자열이 포함되어 있는지 확인
    #     if iRAS_test.run_fen_verification("Relay"):
    #          print("\n🎉 [Pass] FEN Relay 연결 확인됨")
    #     else:
    #          print("\n⚠️ [Fail] Relay 연결 실패 (공유기 설정 확인 필요)")

    # [Step 10] WebGuard 테스트 (수정됨)
    if new_dhcp_ip:
        print("\n>>> [Step 10] WebGuard 접속 및 로그인 테스트")
        fen_url = f"http://{CFG['FEN_SVR']}/{CFG['FEN_NAME']}" # 예: http://qa1.idis.co.kr/FEN테스트
        print(f"   -> 브라우저 실행: {fen_url}")
        
        with sync_playwright() as p:
            # 1. 브라우저로 접속 시도 (WebGuard 실행 유도)
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            try:
                # WebGuard가 실행되도록 페이지 접속
                # (실제로는 프로토콜 핸들러 등으로 exe가 뜰 것임)
                page.goto(fen_url)
                print("   -> 페이지 로드 완료, WebGuard 실행 대기...")
                time.sleep(5) # exe 실행 시간 대기
                
                # 2. WebGuard 로그인 자동화 (별도 모듈 사용)
                if webgaurd.run_login(CFG["ID"], CFG["PW"]):
                    print("🎉 [Pass] WebGuard 로그인 성공")
                else:
                    print("⚠️ [Fail] WebGuard 로그인 실패")
                    
            except Exception as e:
                print(f"   🔥 브라우저 오류: {e}")
            finally:
                browser.close()

    input("\n✅ 모든 테스트 완료. 종료하려면 Enter...")