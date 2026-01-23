import os
import requests
import json
import urllib3
import html

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ▼ 설정 ▼
# [중요] 찾아낸 API 주소
API_URL = "https://kw.happydorm.or.kr/bbs/getBbsList.do"
# [중요] 우리가 볼 페이지 주소 (버튼 클릭 시 이동)
VIEW_URL = "https://kw.happydorm.or.kr/60/6010.do"

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# ------------------------------------------------------
# 텔레그램 전송 함수 (HTML 모드 + 조용한 알림 + 버튼)
# ------------------------------------------------------
def send_telegram(title, date, link):
    if TOKEN and CHAT_ID:
        try:
            # HTML 특수문자 변환 (제목 깨짐 방지)
            safe_title = html.escape(title)
            
            msg = f"🏠 <b>[행복기숙사] {safe_title}</b>\n" \
                  f"\n" \
                  f"📅 {date}"
            
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "👉 기숙사 공지 보러가기", "url": link}
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
    print(f"🚀 행복기숙사 공지 스캔 시작...")

    # 1. Payload 설정 (스크린샷에서 본 그대로!)
    data = {
        'cPage': '1',
        'rows': '10',
        'bbs_locgbn': 'KW',
        'bbs_id': 'notice',
        'sWord': '' # 검색어 없음
    }

    # 2. 헤더 설정 (봇 차단 방지)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "Origin": "https://kw.happydorm.or.kr",
        "Referer": "https://kw.happydorm.or.kr/60/6010.do"
    }

    try:
        # 3. API 요청 (POST)
        res = requests.post(API_URL, data=data, headers=headers, verify=False, timeout=10)
        
        # 4. 결과 분석 (JSON)
        # 응답이 JSON 형식이므로 .json()으로 바로 딕셔너리 변환 가능
        result = res.json()
        
        # 실제 공지 리스트는 'list'라는 키 안에 들어있음 (스크린샷 참고)
        # 만약 'list'가 없다면 에러 방지를 위해 빈 리스트 처리
        post_list = result.get('list', [])

        current_posts = []
        
        print(f"🔍 가져온 게시글: {len(post_list)}개")

        for post in post_list:
            # JSON 데이터에서 필요한 정보 뽑기
            # (변수명은 보통 subject, regdate, seq 등으로 되어 있음)
            title = post.get('subject', '제목 없음')
            date = post.get('regdate', '날짜 미상')
            seq = post.get('seq') # 고유 번호 (ID로 사용)
            
            if not seq: continue # ID 없으면 패스

            # 식별자 생성 (고유 번호 이용)
            fingerprint = str(seq)
            
            current_posts.append({
                "id": fingerprint,
                "title": title,
                "date": date,
                "link": VIEW_URL # 리스트 페이지로 이동 (개별 링크는 복잡할 수 있음)
            })

        # 5. 기존 데이터와 비교 (중복 방지)
        # 기숙사 전용 데이터 파일(dorm_data.txt)을 따로 씁니다.
        old_posts = []
        if os.path.exists("dorm_data.txt"):
            with open("dorm_data.txt", "r", encoding="utf-8") as f:
                old_posts = [line.strip() for line in f.readlines() if line.strip()]

        save_data = []
        
        # 최신 글부터 확인해야 하므로 역순으로 보거나 그냥 리스트 순서대로 비교
        for post in current_posts:
            save_data.append(post["id"])
            
            if not old_posts:
                continue
            
            if post["id"] not in old_posts:
                print(f"🚀 새 기숙사 공지: {post['title']}")
                send_telegram(post['title'], post['date'], post['link'])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료 (알림 안 보냄)")

        # 6. 파일 저장
        with open("dorm_data.txt", "w", encoding="utf-8") as f:
            for pid in save_data:
                f.write(pid + "\n")
        
        print("💾 dorm_data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        # exit(1) # 에러 나도 GitHub Action이 멈추지 않게 주석 처리 가능

if __name__ == "__main__":
    run()
