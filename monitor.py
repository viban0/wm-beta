import html
import json
import os
from typing import Set
import requests
from bs4 import BeautifulSoup
import urllib3

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 키워드별 이모지 매핑 테이블
EMOJI_MAP = [
    (("장학", "대출"), "💰"),
    (("학사", "수업", "복학"), "📅"),
    (("행사", "축제", "특강"), "🎉"),
    (("모집", "인턴"), "👔"),
    (("국제", "교환"), "✈️"),
    (("봉사",), "❤️"),
    (("대회", "공모"), "🏆"),
]

def get_emoji(title: str) -> str:
    """제목의 키워드에 맞춰 카테고리 이모지를 반환합니다."""
    for keywords, emoji in EMOJI_MAP:
        if any(keyword in title for keyword in keywords):
            return emoji
    return "📢"

def send_telegram(session: requests.Session, title: str, link: str, info: str) -> None:
    """텔레그램 봇으로 알림 메시지 및 인라인 버튼을 전송합니다."""
    if not (TOKEN and CHAT_ID):
        return

    try:
        icon = get_emoji(title)
        safe_title = html.escape(title)
        safe_info = html.escape(info)
        
        msg = f"{icon} <b>{safe_title}</b>\n\n{safe_info}"
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

        keyboard = {
            "inline_keyboard": [
                [{"text": "👉 공지 내용 보러가기", "url": link}]
            ]
        }

        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        }

        response = session.post(url, data=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"⚠️ 텔레그램 전송 실패: {e}")

def parse_meta_info(info_tag) -> str:
    """게시글 태그에서 작성일 등 필요 메타 정보만 정제하여 반환합니다."""
    if not info_tag:
        return ""
        
    raw_text = info_tag.get_text("|", strip=True)
    parts = raw_text.split("|")
    clean_parts = []
    skip_next = False

    for part in parts:
        p = part.strip()
        if not p:
            continue
        if "수정일" in p:
            skip_next = True
            continue
        if skip_next:
            skip_next = not any(char.isdigit() for char in p)
            continue
        if "조회" in p:
            continue
        clean_parts.append(p)

    final_parts = []
    idx = 0
    while idx < len(clean_parts):
        current = clean_parts[idx]
        if "작성일" in current and idx + 1 < len(clean_parts):
            final_parts.append(f"{current} {clean_parts[idx+1]}")
            idx += 2
        else:
            final_parts.append(current)
            idx += 1

    return "| " + " | ".join(final_parts) if final_parts else ""

def run() -> None:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    })

    try:
        print(f"🌐 접속 시도: {TARGET_URL}")
        response = session.get(TARGET_URL, verify=False, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select(".board-list-box ul li")[:50]
        current_new_posts = []

        print(f"🔍 스캔 중... ({len(items)}개)")

        for item in items:
            if "신규게시글" not in item.get_text():
                continue

            a_tag = item.select_one("div.board-text > a")
            info_tag = item.select_one("p.info")

            # 필터링 조건 확인 (특정 부서/학생 그룹)
            if info_tag:
                info_text = info_tag.get_text()
                if "교수지원팀" in info_text or "국제학생" in info_text:
                    continue

            if a_tag:
                raw_title = " ".join(a_tag.get_text().split())
                clean_title = raw_title.replace("신규게시글", "").replace("Attachment", "").strip()

                # '채용' 키워드가 포함된 경우 필터링
                if "채용" in clean_title:
                    continue

                link = a_tag.get('href')
                full_link = f"https://www.kw.ac.kr{link}" if link else TARGET_URL
                
                meta_info = parse_meta_info(info_tag)
                fingerprint = f"{clean_title}|{full_link}"

                current_new_posts.append({
                    "id": fingerprint,
                    "title": clean_title,
                    "link": full_link,
                    "info": meta_info
                })

        # 이전 데이터 읽기 (Set을 활용하여 조회 속도 단축)
        old_posts: Set[str] = set()
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
                old_posts = {line.strip() for line in f if line.strip()}

        is_first_run = not old_posts
        save_data = []

        for post in current_new_posts:
            save_data.append(post["id"])

            if is_first_run:
                continue

            if post["id"] not in old_posts:
                print(f"🚀 새 공지: {post['title']}")
                send_telegram(session, post['title'], post['link'], post['info'])

        if is_first_run:
            print("🚀 첫 실행: 기준점 잡기 완료")

        # 파일 갱신
        with open("data.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(save_data) + ("\n" if save_data else ""))
        
        print("💾 data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        exit(1)

if __name__ == "__main__":
    run()
