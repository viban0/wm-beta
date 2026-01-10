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

# -----------------------------------------------------------
# [기능 1] 텔레그램 전송
# -----------------------------------------------------------
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

# -----------------------------------------------------------
# [기능 2] 학식 식단 가져오기 (Requests 사용)
# -----------------------------------------------------------
def get_cafeteria_menu():
    try:
        print(f"🍚 학식 정보 가져오는 중... ({MENU_URL})")
        
        # 학식 페이지는 정적 페이지라 requests로 충분합니다 (속도 빠름)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(MENU_URL, headers=headers, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        today_str = date.today().strftime("%Y-%m-%d")
        # today_str = "2025-12-08" # 테스트용 날짜 (HTML 파일 기준)
        
        # 1. 오늘 날짜에 해당하는 '요일 컬럼 인덱스' 찾기
        table = soup.select_one("table.tbl-list")
        if not table:
            return "❌ 식단표를 찾을 수 없습니다."

        headers = table.select("thead th")
        target_idx = -1
        
        # 헤더: [구분, 월, 화, 수, 목, 금] 순서
        for idx, th in enumerate(headers):
            # 헤더 안의 날짜(span.nowDate)가 오늘과 같은지 확인
            if today_str in th.get_text():
                target_idx = idx
                break
        
        if target_idx == -1:
            return "😴 오늘은 운영하지 않거나 식단 정보가 없어요. (주말/공휴일)"

        # 2. 해당 요일의 메뉴 가져오기
        menu_rows = table.select("tbody tr")
        menu_list = []
        
        for row in menu_rows:
            cols = row.select("td")
            if len(cols) <= target_idx: continue
            
            # 메뉴 이름 (예: 천원의 아침, 함지마루 자율한식)
            # 보통 첫 번째 td에 제목이 있음. strong 태그 등 제거하고 텍스트만 깔끔하게
            category = cols[0].get_text(" ", strip=True).split("판매시간")[0].strip()
            
            # 오늘 요일의 메뉴 내용
            menu_content = cols[target_idx].get_text("\n", strip=True)
            
            if menu_content:
                menu_list.append(f"🍱 *{category}*\n{menu_content}")

        if not menu_list:
            return "🍙 등록된 식단 내용이 없습니다."
            
        return "\n\n".join(menu_list)

    except Exception as e:
        print(f"❌ 학식 파싱 에러: {e}")
        return "⚠️ 식단 정보를 불러오는데 실패했습니다."

# -----------------------------------------------------------
# [기능 3] 학사일정 가져오기 (Selenium 사용)
# -----------------------------------------------------------
def get_academic_calendar():
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
        
        # 데이터 로딩 대기
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
        except:
            pass # 로딩 실패해도 계속 진행 (빈 리스트 처리)

        time.sleep(1) # 안전 대기
        
        # HTML 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 태그 구조로 찾기 (strong=날짜, p=제목)
        list_items = soup.select(".schedule-this-yearlist li")
        
        today = date.today()
        # today = date(2026, 2, 20) # 테스트용

        today_events = []
        upcoming_events = []
        
        for item in list_items:
            date_tag = item.select_one("strong")
            title_tag = item.select_one("p")
            
            if not date_tag or not title_tag: continue
            
            raw_date = date_tag.get_text(strip=True)
            title = title_tag.get_text(strip=True)
            
            # 날짜 파싱 (02.02 ~ 02.27)
            dates = re.findall(r'(\d{2}\.\d{2})', raw_date)
            if not dates: continue
            
            current_year = today.year
            try:
                s_date = datetime.strptime(f"{current_year}.{dates[0]}", "%Y.%m.%d").date()
                e_date = datetime.strptime(f"{current_year}.{dates[1]}", "%Y.%m.%d").date() if len(dates) > 1 else s_date
            except:
                continue

            # 분류
            if s_date <= today <= e_date:
                today_events.append(f"• {title}")
            elif s_date > today:
                d_day = (s_date - today).days
                if d_day <= 14: # 2주 이내 일정만
                    upcoming_events.append({
                        "date": raw_date,
                        "title": title,
                        "d_day": d_day
                    })

        # 메시지 조립
        if today_events:
            events_text.append(f"🔔 *오늘의 일정*\n" + "\n".join(today_events))
        
        if upcoming_events:
            upcoming_events.sort(key=lambda x: x['d_day'])
            top_events = upcoming_events[:3] # 최대 3개만
            temp = ["⏳ *다가오는 일정*"]
            for e in top_events:
                d_day_str = "D-DAY" if e['d_day'] == 0 else f"D-{e['d_day']}"
                temp.append(f"[{d_day_str}] {e['title']} ({e['date']})")
            events_text.append("\n".join(temp))
            
    except Exception as e:
        print(f"❌ 학사일정 에러: {e}")
        events_text.append("(학사일정 로딩 실패)")
    finally:
        driver.quit()
        
    return "\n\n".join(events_text) if events_text else "• 예정된 주요 학사일정이 없습니다."

# -----------------------------------------------------------
# [메인 실행]
# -----------------------------------------------------------
def run():
    print("🚀 모닝 브리핑 시작")
    
    today_str = date.today().strftime('%Y-%m-%d (%a)')
    
    # 1. 학사일정 가져오기
    calendar_msg = get_academic_calendar()
    
    # 2. 학식 정보 가져오기
    menu_msg = get_cafeteria_menu()
    
    # 3. 메시지 통합
    final_msg = f"☀️ *광운대 모닝 브리핑* ({today_str})\n\n" \
                f"{calendar_msg}\n\n" \
                f"────────────────\n\n" \
                f"🥄 *오늘의 학식*\n\n" \
                f"{menu_msg}\n\n" \
                f"[👉 전체 식단 보기]({MENU_URL})"
    
    print("📨 텔레그램 전송 중...")
    print(final_msg) # 로그 확인용
    send_telegram(final_msg)
    print("✅ 전송 완료")

if __name__ == "__main__":
    run()
