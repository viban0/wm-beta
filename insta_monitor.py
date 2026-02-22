import os
import requests
import json
import instaloader # [NEW] 인스타그램 크롤링을 위한 마법의 라이브러리
import html
import re

# ▼ 설정 ▼
TARGET_ACCOUNT = "kwu_studentcouncil"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def get_emoji(title):
    # 인스타는 해시태그나 본문 내용에 따라 이모지를 결정하면 좋습니다
    if "장학" in title or "대출" in title: return "💰" 
    elif "축제" in title or "비마랑" in title: return "🎉" 
    elif "간식" in title or "행사" in title: return "🍕" 
    else: return "📢" 

def send_telegram(title, link, info):
    if TOKEN and CHAT_ID:
        try:
            icon = get_emoji(title)
            safe_title = html.escape(title)

            # 인스타그램은 이미지가 메인이므로 본문(title)을 적당히 잘라서 보여줍니다.
            msg = f"{icon} <b>[총학생회 새글]</b>\n\n" \
                  f"<i>{safe_title}</i>\n\n" \
                  f"📅 {info}"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "👉 인스타로 보러가기", "url": link}
                    ]
                ]
            }

            payload = {
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard),
                "disable_notification": True 
            }
            requests.post(url, data=payload)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def run():
    print(f"🔍 [{TARGET_ACCOUNT}] 인스타그램 스캔 시도...")
    
    # Instaloader 객체 생성
    L = instaloader.Instaloader()
    
    # [주의] 인스타그램이 익명 접근을 막을 경우 아래 주석을 풀고 "안 쓰는 부계정"으로 로그인해야 할 수 있습니다.
    # 본계정 사용은 절대 금물입니다! (봇으로 오해받아 정지될 수 있음)
    # L.login("내_부계정_아이디", "내_부계정_비밀번호")

    try:
        # 타겟 계정 프로필 가져오기
        profile = instaloader.Profile.from_username(L.context, TARGET_ACCOUNT)
        
        # 게시물 가져오기 (제네레이터 형태)
        posts = profile.get_posts()

        current_new_posts = []
        count = 0
        
        print("📥 최신 게시물 분석 중...")
        for post in posts:
            # 💡 [핵심] 무료를 유지하려면 인스타 서버에 무리를 주면 안 됩니다. 
            # 딱 최신 3개만 검사하고 빠집니다.
            if count >= 3: 
                break
                
            # post.shortcode: 게시물 고유 ID (이걸 기준으로 중복 판별)
            # post.caption: 인스타 본문
            link = f"https://www.instagram.com/p/{post.shortcode}/"
            caption = post.caption if post.caption else "내용 없음"
            
            # 인스타는 제목이 없으니 본문 앞부분을 제목처럼 사용
            title_preview = caption[:100] + "..." if len(caption) > 100 else caption
            fingerprint = post.shortcode

            current_new_posts.append({
                "id": fingerprint,
                "title": title_preview,
                "link": link,
                "info": f"{post.date_utc.strftime('%Y-%m-%d %H:%M:%S')} (UTC)"
            })
            count += 1

        # --- 이 아래는 바이브코더님의 원본 로직과 100% 동일합니다! ---
        # 파일 이름을 insta_data.txt로 바꿔서 기존 학교 공지 봇과 충돌하지 않게 합니다.
        old_posts = []
        if os.path.exists("insta_data.txt"):
            with open("insta_data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        for post in current_new_posts:
            save_data.append(post["id"])
            
            if not old_posts:
                continue
            
            if post["id"] not in old_posts:
                print(f"🚀 새 인스타 알림 전송: {post['link']}")
                send_telegram(post['title'], post['link'], post['info'])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료")

        with open("insta_data.txt", "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 insta_data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 힌트: 인스타그램에서 봇을 차단했을 수 있습니다. IP를 바꾸거나 부계정 로그인이 필요할 수 있습니다.")
        exit(1)

if __name__ == "__main__":
    run()
