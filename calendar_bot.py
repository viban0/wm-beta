import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime, timedelta
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
# 이 날짜를 '오늘'이라고 가정합니다.
TEST_DATE = date(2026, 2, 20) 

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
    # 학사일정 테스트에 집중하기 위해 식단은 간단히 처리
    return "😴 (학사일정 테스트 중이라 식단 정보는 생략합니다)"

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
        print(f"📅 학사일정 접속 중... (기준일: {TEST_DATE})")
        driver.get(CALENDAR_URL)
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
        except:
            pass 

        time.sleep(1) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 태그 구조로 찾기 (strong=날짜, p=제목)
        # 페이지 내의 모든 li를 뒤져서 날짜/제목 있는 것만 추출 (무차별 탐색)
        all_list_items = soup.find_all("li")
        
        today = TEST_DATE # ★ 테스트 날짜 적용 ★
        
        today_events = []
        upcoming_events = []
        
        print(f"🔍 전체 리스트 아이템 {len(all_list_items)}개 분석 시작...")

        for item in all_list_items:
            date_tag = item.find("strong")
            title_tag = item.find("p")
            
            if not date_tag or not title_tag: continue
            
            raw_date = date_tag.get_text(strip=True)
            title = title_tag.get_text(strip=True)
            
            # 날짜 파싱 (02.02 ~ 02.27)
            dates = re.findall(r'(\d{2}\.\d{2})', raw_date)
            if not dates: continue
            
            current_year = today.year
            try:
                # 시작일
                s_date = datetime.strptime(f"{current_year}.{dates[0]}", "%Y.%m.%d").date()
                
                # 종료일 (없으면 시작일과 동일)
                if len(dates) > 1:
                    e_date = datetime.strptime(f"{current_year}.{dates[1]}", "%Y.%m.%d").date()
                else:
                    e_date = s_date
            except:
                continue

            # [디버깅용 로그] - 실제 봇에서는 제거 가능
            # if s_date.month == 2:
            #     print(f"  - 확인됨: {raw_date} : {title}")

            # 1. 오늘의 일정 (오늘이 기간 내에 포함되면)
            if s_date <= today <= e_date:
                today_events.append(f"• {title}")
            
            # 2. 다가오는 일정 (오늘 이후 시작되는 것)
            elif s_date > today:
                d_day = (s_date - today).days
                # 너무 먼 일정은 제외 (예: 14일 이내)
                if d_day <= 14: 
                    upcoming_events.append({
                        "date": raw_date,
                        "title": title,
                        "d_day": d_day
                    })

        # 메시지 조립
        if today_events:
            events_text.append(f"🔔 *오늘의 일정*\n" + "\n".join(today_events))
        else:
            events_text.append(f"🔔 *오늘의 일정*\n(일정이 없습니다)")
        
        if upcoming_events:
            upcoming_events.sort(key=lambda x: x['d_day'])
            top_events = upcoming_events[:5] # 최대 5개까지
            
            temp = ["\n⏳ *다가오는 일정*"]
            for e in top_events:
                d_day_str = "D-DAY" if e['d_day'] == 0 else f"D-{e['d_day']}"
                temp.append(f"[{d_day_str}] {e['title']} ({e['date']})")
            events_text.append("\n".join(temp))
            
    except Exception as e:
        print(f"❌ 학사일정 에러: {e}")
        events_text.append("(학사일정 로딩 실패)")
    finally:
        driver.quit()
        
    return "\n".join(events_text) if events_text else "• 예정된 주요 학사일정이 없습니다."

def run():
    print(f"🚀 모닝 브리핑 테스트 시작 (가상 기준일: {TEST_DATE})")
    
    today_str = TEST_DATE.strftime('%Y-%m-%d (%a)')
    
    # 1. 학사일정 가져오기 (실시간 크롤링 + 가짜 날짜 적용)
    calendar_msg = get_academic_calendar()
    
    # 2. 학식 정보 (생략)
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
