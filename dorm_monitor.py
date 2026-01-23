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
            # 날짜 형식 통일
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

def run():
    print(f"🚀 행복기숙사 공지 스캔 시작...")

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

        all_raw_posts = []

        # [핵심 수정] 모든 키를 뒤져서 리스트란 리스트는 다 합친다!
        # 1. 최상위가 리스트인 경우
        if isinstance(result, list):
            all_raw_posts.extend(result)
        
        # 2. 최상위가 딕셔너리인 경우 ('root' 등을 찾음)
        elif isinstance(result, dict):
            # 'root' 같은 포장지가 있으면 한 꺼풀 벗김
            target_data = result
            if 'root' in result and isinstance(result['root'], dict):
                target_data = result['root']
                print("📦 'root' 포장지를 벗겼습니다.")

            # 이제 target_data 안에 있는 모든 리스트(list, noticeList 등)를 싹 긁어모음
            for key, value in target_data.items():
                if isinstance(value, list):
                    # 리스트 안에 내용물이 있고, 그게 게시글(딕셔너리)처럼 생겼으면 추가
                    if len(value) > 0 and isinstance(value[0], dict):
                        print(f"🔍 '{key}' 키에서 게시글 {len(value)}개 발견! 합칩니다.")
                        all_raw_posts.extend(value)

        print(f"∑ 총 수집된 데이터: {len(all_raw_posts)}개")

        # 3. 데이터 정제
        current_posts = []
        for post in all_raw_posts:
            # 제목/날짜/ID 추출
            title = post.get('subject') or post.get('SUBJECT') or post.get('nttSj') or post.get('title')
            if not title: continue # 제목 없으면 패스

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

        # [중복 제거] noticeList와 list에 같은 글이 있을 수도 있으니 ID 기준으로 중복 제거
        # 딕셔너리 컴프리헨션을 이용해 ID를 키로 하여 중복 제거 후 다시 리스트로 변환
        unique_posts_dict = {p['id']: p for p in current_posts}
        unique_posts = list(unique_posts_dict.values())

        # [정렬] ID 기준 내림차순 (최신글이 맨 위로) -> 8340이 8335보다 위로 옴!
        unique_posts.sort(key=lambda x: int(x['id']), reverse=True)
        
        print(f"🧹 중복 제거 및 정렬 후 게시글: {len(unique_posts)}개 (최신 ID: {unique_posts[0]['id'] if unique_posts else '없음'})")

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
