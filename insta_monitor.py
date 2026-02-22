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
        # 제목 정제 및 HTML 이스케이프 (바이브코더님 기존 스타일 반영)
        clean_title = html.escape(title[:200]) + "..." if len(title) > 200 else html.escape(title)
        caption = f"📸 <b>[총학생회 인스타 새글]</b>\n\n{clean_title}"
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        keyboard = {"inline_keyboard": [[{"text": "👉 원본 보기", "url": link}]]}
        
        payload = {
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        }
        res = requests.post(url, data=payload)
        if res.status_code != 200: # 사진 전송 실패 시 텍스트라도 전송
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                          data={"chat_id": CHAT_ID, "text": f"🔔 새글 발견 (사진전송실패)\n\n{link}", "parse_mode": "HTML"})
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def run():
    print(f"🔍 Picuki를 통해 @{TARGET_ACCOUNT} 스캔 중...")
    url = f"https://www.picuki.com/profile/{TARGET_ACCOUNT}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Picuki의 게시물 상자 선택자 (구조 변경 대응)
        items = soup.select(".post-box")
        
        if not items:
            print("❌ 게시물을 하나도 찾지 못했습니다. 사이트 구조가 바뀌었거나 차단되었을 수 있습니다.")
            # 디버깅을 위해 응답 코드 확인
            print(f"응답 코드: {response.status_code}")
            return

        current_posts = []
        for item in items[:5]: # 최신 5개
            # 1. 고유 ID 및 링크 추출
            link_tag = item.select_one(".photo > a")
            if not link_tag: continue
            link = "https://www.picuki.com" + link_tag.get("href")
            post_id = link.split("/")[-1]
            
            # 2. 이미지 URL 추출
            img_tag = item.select_one(".post-image")
            image_url = img_tag.get("src") if img_tag else ""
            
            # 3. 본문 추출
            desc_tag = item.select_one(".post-description")
            description = desc_tag.get_text().strip() if desc_tag else "내용 없음"

            current_posts.append({
                "id": post_id,
                "title": description,
                "link": link,
                "image": image_url
            })

        print(f"✅ {len(current_posts)}개의 게시물을 읽어왔습니다.")

        # --- 데이터 비교 및 저장 ---
        DB_FILE = "insta_data.txt"
        old_posts = []
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        for post in current_posts:
            save_data.append(post["id"])
            
            # 중복 체크: 기존에 없는 ID일 때만 발송
            if old_posts and post["id"] not in old_posts:
                print(f"🚀 새 게시물 전송 중: {post['id']}")
                send_telegram(post['title'], post['link'], post['image'])

        # 파일 업데이트
        with open(DB_FILE, "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print(f"💾 {DB_FILE} 업데이트 완료 (총 {len(save_data)}개 기록)")

    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    run()
