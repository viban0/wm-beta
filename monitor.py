import html
import re
from typing import Set
import requests
from bs4 import BeautifulSoup
from bot_utils import create_session, read_state, send_telegram, write_state

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
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

def notify_post(session: requests.Session, title: str, link: str, modified_at: str) -> bool:
    """텔레그램 봇으로 알림 메시지 및 인라인 버튼을 전송합니다."""
    icon = get_emoji(title)
    safe_title = html.escape(title)
    # The notification itself already conveys "new"; keep the title as the
    # first thing students see and avoid duplicating low-value metadata.
    modified_line = f"\n수정일 · {html.escape(modified_at)}" if modified_at else ""
    message = f"{icon} <b>{safe_title}</b>{modified_line}"
    return send_telegram(session, message, {
        "inline_keyboard": [[{"text": "공지 자세히 보기 →", "url": link}]]
    })


def get_modified_date(info_tag) -> str:
    """Extract only the updated date from the board metadata, when available."""
    if not info_tag:
        return ""

    text = " ".join(info_tag.stripped_strings)
    match = re.search(r"수정일\s*[:：]?\s*([^|]+?)(?=\s*(?:\||작성일|조회)|$)", text)
    return match.group(1).strip() if match else ""

def run() -> None:
    session = create_session()

    try:
        print(f"🌐 접속 시도: {TARGET_URL}")
        response = session.get(TARGET_URL, timeout=30)
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
                
                fingerprint = f"{clean_title}|{full_link}"

                current_new_posts.append({
                    "id": fingerprint,
                    "title": clean_title,
                    "link": full_link,
                    "modified_at": get_modified_date(info_tag),
                })

        # 이전 데이터 읽기 (Set을 활용하여 조회 속도 단축)
        old_posts: Set[str] = read_state("data.txt")

        is_first_run = not old_posts
        # Preserve a rolling history. This prevents a temporarily failed delivery
        # from disappearing when the site removes its "new" label.
        save_data = list(old_posts)

        for post in current_new_posts:
            if is_first_run:
                save_data.append(post["id"])
                continue

            if post["id"] not in old_posts:
                print(f"🚀 새 공지: {post['title']}")
                if notify_post(session, post['title'], post['link'], post['modified_at']):
                    save_data.append(post["id"])

        if is_first_run:
            print("🚀 첫 실행: 기준점 잡기 완료")

        # 파일 갱신
        write_state("data.txt", save_data[-250:])
        
        print("💾 data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        exit(1)

if __name__ == "__main__":
    run()
