import os
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime, timedelta
import re

# ▼ 설정 ▼
CALENDAR_API_URL = "https://www.kw.ac.kr/KWBoard/list5_detail.jsp"
CALENDAR_PAGE_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
MENU_URL = "https://www.kw.ac.kr/ko/life/facility11.jsp"

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# ★★★ [테스트 모드 설정] ★★★
# 이 날짜를 '오늘'로 가정하고 실행합니다.
TEST_DATE = date(2026, 2, 27) 

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

def get_day_kor(date_obj):
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[date_obj.weekday()]

# -----------------------------------------------------------
# [기능 1] 학식 식단 (테스트 중 생략)
# -----------------------------------------------------------
def get_cafeteria_menu():
    return "🚧 (2026-02-27 기준 테스트 중이라 식단 정보는 생략합니다)"

# -----------------------------------------------------------
# [기능 2] 학사일정 (API Reverse Engineering)
# -----------------------------------------------------------
def fetch_calendar_data(year, month):
    try:
        print(f"📅 API 요청: {year}년 {month}월")
        data = {'sy': str(year), 'sm': str(month)}
        res = requests.post(CALENDAR_API_URL, data=data, verify=False, timeout=10)
        return res.text 
    except Exception as e:
        print(f"❌ API 요청 실패: {e}")
        return ""

def get_academic_calendar():
    # [테스트] 오늘 날짜를 강제로 설정
    today = TEST_DATE
    
    target_months = []
    # 이번 달 (2월)
    target_months.append((today.year, today.month))
    # 다음 달 (3월)
    next_month_date = today.replace(day=1) + timedelta(days=32)
    target_months.append((next_month_date.year, next_month_date.month))
    # 다다음 달 (4월)
    next_next_month_date = next_month_date.replace(day=1) + timedelta(days=32)
    target_months.append((next_next_month_date.year, next_next_month_date.month))

    all_list_items = []
    
    for y, m in target_months:
        html_fragment = fetch_calendar_data(y, m)
        if html_fragment:
            soup = BeautifulSoup(html_fragment, 'html.parser')
            items = soup.find_all("li")
            all_list_items.extend(items)

    today_events = []
    upcoming_events = []
    seen_events = set() 

    for item in all_list_items:
        date_tag = item.find("strong")
        title_tag = item.find("p")
        
        if not date_tag or not title_tag: continue
        
        raw_date = date_tag.get_text(strip=True)
        title = title_tag.get_text(strip=True)
        
        unique_key = f"{raw_date}_{title}"
        if unique_key in seen_events: continue
        seen_events.add(unique_key)
        
        dates = re.findall(r'(\d{2}\.\d{2})', raw_date)
        if not dates: continue
        
        current_year = today.year 
        
        try:
            msg_s_mon = int(dates[0].split('.')[0])
            calc_year = current_year
            
            # 연도 보정 (현재 11~12월인데 일정은 1~2월인 경우 등)
            if today.month >= 11 and msg_s_mon <= 2:
                calc_year += 1
            elif today.month <= 2 and msg_s_mon >= 11:
                calc_year -= 1
            
            s_date = datetime.strptime(f"{calc_year}.{dates[0]}", "%Y.%m.%d").date()
            if len(dates) > 1:
                e_date = datetime.strptime(f"{calc_year}.{dates[1]}", "%Y.%m.%d").date()
            else:
                e_date = s_date
        except:
            continue

        # 1. 오늘의 일정
        if s_date <= today <= e_date:
            if s_date != e_date:
                end_str = e_date.strftime("%m.%d")
                end_day = get_day_kor(e_date)
                # [확인] ~ 02.27(금) 형식 (괄호 제거됨)
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

    events_text = []
    
    if today_events:
        events_text.append(f"🔔 *오늘의 일정*\n" + "\n".join(today_events))
    else:
        events_text.append(f"🔔 *오늘의 일정*\n(일정이 없습니다)")
    
    if upcoming_events:
        upcoming_events.sort(key=lambda x: x['d_day'])
        min_d_day = upcoming_events[0]['d_day']
        nearest_events = [e for e in upcoming_events if e['d_day'] == min_d_day]
        
        temp = ["\n⏳ *다가오는 일정*"]
        for e in nearest_events:
            d_day_str = "D-DAY" if e['d_day'] == 0 else f"D-{e['d_day']}"
            # [확인] 03.02(월) 형식 (괄호 제거됨)
            temp.append(f"[{d_day_str}] {e['title']} {e['date']}")
        events_text.append("\n".join(temp))
        
    return "\n".join(events_text) if events_text else "• 예정된 주요 학사일정이 없습니다."

def run():
    print(f"🚀 광운대 모닝 브리핑 실행 (TEST DATE: {TEST_DATE})")
    
    today_str = TEST_DATE.strftime('%Y-%m-%d (%a)')
    
    calendar_msg = get_academic_calendar()
    menu_msg = get_cafeteria_menu()
    
    final_msg = f"☀️ *광운대 모닝 브리핑* {today_str}\n\n" \
                f"{calendar_msg}\n\n" \
                f"[👉 전체 일정 보기]({CALENDAR_PAGE_URL})\n" \
                f"────────────────\n\n" \
                f"🥄 *오늘의 학식*\n\n" \
                f"{menu_msg}\n\n" \
                f"[👉 전체 식단 보기]({MENU_URL})"
    
    print(final_msg)
    send_telegram(final_msg)

if __name__ == "__main__":
    run()
