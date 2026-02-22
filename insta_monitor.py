import os
import requests
from bs4 import BeautifulSoup
import html
import json

# ▼ 설정 (GitHub Secrets에서 가져옴) ▼
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 광운대 총학 인스타그램 RSS 주소 (RSS-Bridge 공용 인스턴스 활용)
# 만약 아래 URL이 작동하지 않으면 다른 RSS-Bridge 인스턴스로 교체하면 됩니다.
TARGET_ACCOUNT = "kwu_studentcouncil"
RSS_URL = f"https://rss-bridge.org/bridge01/?action=display&bridge=InstagramBridge&context=Username&u=kwu_studentcouncil&media_type=picture&direct_links=on&format=Html"

def send_telegram(title, link, date):
    if TOKEN and CHAT_ID:
        try:
            # HTML 특수문자 처리 및 제목 정리
            # RSS 피드 특성상 제목에 HTML 태그가 섞일 수 있어 제거해줍니다.
            clean_title = BeautifulSoup(title, "html.parser").get_text()
            safe_title = html.escape(clean_title[:100]) + "..." if len(clean_title) > 100 else html.escape(clean_title)

            msg = f"🔔 <b>[총학생회 인스타 새글]</b>\n\n" \
                  f"{safe_title}\n\n" \
                  f"📅 작성일: {date}"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            keyboard = {"inline_keyboard": [[{"text": "👉 게시물 보기", "url": link}]]}

            payload = {
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard)
            }
            requests.post(url, data=payload)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def run():
    print(f"🔍 Picuki를 통해 {TARGET_ACCOUNT} 모니터링 중...")
    # 인스타그램을 미러링해서 보여주는 사이트입니다.
    url = f"https://www.picuki.com/profile/{TARGET_ACCOUNT}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Picuki의 게시물 리스트 아이템 찾기
        items = soup.select(".post-box")[:5]
        
        current_posts = []
        for item in items:
            # 이미지와 링크 추출
            img_tag = item.select_one(".post-image")
            image_url = img_tag.get("src") if img_tag else ""
            
            link_tag = item.select_one(".photo > a")
            link = "https://www.picuki.com" + link_tag.get("href") if link_tag else ""
            
            # 본문 추출
            desc_tag = item.select_one(".post-description")
            description = desc_tag.get_text().strip() if desc_tag else "내용 없음"
            
            # 고유 ID 생성 (링크 마지막 부분의 고유 코드 사용)
            post_id = link.split("/")[-1]

            current_posts.append({
                "id": post_id,
                "title": description,
                "link": link,
                "image": image_url,
                "date": "최근 게시물"
            })

        # --- 데이터 비교 로직 ---
        DB_FILE = "insta_data.txt"
        old_posts = []
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        for post in current_posts:
            save_data.append(post["id"])
            
            # 첫 실행이 아니고, 기존 DB에 없는 링크라면 전송
            if old_posts and post["id"] not in old_posts:
                print(f"🚀 새 게시물 발견! 전송 중: {post['link']}")
                send_telegram(post['title'], post['link'], post['date'])

        # 결과 저장
        with open(DB_FILE, "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 체크 완료 및 데이터 업데이트.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    run()
