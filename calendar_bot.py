import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime, timedelta
import re

# ▼ 셀레니움 라이브러리 ▼
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

# ▼▼▼ [핵심 수정] 한국 시간 구하는 함수 추가 ▼▼▼
def get_korea_today():
    """서버 시간(UTC)에 9시간을 더해 한국 날짜를 반환"""
    utc_now = datetime.utcnow()
    kst_now = utc_now + timedelta(hours=9)
    return kst_now.date()

def get_day_kor(date_obj):
    """ 날짜 객체를 받아서 한국어 요일(월~일) 반환 """
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[date_obj.weekday()]

# -----------------------------------------------------------
# [기능 1] 학식 식단 가져오기
# -----------------------------------------------------------
def get_cafeteria_menu():
    try:
        print(f"🍚 학식 정보 가져오는 중... ({MENU_URL})")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(MENU_URL, headers=headers, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # [수정] 한국 시간 기준 오늘 날짜 사용
        today_str = get_korea_today().strftime("%Y-%m-%d")
        
        # 1. 오늘 날짜에 해당하는 '요일 컬럼 인덱스' 찾기
        table = soup.select_one("table.tbl-list")
        if not table:
            return "❌ 식단표를 찾을 수 없습니다."

        headers = table.select("thead th")
        target_idx = -1
        
        for idx, th in enumerate(headers):
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
            
            category = cols[0].get_text(" ", strip=True).split("판매시간")[0].strip()
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
# [기능 2] 학사일정 가져오기
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
        # [수정] 한국 시간 기준 오늘 날짜 사용
        today = get_korea_today()
        print(f"📅 학사일정 접속 중... (기준일: {today})")
        
        driver.get(CALENDAR_URL)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
        except:
            pass 

        time.sleep(1) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_list_items = soup.find_all("li")
        
        today_events = []
        upcoming_events = []
        
        for item in all_list_items:
            date_tag = item.find("strong")
            title_tag = item.find("p")
            
            if not date_tag or not title_tag: continue
            
            raw_date = date_tag.get_text(strip=True)
            title = title_tag.get_text(strip=True)
            
            dates = re.findall(r'(\d{2}\.\d{2})', raw_date)
            if not dates: continue
            
            current_year = today.year
            try:
                s_date = datetime.strptime(f"{current_year}.{dates[0]}", "%Y.%m.%d").date()
                if len(dates) > 1:
                    e_date = datetime.strptime(f"{current_year}.{dates[1]}", "%Y.%m.%d").date()
                else:
                    e_date = s_date
            except:
                continue

            # 1. 오늘의 일정
            if s_date <= today <= e_date:
                if s_date != e_date:
                    end_str = e_date.strftime("%m.%d")
                    end_day = get_day_kor(e_date)
                    today_events.append(f"• {title} ~ {end_str}({end_day})")
                else:
                    today_events.append(f"• {title}")
            
            # 2. 다가오는 일정
            elif s_date > today:
                d_day = (s_date - today).days
                # [유지] 방학 기간 고려해서 50일로 넉넉하게
                if d_day <= 50: 
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
        
        # 다가오는 일정 (가장 가까운 것만)
        if upcoming_events:
            upcoming_events.sort(key=lambda x: x['d_day'])
            min_d_day = upcoming_events[0]['d_day']
            
            nearest_events = [e for e in upcoming_events if e['d_day'] == min_d_day]
            
            temp = ["\n⏳ *다가오는 일정*"]
            for e in nearest_events:
                d_day_str = "D-DAY" if e['d_day'] == 0 else f"D-{e['d_day']}"
                temp.append(f"[{d_day_str}] {e['title']} {e['date']}")
            events_text.append("\n".join(temp))
            
    except Exception as e:
        print(f"❌ 학사일정 에러: {e}")
        events_text.append("(학사일정 로딩 실패)")
    finally:
        driver.quit()
        
    return "\n".join(events_text) if events_text else "• 예정된 주요 학사일정이 없습니다."

def run():
    print("🚀 광운대 모닝 브리핑 실행 (한국 시간 적용)")
    
    # [수정] 한국 시간 기준 오늘 날짜 문자열
    today_str = get_korea_today().strftime('%Y-%m-%d (%a)')
    
    calendar_msg = get_academic_calendar()
    menu_msg = get_cafeteria_menu()
    
    final_msg = f"☀️ *광운대 모닝 브리핑* {today_str}\n\n" \
                f"{calendar_msg}\n\n" \
                f"[👉 전체 일정 보기]({CALENDAR_URL})\n" \
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
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def get_day_kor(date_obj):
    """ 날짜 객체를 받아서 한국어 요일(월~일) 반환 """
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[date_obj.weekday()]

# -----------------------------------------------------------
# [기능 1] 학식 식단 가져오기 (실전 모드 복구)
# -----------------------------------------------------------
def get_cafeteria_menu():
    try:
        print(f"🍚 학식 정보 가져오는 중... ({MENU_URL})")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(MENU_URL, headers=headers, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # [실전] 진짜 오늘 날짜 사용
        today_str = date.today().strftime("%Y-%m-%d")
        
        # 1. 오늘 날짜에 해당하는 '요일 컬럼 인덱스' 찾기
        table = soup.select_one("table.tbl-list")
        if not table:
            return "❌ 식단표를 찾을 수 없습니다."

        headers = table.select("thead th")
        target_idx = -1
        
        for idx, th in enumerate(headers):
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
            
            category = cols[0].get_text(" ", strip=True).split("판매시간")[0].strip()
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
# [기능 2] 학사일정 가져오기 (실전 모드)
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
        # [실전] 진짜 오늘 날짜 사용
        today = date.today()
        print(f"📅 학사일정 접속 중... (기준일: {today})")
        
        driver.get(CALENDAR_URL)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".schedule-this-yearlist li"))
            )
        except:
            pass 

        time.sleep(1) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_list_items = soup.find_all("li")
        
        today_events = []
        upcoming_events = []
        
        for item in all_list_items:
            date_tag = item.find("strong")
            title_tag = item.find("p")
            
            if not date_tag or not title_tag: continue
            
            raw_date = date_tag.get_text(strip=True)
            title = title_tag.get_text(strip=True)
            
            dates = re.findall(r'(\d{2}\.\d{2})', raw_date)
            if not dates: continue
            
            current_year = today.year
            try:
                s_date = datetime.strptime(f"{current_year}.{dates[0]}", "%Y.%m.%d").date()
                if len(dates) > 1:
                    e_date = datetime.strptime(f"{current_year}.{dates[1]}", "%Y.%m.%d").date()
                else:
                    e_date = s_date
            except:
                continue

            # 1. 오늘의 일정
            if s_date <= today <= e_date:
                if s_date != e_date:
                    end_str = e_date.strftime("%m.%d")
                    end_day = get_day_kor(e_date)
                    today_events.append(f"• {title} ~ {end_str}({end_day})")
                else:
                    today_events.append(f"• {title}")
            
            # 2. 다가오는 일정
            elif s_date > today:
                d_day = (s_date - today).days
                if d_day <= 50: 
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
        
        # 다가오는 일정 (가장 가까운 것만, 괄호 제거)
        if upcoming_events:
            upcoming_events.sort(key=lambda x: x['d_day'])
            min_d_day = upcoming_events[0]['d_day']
            
            nearest_events = [e for e in upcoming_events if e['d_day'] == min_d_day]
            
            temp = ["\n⏳ *다가오는 일정*"]
            for e in nearest_events:
                d_day_str = "D-DAY" if e['d_day'] == 0 else f"D-{e['d_day']}"
                # [수정] 괄호 제거: ({e['date']}) -> {e['date']}
                temp.append(f"[{d_day_str}] {e['title']} {e['date']}")
            events_text.append("\n".join(temp))
            
    except Exception as e:
        print(f"❌ 학사일정 에러: {e}")
        events_text.append("(학사일정 로딩 실패)")
    finally:
        driver.quit()
        
    return "\n".join(events_text) if events_text else "• 예정된 주요 학사일정이 없습니다."

def run():
    print("🚀 광운대 모닝 브리핑 실행 (실전 모드)")
    
    today_str = date.today().strftime('%Y-%m-%d (%a)')
    
    calendar_msg = get_academic_calendar()
    menu_msg = get_cafeteria_menu()
    
    final_msg = f"☀️ *모닝 브리핑* {today_str}\n\n" \
                f"{calendar_msg}\n\n" \
                f"[👉 전체 일정 보기]({CALENDAR_URL})\n" \
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
