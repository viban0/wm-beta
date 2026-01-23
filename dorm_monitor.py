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

    # [수정 1] sType 추가 (빈 값이라도 보내야 함)
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
        
        # JSON 응답 받기
        try:
            result = res.json()
        except ValueError:
            print(f"❌ 응답이 JSON이 아닙니다! (내용: {res.text[:100]})")
            return

        post_list = []

        # [수정 2] 응답 구조 자동 탐지 (스마트 로직)
        if isinstance(result, list):
            # 1. 만약 응답이 바로 리스트([...])라면 그대로 사용
            print("✅ 응답 형태: 리스트(List) 감지됨")
            post_list = result
        elif isinstance(result, dict):
            # 2. 딕셔너리라면 흔한 키 이름들을 순서대로 확인
            print(f"✅ 응답 형태: 딕셔너리(Dict) 감지됨. 키 목록: {list(result.keys())}")
            
            # 찾을 후보 키 이름들
            possible_keys = ['list', 'List', 'root', 'rows', 'data', 'resultList']
            
            found_key = None
            for key in possible_keys:
                if key in result:
                    found_key = key
                    break
            
            if found_key:
                post_list = result[found_key]
                print(f"🔑 '{found_key}' 키에서 데이터 발견!")
            else:
                print(f"⚠️ 데이터를 담은 키를 찾지 못했습니다. 구조 확인이 필요합니다.")
        
        print(f"🔍 가져온 게시글: {len(post_list)}개")

        # 데이터 처리
        current_posts = []
        for post in post_list:
            # 제목과 날짜 키 찾기 (subject, regdate가 일반적이지만 다를 수 있음)
            title = post.get('subject') or post.get('TITLE') or post.get('title') or '제목 없음'
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
