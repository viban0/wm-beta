import html
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import traceback
from zoneinfo import ZoneInfo
from bot_utils import create_session, send_telegram

# ▼ 설정 ▼
CALENDAR_API_URL = "https://www.kw.ac.kr/KWBoard/list5_detail.jsp"
CALENDAR_PAGE_URL = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"
MENU_URL = "https://www.kw.ac.kr/ko/life/facility11.jsp"
NOTICE_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
FEEDBACK_GROUP_URL = "https://t.me/+p-QVo1Z6e5AxNTdl"

def get_korea_today():
    """Return the current calendar date in Korea, independent of runner locale."""
    return datetime.now(ZoneInfo("Asia/Seoul")).date()

def get_day_kor(date_obj):
    """ 날짜 객체를 받아서 한국어 요일(월~일) 반환 """
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[date_obj.weekday()]

# -----------------------------------------------------------
# [기능 1] 학식 (Requests)
# -----------------------------------------------------------
def get_cafeteria_menu(session):
    try:
        # print(f"🍚 학식 정보 요청: {MENU_URL}") # 로그 줄임
        res = session.get(MENU_URL, timeout=10)
        res.raise_for_status()
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
        
        # [수정] 멘트 변경
        if target_idx == -1:
            return "😴 오늘은 운영하지 않아요."

        menu_rows = table.select("tbody tr")
        menu_list = []
        
        for row in menu_rows:
            cols = row.select("td")
            if len(cols) <= target_idx: continue
            
            category = cols[0].get_text("\n", strip=True).split("판매시간")[0].strip()
            menu_content = cols[target_idx].get_text("\n", strip=True)
            
            if menu_content:
                menu_list.append(f"<b>{html.escape(category)}</b>\n{html.escape(menu_content)}")

        return "\n\n".join(menu_list) if menu_list else "🍙 등록된 식단 내용이 없습니다."

    except Exception as e:
        return "⚠️ 식단 정보를 불러오는데 실패했습니다."

# -----------------------------------------------------------
# [기능 2] 학사일정 (API Reverse Engineering)
# -----------------------------------------------------------
def fetch_calendar_data(session, year, month):
    try:
        data = {'sy': str(year), 'sm': str(month)}
        res = session.post(CALENDAR_API_URL, data=data, timeout=10)
        res.raise_for_status()
        return res.text 
    except:
        return ""

def get_academic_calendar(session):
    today = get_korea_today()
    
    target_months = [
        (today.year, today.month),
        ((today.replace(day=1) + timedelta(days=32)).year, (today.replace(day=1) + timedelta(days=32)).month),
        ((today.replace(day=1) + timedelta(days=62)).year, (today.replace(day=1) + timedelta(days=62)).month)
    ]

    all_list_items = []
    for y, m in target_months:
        html_fragment = fetch_calendar_data(session, y, m)
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

        # 오늘의 일정
        if s_date <= today <= e_date:
            if s_date != e_date:
                end_str = e_date.strftime("%m.%d")
                end_day = get_day_kor(e_date)
                today_events.append(f"• {html.escape(title)} ~ {end_str}({end_day})")
            else:
                today_events.append(f"• {html.escape(title)}")
        
        # 다가오는 일정
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
        events_text.append("🔔 <b>오늘의 일정</b>\n" + "\n".join(today_events))
    else:
        # [수정] 멘트 변경 (부드럽게)
        events_text.append("🔔 <b>오늘의 일정</b>\n오늘은 예정된 일정이 없어요 🌿")
    
    if upcoming_events:
        upcoming_events.sort(key=lambda x: x['d_day'])
        min_d_day = upcoming_events[0]['d_day']
        nearest_events = [e for e in upcoming_events if e['d_day'] == min_d_day]
        
        temp = ["⏳ <b>다가오는 일정</b>"]
        for e in nearest_events:
            d_day_str = "D-DAY" if e['d_day'] == 0 else f"D-{e['d_day']}"
            # 괄호 제거된 상태 유지
            temp.append(f"<b>{d_day_str}</b>  {html.escape(e['title'])}\n{html.escape(e['date'])}")
        events_text.append("\n".join(temp))
        
    return "\n".join(events_text) if events_text else "• 예정된 주요 학사일정이 없습니다."

def run():
    try:
        session = create_session()
        today = get_korea_today()
        # [수정] 요일 한국어로 변경
        day_kor = get_day_kor(today)
        today_str = f"{today.strftime('%Y-%m-%d')} ({day_kor})"
        
        print(f"🚀 모닝 브리핑 실행 ({today_str})")
        
        calendar_msg = get_academic_calendar(session)
        menu_msg = get_cafeteria_menu(session)
        
        # [수정] 제목 변경 (광운대 삭제), 날씨 삭제
        final_msg = f"☀️ <b>광운대 데일리 브리핑</b>\n{today_str}\n\n" \
                    f"{calendar_msg}\n\n" \
                    f"━━━━━━━━━━━━━━━━\n" \
                    f"🥄 <b>오늘의 학식</b>\n\n" \
                    f"{menu_msg}"
        
        # [수정] 버튼 이름 변경 (피드백)
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📅 전체 학사일정", "url": CALENDAR_PAGE_URL},
                    {"text": "🍙 전체 식단표", "url": MENU_URL}
                ],
                [
                    {"text": "📢 전체 공지사항", "url": NOTICE_URL},
                    {"text": "🗣️ 피드백", "url": FEEDBACK_GROUP_URL}
                ]
            ]
        }

        # print(final_msg) # 로그 너무 길면 생략 가능
        print("📨 텔레그램 전송 중...")
        if send_telegram(session, final_msg, buttons=keyboard):
            print("✅ 전송 완료")
        else:
            raise RuntimeError("Telegram did not accept the morning briefing")

    except Exception as e:
        error_msg = f"🔥 <b>모닝 브리핑 실행 오류</b>\n\n{html.escape(str(e))}"
        print(error_msg)
        send_telegram(create_session(), error_msg)
        print(traceback.format_exc())

if __name__ == "__main__":
    run()
