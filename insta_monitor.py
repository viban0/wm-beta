import os
import requests
from bs4 import BeautifulSoup
import html
import json
import time

# ▼ 설정 ▼
TARGET_ACCOUNT = "kwu_studentcouncil"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(title, link):
    if not (TOKEN and CHAT_ID): return
    try:
        safe_title = html.escape(title[:200])
        msg = f"🔔 <b>[총학생회 인스타 새글 알림]</b>\n\n{safe_title}\n\n🔗 <a href='{link}'>게시물 바로가기</a>"
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False # 미리보기 활성화
        }
        requests.post(url, data=payload)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def run():
    # 전략 변경: 인스타그램을 직접 긁지 않고, 구글 검색 결과 페이지를 통해 우회합니다.
    # 혹은 차단이 덜한 '인스타 내비게이터' 류의 사이트를 공략합니다.
    print(f"🔍 우회 경로를 통해 @{TARGET_ACCOUNT} 스캔 중...")
    
    # 미러 사이트 중 현재 가장 뚫려있는 '인스타내비'류 사이트 타겟팅
    url = f"https://www.google.com/search?q=site:instagram.com/{TARGET_ACCOUNT}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    try:
        # 1. 구글 검색 결과를 통해 최신글 링크를 유추
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code == 429:
            print("❌ 구글마저 너무 잦은 요청으로 차단했습니다. 잠시 후 실행하세요.")
            return
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 구글 검색 결과 내 인스타그램 링크들 추출
        links = soup.find_all('a')
        current_posts = []
        
        for l in links:
            href = l.get('href', '')
            if f"instagram.com/p/" in href:
                # 구글 검색 결과 링크 정제
                actual_link = href.split('&')[0].replace('/url?q=', '')
                post_id = actual_link.split('/')[-2]
                
                if post_id not in [p['id'] for p in current_posts]:
                    current_posts.append({
                        "id": post_id,
                        "title": "인스타그램에 새 게시물이 올라왔습니다!",
                        "link": f"https://www.instagram.com/p/{post_id}/"
                    })

        if not current_posts:
            print("❌ 게시물을 발견하지 못했습니다. (검색 결과 없음)")
            return

        print(f"✅ {len(current_posts)}개의 게시물 링크를 감지했습니다.")

        # --- DB 비교 및 전송 (바이브코더님 기존 로직) ---
        DB_FILE = "insta_data.txt"
        old_posts = []
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines()]

        save_data = []
        for post in current_posts:
            save_data.append(post["id"])
            if old_posts and post["id"] not in old_posts:
                send_telegram(post['title'], post['link'])

        with open(DB_FILE, "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    run()
