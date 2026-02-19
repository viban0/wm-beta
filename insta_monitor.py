import os
import requests
import json
import instaloader
import html
import urllib3

# SSL 인증서 경고 무시 (기존 스타일 유지)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
TARGET_IG_USERNAME = "kwu_studentcouncil" # 모니터링할 계정명 입력
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(title, link):
    if TOKEN and CHAT_ID:
        try:
            # 기존 코드의 HTML 이스케이프 처리 방식 적용
            safe_title = html.escape(title)
            
            # 인스타 본문이 너무 길면 텔레그램 메시지가 지저분해지므로 자르기
            if len(safe_title) > 200:
                safe_title = safe_title[:200] + "..."

            msg = f"📸 <b>[{TARGET_IG_USERNAME}] 새 인스타그램 게시물</b>\n\n" \
                  f"{safe_title}"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            
            # 기존 봇들과 동일한 인라인 키보드 UI 적용
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "👉 게시물 보러가기", "url": link}
                    ]
                ]
            }

            payload = {
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "HTML", 
                "reply_markup": json.dumps(keyboard),
                "disable_notification": False, # 인스타 새 글은 알림 소리 켜기
                "disable_web_page_preview": False # 인스타 썸네일이 보일 수 있도록 False 설정
            }
            requests.post(url, data=payload)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def run():
    print(f"🚀 인스타그램({TARGET_IG_USERNAME}) 스캔 시작...")

    try:
        # Instaloader 초기화
        L = instaloader.Instaloader()
        
        # [주의] 비공개 계정이거나 Rate Limit(차단)에 자주 걸리면 아래 주석을 풀고 로그인하세요.
        IG_USER = os.environ.get('IG_USER')
        IG_PASS = os.environ.get('IG_PASS')
        L.login(IG_USER, IG_PASS)

        # 프로필 가져오기
        profile = instaloader.Profile.from_username(L.context, TARGET_IG_USERNAME)
        posts = profile.get_posts()
        
        current_new_posts = []

        # 최신 5개만 스캔 (서버 부하 및 차단 방지)
        for i, post in enumerate(posts):
            if i >= 2:
                break
            
            shortcode = post.shortcode
            caption = post.caption if post.caption else "내용 없음"
            link = f"https://www.instagram.com/p/{shortcode}/"
            
            current_new_posts.append({
                "id": shortcode,
                "title": caption,
                "link": link
            })

        # 기존 스타일대로 txt 파일에서 이전 데이터 불러오기
        old_posts = []
        if os.path.exists("insta_data.txt"):
            with open("insta_data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        
        # 알림 전송 및 저장
        for post in current_new_posts:
            # 현재 스캔된 shortcode는 무조건 저장 리스트에 추가
            save_data.append(post["id"])
            
            # 첫 실행 시에는 알림을 보내지 않고 기준점만 잡음
            if not old_posts:
                continue
            
            # 기존 기록에 없는 새로운 shortcode라면 알림 전송
            if post["id"] not in old_posts:
                print(f"🚀 새 인스타 게시물: {post['id']}")
                send_telegram(post['title'], post['link'])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료")

        # 최신 5개의 shortcode로 데이터 덮어쓰기 (용량 관리)
        with open("insta_data.txt", "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 insta_data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        exit(1)

if __name__ == "__main__":
    run()
