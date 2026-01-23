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

def run():
    print(f"🚀 행복기숙사 공지 스캔 시작...")

    # [수정 1] 요청 개수를 20개로 줄임 (고정공지 약 13개 + 최신글 @)
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

        all_raw_posts = []

        # [수정 2] 사이트 보이는 순서(고정공지 -> 일반공지)를 유지하기 위해 순차적으로 추출
        # 서버가 보통 { root: [ { noticeList: [...], list: [...] } ] } 형태로 줌
        
        target_root = None
        
        # 1. 구조 파악 및 진입
        if isinstance(result, list):
            if len(result) > 0 and isinstance(result[0], dict):
                target_root = result[0] # 리스트의 첫 번째 요소가 진짜 데이터 뭉치
            else:
                all_raw_posts = result # 그냥 리스트 자체가 데이터일 경우
        elif isinstance(result, dict):
            # 'root' 키가 있으면 그 안으로 진입
            if 'root' in result:
                if isinstance(result['root'], list) and len(result['root']) > 0:
                    target_root = result['root'][0]
                else:
                    target_root = result['root']
            else:
                target_root = result # 그냥 딕셔너리 자체가 데이터

        # 2. 순서대로 담기 (noticeList 먼저, 그 다음 list)
        if target_root and isinstance(target_root, dict):
            # (1) 고정 공지 (상단)
            if 'noticeList' in target_root and isinstance(target_root['noticeList'], list):
                print(f"📌 고정 공지(noticeList) 발견: {len(target_root['noticeList'])}개")
                all_raw_posts.extend(target_root['noticeList'])
            
            # (2) 일반 공지 (하단)
            if 'list' in target_root and isinstance(target_root['list'], list):
                print(f"📄 일반 공지(list) 발견: {len(target_root['list'])}개")
                all_raw_posts.extend(target_root['list'])
            
            # (3) 만약 둘 다 없으면 그냥 전체 값을 뒤져서 리스트 찾기 (비상용)
            if not all_raw_posts:
                for val in target_root.values():
                    if isinstance(val, list):
                        all_raw_posts.extend(val)

        print(f"🔍 확보한 게시글: {len(all_raw_posts)}개")

        # 3. 데이터 정제 (순서 유지하며 추출)
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

        # [수정 3] 중복 제거 (순서 유지! - Python 3.7+ 딕셔너리는 입력 순서 보장)
        # 고정 공지와 일반 공지에 같은 글이 있을 경우, 먼저 나온(고정 공지 위치) 녀석을 살림
        unique_posts = list({p['id']: p for p in current_posts}.values())
        
        # [수정 4] 강제 정렬 코드 삭제
        # unique_posts.sort(...) <- 이 줄을 지워서 서버가 준 순서(사이트 순서)를 그대로 유지함

        if unique_posts:
            print(f"📝 파일 저장 순서: 상단 {unique_posts[0]['id']} ... 하단 {unique_posts[-1]['id']}")

        old_posts = []
        if os.path.exists("dorm_data.txt"):
            with open("dorm_data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        
        # 순서대로 저장하면서, 알림은 '새로운 것'만 보냄
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
