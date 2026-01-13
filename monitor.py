import os
import requests
import json # [NEW] 버튼 기능을 위해 추가
from bs4 import BeautifulSoup
import urllib3

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
TARGET_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# ------------------------------------------------------
# 1. 키워드별 이모지 매핑
# ------------------------------------------------------
def get_emoji(title):
    if "장학" in title or "대출" in title: return "💰" 
    elif "학사" in title or "수업" in title or "복학" in title: return "📅" 
    elif "행사" in title or "축제" in title or "특강" in title: return "🎉" 
    elif "채용" in title or "모집" in title or "인턴" in title: return "👔" 
    elif "국제" in title or "교환" in title: return "✈️" 
    elif "봉사" in title: return "❤️" 
    elif "대회" in title or "공모" in title: return "🏆" 
    else: return "📢" 

# ------------------------------------------------------
# 2. 텔레그램 전송 함수 (버튼 추가)
# ------------------------------------------------------
def send_telegram(title, link, info):
    if TOKEN and CHAT_ID:
        try:
            icon = get_emoji(title)
            # 대괄호가 마크다운 링크 문법이랑 겹쳐서 깨지는 걸 방지
            safe_title = title
            
            # [수정] 텍스트 링크([👉 공지 바로가기]...)를 제거하고 본문만 남김
            msg = f"{icon} *{safe_title}*\n" \
                  f"\n" \
                  f"{info}"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            
            # [NEW] 버튼 생성
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "👉 공지 내용 보러가기", "url": link}
                    ]
                ]
            }

            payload = {
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown",
                "reply_markup": json.dumps(keyboard) # 버튼 데이터 추가
            }
            requests.post(url, data=payload)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

def run():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        print(f"접속 시도: {TARGET_URL}")
        response = requests.get(TARGET_URL, headers=headers, verify=False, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.select(".board-list-box ul li")[:50]
        current_new_posts = []

        print(f"🔍 스캔 중... ({len(items)}개)")

        for item in items:
            if "신규게시글" not in item.get_text():
                continue

            a_tag = item.select_one("div.board-text > a")
            info_tag = item.select_one("p.info") 

            # 교수지원팀 필터링
            if info_tag and "교수지원팀" in info_tag.get_text():
                continue

            if a_tag:
                raw_title = " ".join(a_tag.get_text().split())
                clean_title = raw_title.replace("신규게시글", "").replace("Attachment", "").strip()
                
                link = a_tag.get('href')
                full_link = f"https://www.kw.ac.kr{link}" if link else TARGET_URL
                
                meta_info = ""
                if info_tag:
                    raw_text = info_tag.get_text("|", strip=True)
                    parts = raw_text.split("|")
                    clean_parts = []
                    skip_next = False
                    for part in parts:
                        p = part.strip()
                        if not p: continue
                        if "수정일" in p:
                            skip_next = True
                            continue
                        if skip_next:
                            if any(char.isdigit() for char in p):
                                skip_next = False
                                continue
                            else:
                                skip_next = False
                        if "조회" in p: continue
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
                    
                    if final_parts:
                        meta_info = "| " + " | ".join(final_parts)

                fingerprint = f"{clean_title}|{full_link}"
                
                current_new_posts.append({
                    "id": fingerprint,
                    "title": clean_title,
                    "link": full_link,
                    "info": meta_info
                })

        old_posts = []
        if os.path.exists("data.txt"):
            with open("data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        for post in current_new_posts:
            save_data.append(post["id"])
            
            if not old_posts:
                continue
            
            if post["id"] not in old_posts:
                print(f"🚀 새 공지: {post['title']}")
                send_telegram(post['title'], post['link'], post['info'])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료")

        with open("data.txt", "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        exit(1)

if __name__ == "__main__":
    run()
