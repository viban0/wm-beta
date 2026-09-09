import html
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

def notify_post(session: requests.Session, title: str, link: str, info: str) -> bool:
    """텔레그램 봇으로 알림 메시지 및 인라인 버튼을 전송합니다."""
    icon = get_emoji(title)
    safe_title = html.escape(title)
    safe_info = html.escape(info)
    detail = f"\n<blockquote>{safe_info.lstrip('| ').strip()}</blockquote>" if safe_info else ""
    message = f"{icon} <b>새 광운대 공지</b>\n\n{safe_title}{detail}"
    return send_telegram(session, message, {
        "inline_keyboard": [[{"text": "공지 자세히 보기 →", "url": link}]]
    })

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
                
                meta_info = parse_meta_info(info_tag)
                fingerprint = f"{clean_title}|{full_link}"

                current_new_posts.append({
                    "id": fingerprint,
                    "title": clean_title,
                    "link": full_link,
                    "info": meta_info
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
                if notify_post(session, post['title'], post['link'], post['info']):
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
