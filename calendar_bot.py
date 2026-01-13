import os
import requests
import json # [NEW] 버튼 처리를 위한 라이브러리
from bs4 import BeautifulSoup
from datetime import date, datetime, timedelta
import re
import traceback

# ▼ 설정 ▼
CALENDAR_API_URL = "https://www.kw.ac.kr/KWBoard/list5_detail.jsp"
CALENDAR_PAGE_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
MENU_URL = "https://www.kw.ac.kr/ko/life/facility11.jsp"
NOTICE_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
WEATHER_URL = "https://search.naver.com/search.naver?query=광운대학교+날씨"

# ★ [수정 필요] 여기에 운영 중인 텔레그램 그룹/채널 링크를 넣으세요!
FEEDBACK_GROUP_URL = "https://t.me/여기에_링크_입력"

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# [수정] 버튼(reply_markup)을 받을 수 있도록 업그레이드
def send_telegram(message, buttons=None):
    if TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            # 버튼이 있으면 payload에 추가
            if buttons:
                payload['reply_markup'] = json.dumps(buttons)
                
            requests.post(url, data=payload)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def get_korea_today():
    utc_now = datetime.utcnow()
    kst_now = utc_now + timedelta(hours=9)
    return kst_now.date()

def get_day_kor(date_obj):
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[date_obj.weekday()]

# -----------------------------------------------------------
# [기능 1] 날씨 (네이버 크롤링)
# -----------------------------------------------------------
def get_weather():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(WEATHER_URL, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        temp = soup.select_one("div.temperature_text > strong").get_text(strip=True).replace("현재 온도", "")
        status = soup.select_one("span.weather.before_slash").get_text(strip=True)
        rain_info = ""
        rain_rate = soup.select("dl.summary_list dd")
        if rain_rate:
            rain_info = f" (☔ {rain_rate[0].get_text(strip=True)})"
        return f"{status}, {temp}{rain_info}"
    except:
        return "날씨 정보 없음"

# -----------------------------------------------------------
# [기능 2] 학식 (Requests)
# -----------------------------------------------------------
def get_cafeteria_menu():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(MENU_URL, headers=headers, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        today_str = get_korea_today().strftime("%Y-%m-%d")
        table = soup.select_one("table.tbl-list")
        if not table: return "❌ 식단표 없음"
        headers = table.select("thead th")
        target_idx = -1
        for idx, th in enumerate(headers):
            if today_str in th.get_text():
                target_idx = idx
                break
        if target_idx == -1: return "😴 오늘은 운영하지 않거나 식단 정보가 없어요."
        menu_rows = table.select("tbody tr")
        menu_list = []
        for row in menu_rows:
            cols = row.select("td")
            if len(cols) <= target_idx: continue
            category = cols[0].get_text(" ", strip=True).split("판매시간")[0].strip()
            menu_content = cols[target_idx].get_text("\n", strip=True)
            if menu_content:
                menu_list.append(f"🍱 *{category}*\n{menu_content}")
        return "\n\n".join(menu_list) if menu_list else "🍙 등록된 식단 내용 없음"
    except:
        return "⚠️ 식단 로딩 실패"

# -----------------------------------------------------------
# [기능 3] 학사일정 (API Reverse Engineering)
# -----------------------------------------------------------
def fetch_calendar_data(year, month):
    try:
        data = {'sy': str(year), 'sm': str(month)}
        res = requests.post(CALENDAR_API_URL, data=data, verify=False, timeout=10)
        return res.text 
    except:
        return ""

def get_academic_calendar():
    today = get_korea_today()
    target_months = [
        (today.year, today.month),
        ((today.replace(day=1) + timedelta(days=32)).year, (today.replace(day=1) + timedelta(days=32)).month),
        ((today.replace(day=1) + timedelta(days=62)).year, (today.replace(day=1) + timedelta(days=62)).month)
    ]
    all_list_items = []
    for y, m in target_months:
        html = fetch_calendar_data(y, m)
        if html: all_list_items.extend(BeautifulSoup(html, 'html.parser').find_all("li"))

    today_events = []
    upcoming_events = []
    seen = set()

    for item in all_list_items:
        dt, tt = item.find("strong"), item.find("p")
        if not dt or not tt: continue
        r_d, t = dt.get_text(strip=True), tt.get_text(strip=True)
        if f"{r_d}_{t}" in seen: continue
        seen.add(f"{r_d}_{t}")
        
        dates = re.findall(r'(\d{2}\.\d{2})', r_d)
        if not dates: continue
        try:
            cy = today.year
            m = int(dates[0].split('.')[0])
            if today.month >= 11 and m <= 2: cy += 1
            elif today.month <= 2 and m >= 11: cy -= 1
            sd = datetime.strptime(f"{cy}.{dates[0]}", "%Y.%m.%d").date()
            ed = datetime.strptime(f"{cy}.{dates[1]}", "%Y.%m.%d").date() if len(dates) > 1 else sd
        except: continue

        if sd <= today <= ed:
            pd = f" ~ {ed.strftime('%m.%d')}({get_day_kor(ed)})" if sd != ed else ""
            today_events.append(f"• {t}{pd}")
        elif sd > today:
            d = (sd - today).days
            if d <= 50: upcoming_events.append({"d": r_d, "t": t, "dd": d})

    msg = []
    if today_events: msg.append(f"🔔 *오늘의 일정*\n" + "\n".join(today_events))
    else: msg.append(f"🔔 *오늘의 일정*\n(일정이 없습니다)")
    
    if upcoming_events:
        upcoming_events.sort(key=lambda x: x['dd'])
        min_d = upcoming_events[0]['dd']
        for e in [x for x in upcoming_events if x['dd'] == min_d]:
            msg.append(f"\n⏳ *다가오는 일정*\n[D-{e['dd']}] {e['t']} {e['d']}")
            
    return "\n".join(msg)

def run():
    try:
        today_str = get_korea_today().strftime('%Y-%m-%d (%a)')
        print(f"🚀 광운대 모닝 브리핑 실행 ({today_str})")
        
        weather_info = get_weather()
        calendar_msg = get_academic_calendar()
        menu_msg = get_cafeteria_menu()
        
        # 메시지 본문에서 [👉 전체 일정 보기] 등의 링크를 삭제했습니다.
        # 왜냐하면 아래 버튼으로 들어갈 거니까요!
        final_msg = f"☀️ *광운대 모닝 브리핑* {today_str}\n" \
                    f"🌡 {weather_info}\n\n" \
                    f"{calendar_msg}\n\n" \
                    f"────────────────\n\n" \
                    f"🥄 *오늘의 학식*\n\n" \
                    f"{menu_msg}"
        
        # ▼ 버튼 메뉴 설정 (가장 중요!) ▼
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📅 전체 학사일정", "url": CALENDAR_PAGE_URL},
                    {"text": "🍙 전체 식단표", "url": MENU_URL}
                ],
                [
                    {"text": "📢 학교 공지사항", "url": NOTICE_URL},
                    {"text": "💬 소통방 / 피드백", "url": FEEDBACK_GROUP_URL}
                ]
            ]
        }

        print("📨 텔레그램 전송 중...")
        send_telegram(final_msg, buttons=keyboard)
        print("✅ 전송 완료")

    except Exception as e:
        # 에러 리포팅 기능 유지
        error_msg = f"🔥 [비상] 봇 실행 중 오류 발생!\n\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    run()
