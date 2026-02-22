import os
import requests
from bs4 import BeautifulSoup
import html
import json

# ▼ 설정 ▼
TARGET_ACCOUNT = "kwu_studentcouncil"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(title, link, image_url):
    if not (TOKEN and CHAT_ID): return
    try:
        clean_title = html.escape(title[:200]) + "..." if len(title) > 200 else html.escape(title)
        caption = f"📸 <b>[총학생회 인스타 새글]</b>\n\n{clean_title}"
        
        # 이미지가 없으면 텍스트만, 있으면 사진 전송
        if image_url:
            url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
            payload = {
                "chat_id": CHAT_ID,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps({"inline_keyboard": [[{"text": "👉 원본 보기", "url": link}]]})
            }
        else:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                "chat_id": CHAT_ID,
                "text": caption + f"\n\n🔗 {link}",
                "parse_mode": "HTML"
            }
        requests.post(url, data=payload)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def run():
    # Imginn 사이트를 활용 (Picuki 403 우회용)
    print(f"🔍 Imginn을 통해 @{TARGET_ACCOUNT} 스캔 중...")
    url = f"https://imginn.com/{TARGET_ACCOUNT}/"
    
    # 봇 차단을 피하기 위한 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ 접속 실패 (응답 코드: {response.status_code})")
            return

        soup = BeautifulSoup(response.content, "html.parser")
        
        # Imginn 게시물 박스 찾기
        items = soup.select(".item")
        
        if not items:
            print("❌ 게시물을 찾을 수 없습니다. (구조 변경 가능성)")
            return

        current_posts = []
        for item in items[:5]:
            # 링크 및 ID
            link_tag = item.select_one("a")
            if not link_tag: continue
            link = "https://imginn.com" + link_tag.get("href")
            post_id = link.split("/")[-2] if link.endswith("/") else link.split("/")[-1]
            
            # 이미지
            img_tag = item.select_one("img")
            image_url = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
            
            # 제목 (Imginn은 alt 속성에 본문이 들어가는 경우가 많음)
            description = img_tag.get("alt") if img_tag else "새 게시물"

            current_posts.append({
                "id": post_id,
                "title": description,
                "link": link,
                "image": image_url
            })

        print(f"✅ {len(current_posts)}개의 게시물을 가져왔습니다.")

        # --- DB 비교 로직 ---
        DB_FILE = "insta_data.txt"
        old_posts = []
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines()]

        save_data = []
        for post in current_posts:
            save_data.append(post["id"])
            if old_posts and post["id"] not in old_posts:
                print(f"🚀 새 글 전송: {post['id']}")
                send_telegram(post['title'], post['link'], post['image'])

        with open(DB_FILE, "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")

    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    run()
