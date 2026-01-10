import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
import re

# ▼ 셀레니움 라이브러리 (학사일정용) ▼
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ▼ 설정 ▼
CALENDAR_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
MENU_URL = "https://www.kw.ac.kr/ko/life/facility11.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# ★★★ [테스트 설정] ★★★
# True로 설정하면 2025-12-09 기준으로 가짜 HTML을 파싱합니다.
# 테스트가 끝나면 False로 바꿔주세요.
TEST_MODE = True 

# 제공해주신 HTML 파일의 핵심 내용 (테스트용 데이터)
TEST_HTML = """
<div class="table-scroll-box">
    <table class="tbl-list w100">
        <thead>
            <tr>
                <th scope="col">구분</th>
                <th scope="col"><span class="nowDay">월요일</span><br><span class="nowDate">2025-12-08</span></th>
                <th scope="col"><span class="nowDay">화요일</span><br><span class="nowDate">2025-12-09</span></th>
                <th scope="col"><span class="nowDay">수요일</span><br><span class="nowDate">2025-12-10</span></th>
                <th scope="col"><span class="nowDay">목요일</span><br><span class="nowDate">2025-12-11</span></th>
                <th scope="col"><span class="nowDay">금요일</span><br><span class="nowDate">2025-12-12</span></th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>
                    <strong class="dietTitle">광운대 함지마루천원의 아침</strong>
                    <br><span class="dietTime">8:30 ~ 9:30</span>
                </td>
                <td class="vt al"><pre>잡곡밥\n얼큰순대국</pre></td>
                <td class="vt al"><pre>잡곡밥\n사골우거지탕\n미트볼홍피망조림\n연두부&오리엔탈\n배추김치</pre></td>
                <td class="vt al"><pre>잡곡밥\n떡손만둣국</pre></td>
                <td class="vt al"><pre>비엔나카레라이스덮밥</pre></td>
                <td class="vt al"><pre>백미밥\n두부햄김치찌개</pre></td>
            </tr>
            <tr>
                <td>
                    <strong class="dietTitle">함지마루 자율한식 식단</strong>
                    <br><span class="dietTime">11:30 ~ 14:00</span>
                </td>
                <td class="vt al"><pre>잡곡밥\n아욱국</pre></td>
                <td class="vt al"><pre>잡곡밥\n유부팽이장국\n순살돈까스&브라운s\n로제파스타\n열무쌈장무침\n배추김치\n그린샐러드&드레싱</pre></td>
                <td class="vt al"><pre>잡곡밥\n얼큰소고기무국</pre></td>
                <td class="vt al"><pre>햄야채볶음밥</pre></td>
                <td class="vt al"><pre>백미밥\n쑥갓꼬치어묵우동</pre></td>
            </tr>
        </tbody>
    </table>
</div>
"""

def send_telegram(message):
    if TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            requests.post(url, data=payload)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def get_cafeteria_menu():
    try:
        # [테스트 모드 분기]
        if TEST_MODE:
            print(f"🧪 [테스트 모드] 2025-12-09 기준 가상 데이터 파싱 중...")
            soup = BeautifulSoup(TEST_HTML, 'html.parser')
            target_date = "2025-12-09" # 화요일
        else:
            print(f"🍚 학식 정보 가져오는 중... ({MENU_URL})")
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(MENU_URL, headers=headers, verify=False, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            target_date = date.today().strftime("%Y-%m-%d")
        
        # 1. 날짜 컬럼 인덱스 찾기
        table = soup.select_one("table.tbl-list")
        if not table:
            return "❌ 식단표를 찾을 수 없습니다."

        headers = table.select("thead th")
        target_idx = -1
        
        for idx, th in enumerate(headers):
            if target_date in th.get_text():
                target_idx = idx
                break
        
        if target_idx == -1:
            return f"😴 {target_date} 식단 정보가 없습니다. (주말/공휴일)"

        # 2. 메뉴 데이터 추출
        menu_rows = table.select("tbody tr")
        menu_list = []
        
        for row in menu_rows:
            cols = row.select("td")
            if len(cols) <= target_idx: continue
            
            # 메뉴명 (strong 태그나 텍스트)
            # '천원의 아침' 등을 추출
            title_cell = cols[0]
            # 판매시간 등 불필요한 텍스트 제거를 위해 strong 태그만 가져오거나 첫 줄만 가져옴
            menu_title = title_cell.get_text(" ", strip=True).split("판매시간")[0].strip()
            
            # 메뉴 내용 (pre 태그 안의 텍스트)
            menu_content = cols[target_idx].get_text("\n", strip=True)
            
            if menu_content:
                menu_list.append(f"🍱 *{menu_title}*\n{menu_content}")

        if not menu_list:
            return "🍙 등록된 식단 내용이 없습니다."
            
        return "\n\n".join(menu_list)

    except Exception as e:
        print(f"❌ 학식 파싱 에러: {e}")
        return "⚠️ 식단 정보를 불러오는데 실패했습니다."

def get_academic_calendar():
    # 테스트 중에는 학사일정은 간단히 스킵하거나 빈 값 리턴 (속도 위해)
    if TEST_MODE:
        return "(테스트 중: 학사일정 생략)"

    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    events_text = []
    
    try:
        print(f"📅 학사일정 접속 중...")
        driver.get(CALENDAR_URL)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
        except: pass
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        list_items = soup.select(".schedule-this-yearlist li")
        today = date.today()
        
        # ... (기존 학사일정 로직 동일) ...
        # 여기서는 생략, 원본 코드 유지하면 됩니다.
        
    except Exception as e:
        print(f"❌ 학사일정 에러: {e}")
        events_text.append("(학사일정 로딩 실패)")
    finally:
        driver.quit()
        
    return "\n\n".join(events_text) if events_text else "• 예정된 주요 학사일정이 없습니다."

def run():
    print("🚀 모닝 브리핑 시작 (TEST MODE: " + str(TEST_MODE) + ")")
    
    if TEST_MODE:
        today_str = "2025-12-09 (화)"
    else:
        today_str = date.today().strftime('%Y-%m-%d (%a)')
    
    # 1. 학사일정
    calendar_msg = get_academic_calendar()
    
    # 2. 학식 정보
    menu_msg = get_cafeteria_menu()
    
    # 3. 메시지 통합
    final_msg = f"☀️ *광운대 모닝 브리핑* ({today_str})\n\n" \
                f"{calendar_msg}\n\n" \
                f"────────────────\n\n" \
                f"🥄 *오늘의 학식*\n\n" \
                f"{menu_msg}\n\n" \
                f"[👉 전체 식단 보기]({MENU_URL})"
    
    print("📨 텔레그램 전송 중...")
    print(final_msg)
    send_telegram(final_msg)
    print("✅ 전송 완료")

if __name__ == "__main__":
    run()
