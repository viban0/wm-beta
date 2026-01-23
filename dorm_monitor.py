import os
import requests
import json
import urllib3
import html

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
API_URL = "https://kw.happydorm.or.kr/bbs/getBbsList.do"
VIEW_URL = "https://kw.happydorm.or.kr/60/6010.do"

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(title, date, link):
    if TOKEN and CHAT_ID:
        try:
            safe_title = html.escape(title)
            msg = f"🏠 <b>[행복기숙사] {safe_title}</b>\n\n" \
                  f"| 작성일 {date}"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            keyboard = {
                "inline_keyboard": [[{"text": "👉 기숙사 공지 보러가기", "url": link}]]
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

# [핵심 기능] JSON 안에 숨어있는 특정 키(key_name)의 리스트를 몽땅 찾아내는 함수
def find_all_by_key(data, target_key):
    found_items = []
    if isinstance(data, dict):
        for key, value in data.items():
            # 키 이름이 같고, 내용물이 리스트면 확보!
            if key == target_key and isinstance(value, list):
                found_items.extend(value)
            # 아니면 더 깊이 들어가서 찾기
            else:
                found_items.extend(find_all_by_key(value, target_key))
    elif isinstance(data, list):
        for item in data:
            found_items.extend(find_all_by_key(item, target_key))
    return found_items

def run():
    print(f"🚀 행복기숙사 공지 스캔 시작...")

    # [설정] 일반 공지 20개 요청 (고정 공지는 서버가 알아서 줌)
    data = {
        'cPage': '1',
        'rows': '20', 
        'bbs_locgbn': 'KW',
        'bbs_id': 'notice',
        'sType': '', 
        'sWord': ''
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "Origin": "https://kw.happydorm.or.kr",
        "Referer": "https://kw.happydorm.or.kr/60/6010.do"
    }

    try:
        res = requests.post(API_URL, data=data, headers=headers, verify=False, timeout=10)
        
        try:
            result = res.json()
        except ValueError:
            print(f"❌ 응답이 JSON이 아닙니다!")
            return

        # 1. 고정 공지(noticeList) 찾기 - 어디에 있든 찾아냄!
        sticky_raw = find_all_by_key(result, 'noticeList')
        print(f"📌 고정 공지(noticeList) 발견: {len(sticky_raw)}개")

        # 2. 일반 공지(list) 찾기 - 어디에 있든 찾아냄!
        general_raw = find_all_by_key(result, 'list')
        print(f"📄 일반 공지(list) 발견: {len(general_raw)}개")

        # 3. 순서대로 합치기 (고정 공지 먼저 + 일반 공지 나중) -> 사이트 순서 구현
        all_raw_posts = sticky_raw + general_raw
        
        print(f"🔍 전체 확보한 게시글: {len(all_raw_posts)}개")

        # 4. 데이터 정제
        current_posts = []
        for post in all_raw_posts:
            if not isinstance(post, dict): continue

            title = post.get('subject') or post.get('SUBJECT') or post.get('nttSj') or post.get('title')
            if not title: continue 

            date = post.get('regdate') or post.get('REGDATE') or post.get('date') or '날짜 미상'
            seq = post.get('seq') or post.get('SEQ') or post.get('id')
            
            if not seq: continue

            fingerprint = str(seq)
            current_posts.append({
                "id": fingerprint,
                "title": title,
                "date": date,
                "link": VIEW_URL
            })

        # 5. 중복 제거 (순서 유지: 앞에서 이미 나온 고정 공지는 살리고, 뒤에 나온 중복은 제거)
        unique_posts = list({p['id']: p for p in current_posts}.values())

        if unique_posts:
            print(f"📝 파일 저장 순서: 상단 {unique_posts[0]['id']} ... 하단 {unique_posts[-1]['id']}")
        
        old_posts = []
        if os.path.exists("dorm_data.txt"):
            with open("dorm_data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        
        # 순서대로 저장 (고정 -> 일반)
        for post in unique_posts:
            save_data.append(post["id"])
            if not old_posts: continue
            
            if post["id"] not in old_posts:
                print(f"🚀 새 기숙사 공지: {post['title']} (ID: {post['id']})")
                send_telegram(post['title'], post['date'], post['link'])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료")

        with open("dorm_data.txt", "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 dorm_data.txt 업데이트 완료 (사이트 순서 적용)")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    run()
