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
            msg = f"🏠 <b>[행복기숙사] {safe_title}</b>\n\n📅 {date}"
            
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

def run():
    print(f"🚀 행복기숙사 공지 스캔 시작...")

    data = {
        'cPage': '1',
        'rows': '10',
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
            print(f"❌ 응답이 JSON이 아닙니다! (내용: {res.text[:100]})")
            return

        post_list = []

        # 1. 1차 구조 탐색
        if isinstance(result, list):
            post_list = result
        elif isinstance(result, dict):
            # 'root', 'list' 등의 키를 찾음
            possible_keys = ['root', 'list', 'List', 'rows', 'data', 'resultList']
            for key in possible_keys:
                if key in result:
                    post_list = result[key]
                    print(f"🔑 '{key}' 키에서 데이터 1차 발견!")
                    break
        
        # [NEW] 2차 포장 뜯기 (핵심!)
        # 만약 리스트가 1개뿐이고, 그 안에 또 'list' 같은 키가 있다면? -> 그게 진짜다!
        if len(post_list) == 1 and isinstance(post_list[0], dict):
            first_item = post_list[0]
            # 안에 리스트가 또 들어있는지 확인
            nested_keys = ['list', 'List', 'detail', 'subList']
            for n_key in nested_keys:
                if n_key in first_item and isinstance(first_item[n_key], list):
                    print(f"📦 '{n_key}' 안에 숨겨진 진짜 리스트를 찾았습니다! 포장을 뜯습니다.")
                    post_list = first_item[n_key]
                    break
            
            # 만약 포장을 못 뜯었다면, 디버깅을 위해 키 목록 출력
            if len(post_list) == 1: 
                print(f"⚠️ 여전히 데이터가 1개입니다. 이 데이터의 키 목록: {list(first_item.keys())}")

        print(f"🔍 최종 확보한 게시글: {len(post_list)}개")

        # 데이터 처리
        current_posts = []
        for post in post_list:
            # 제목/날짜/ID 찾기 (대소문자 다양하게 시도)
            title = post.get('subject') or post.get('SUBJECT') or post.get('title') or '제목 없음'
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

        old_posts = []
        if os.path.exists("dorm_data.txt"):
            with open("dorm_data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        for post in current_posts:
            save_data.append(post["id"])
            if not old_posts: continue
            
            if post["id"] not in old_posts:
                print(f"🚀 새 기숙사 공지: {post['title']}")
                send_telegram(post['title'], post['date'], post['link'])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료")

        with open("dorm_data.txt", "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 dorm_data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    run()
