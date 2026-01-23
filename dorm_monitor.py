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
            # 요청하신 깔끔한 레이아웃 적용
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

# [핵심] 재귀적으로 모든 데이터를 뒤져서 게시글(seq+subject)을 찾아내는 함수
def find_posts_recursively(data, found_posts):
    if isinstance(data, dict):
        # 1. 딕셔너리인데 'seq'와 'subject'가 있다? -> 게시글 당첨!
        # (키 이름은 대소문자 무관하게 체크)
        keys = {k.lower(): k for k in data.keys()}
        seq_key = keys.get('seq')
        subj_key = keys.get('subject') or keys.get('title') or keys.get('nttsj')
        
        if seq_key and subj_key:
            found_posts.append({
                'seq': data[seq_key],
                'subject': data[subj_key],
                'regdate': data.get('regdate') or data.get('REGDATE') or '날짜 미상'
            })
            return # 찾았으면 더 깊이 안 들어가도 됨 (단, 중첩 구조가 아니라는 가정 하에)

        # 2. 게시글이 아니면 내부 값을 더 뒤져본다
        for v in data.values():
            find_posts_recursively(v, found_posts)
            
    elif isinstance(data, list):
        # 3. 리스트면 안에 있는거 하나하나 다 뒤져본다
        for item in data:
            find_posts_recursively(item, found_posts)

def run():
    print(f"🚀 행복기숙사 공지 정밀 스캔 시작...")

    # 고정 공지가 많을 수 있으니 50개 요청 유지
    data = {
        'cPage': '1',
        'rows': '50', 
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

        # [수정] 구조 상관없이 싹 다 찾기 (DFS 탐색)
        found_raw_posts = []
        find_posts_recursively(result, found_raw_posts)
        
        print(f"🔍 발견된 데이터 조각: {len(found_raw_posts)}개")

        # 데이터 정제
        current_posts = []
        for post in found_raw_posts:
            title = post['subject']
            date = post['regdate']
            seq = post['seq']
            
            if not seq: continue

            fingerprint = str(seq)
            current_posts.append({
                "id": fingerprint,
                "title": title,
                "date": date,
                "link": VIEW_URL
            })

        # [중복 제거] noticeList와 list에 같은 글이 있을 수 있으므로 ID 기준 제거
        unique_posts_dict = {p['id']: p for p in current_posts}
        unique_posts = list(unique_posts_dict.values())

        # [정렬] ID 기준 내림차순 (8340 > 8335)
        # 최신 글(번호가 큰 글)이 리스트 앞쪽에 오도록 정렬
        unique_posts.sort(key=lambda x: int(x['id']), reverse=True)

        if unique_posts:
            print(f"🧹 정제 후 게시글: {len(unique_posts)}개 (최신 ID: {unique_posts[0]['id']})")
        else:
            print("⚠️ 정제 후 게시글이 0개입니다. 구조가 완전히 다를 수 있습니다.")

        old_posts = []
        if os.path.exists("dorm_data.txt"):
            with open("dorm_data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        
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
        
        print("💾 dorm_data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    run()
