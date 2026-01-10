import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import date
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

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

def get_page_source_with_selenium():
    """
    가상 브라우저를 띄워 3초 대기 후 소스를 가져옵니다.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 화면 없이 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # 크롬 드라이버 자동 설치 및 실행
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        print(f"🌐 브라우저로 접속 시도: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        print("⏳ 페이지 로딩 대기 중 (3초)...")
        time.sleep(3) # 요청하신 3초 대기
        
        # (선택) 확실하게 연도별 리스트가 떴는지 확인하고 싶다면 더 기다릴 수도 있음
        # 하지만 일단 요청하신 대로 단순 대기만 수행
        
        page_source = driver.page_source
        print("✅ 페이지 소스 확보 완료")
        return page_source
    except Exception as e:
        print(f"❌ 브라우저 실행 중 오류: {e}")
        return None
    finally:
        driver.quit()

def parse_date_range(date_str, current_year):
    # 날짜 문자열 정리 (예: "02.02(월)" -> "02.02")
    clean_str = date_str
    for char in "월화수목금토일() ":
        clean_str = clean_str.replace(char, "")
    
    parts = clean_str.split("~")
    try:
        start_md = parts[0].strip().split(".")
        start_date = date(current_year, int(start_md[0]), int(start_md[1]))
        
        if len(parts) > 1 and parts[1].strip():
            end_md = parts[1].strip().split(".")
            end_date = date(current_year, int(end_md[0]), int(end_md[1]))
        else:
            end_date = start_date
        return start_date, end_date
    except:
        return None, None

def run():
    try:
        # 1. 셀레니움으로 HTML 가져오기
        html = get_page_source_with_selenium()
        if not html:
            print("HTML을 가져오지 못해 종료합니다.")
            exit(1)

        soup = BeautifulSoup(html, 'html.parser')
        
        # 2. 사진 속 구조대로 타겟팅
        # JS가 로딩된 후라면 이 클래스가 존재할 확률이 높음
        items = soup.select("div.schedule-list-box.schedule-this-yearlist ul li")
        
        print(f"🔍 발견된 일정 항목 수: {len(items)}개")
        
        # 만약 여전히 못 찾으면 넓게 검색 (보험용)
        if len(items) == 0:
            print("⚠️ 특정 클래스 검색 실패, 일반 리스트 검색 시도...")
            items = soup.select("div.schedule-list-box ul li")

        today = date.today()
        # today = date(2026, 2, 20) # 테스트용
        
        today_events = []
        upcoming_events = []

        for item in items:
            date_tag = item.select_one("strong")
            title_tag = item.select_one("p")

            if not date_tag or not title_tag:
                continue

            raw_date = date_tag.get_text(strip=True)
            title = title_tag.get_text(strip=True)
            
            start_date, end_date = parse_date_range(raw_date, today.year)
            if not start_date: continue

            # 오늘 일정
            if start_date <= today <= end_date:
                today_events.append(f"• {title}")
            # 다가오는 일정
            elif start_date > today:
                d_day = (start_date - today).days
                upcoming_events.append({
                    "date": raw_date,
                    "title": title,
                    "d_day": d_day,
                    "sort_date": start_date
                })

        # 정렬 및 추출
        upcoming_events.sort(key=lambda x: x["sort_date"])
        next_two = upcoming_events[:2]

        # 메시지 작성
        msg_lines = []
        msg_lines.append(f"📅 *오늘의 학사일정* ({today.strftime('%Y-%m-%d')})\n")
        
        if today_events:
            msg_lines.append("\n".join(today_events))
        else:
            msg_lines.append("• 오늘 예정된 학사일정이 없습니다.")
        
        msg_lines.append("\n🔜 *다가오는 일정*")
        
        if next_two:
            for event in next_two:
                d_day_str = "D-DAY" if event['d_day'] == 0 else f"D-{event['d_day']}"
                msg_lines.append(f"\n[{event['date']}] ({d_day_str})\n👉 {event['title']}")
        else:
             msg_lines.append("\n(예정된 일정이 없습니다)")

        msg_lines.append(f"\n[🔗 전체 일정 보기]({TARGET_URL})")

        final_msg = "\n".join(msg_lines)
        print(final_msg)
        send_telegram(final_msg)

    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
        exit(1)

if __name__ == "__main__":
    run()
