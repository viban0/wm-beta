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
RSS_URL = f"https://rss-bridge.org/?action=display&bridge=InstagramBridge&context=Username&u={TARGET_ACCOUNT}&format=Mrss"

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
    print(f"🔍 {TARGET_ACCOUNT} 모니터링 중...")
    try:
        # RSS 피드 요청 (User-Agent는 예의상 넣어줍니다)
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(RSS_URL, headers=headers, timeout=30)
        
        # XML 파싱 (lxml 설치 필요)
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")[:5] # 최신 5개만 확인
        
        if not items:
            print("⚠️ 게시물을 찾을 수 없습니다. RSS 주소를 확인해주세요.")
            return

        current_posts = []
        for item in items:
            title = item.find("title").get_text() if item.find("title") else "내용 없음"
            link = item.find("link").get_text()
            pub_date = item.find("pubDate").get_text()
            
            current_posts.append({
                "id": link, # 인스타 게시물 고유 링크를 ID로 사용
                "title": title,
                "link": link,
                "date": pub_date
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
