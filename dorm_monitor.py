import html
import requests
from bot_utils import create_session, read_state, send_telegram, write_state

# ▼ 설정 ▼
API_URL = "https://kw.happydorm.or.kr/bbs/getBbsList.do"
VIEW_URL = "https://kw.happydorm.or.kr/60/6010.do"

def notify_post(session, title, date, link):
    message = f"🏠 <b>새 행복기숙사 공지</b>\n\n{html.escape(title)}\n<blockquote>작성일 {html.escape(str(date))}</blockquote>"
    return send_telegram(session, message, {
        "inline_keyboard": [[{"text": "기숙사 공지 보기 →", "url": link}]]
    }, disable_notification=True)

# [핵심 기능] 성공했던 "재귀 탐색" 함수 복구!
# 키 이름(noticeList 등)을 몰라도, 내용물(seq, subject)이 있으면 무조건 찾아냅니다.
def find_posts_recursively(data, found_posts):
    if isinstance(data, dict):
        # 대소문자 무관하게 키 검사
        keys = {k.lower(): k for k in data.keys()}
        seq_key = keys.get('seq')
        subj_key = keys.get('subject') or keys.get('title') or keys.get('nttsj')
        
        # 게시글 형태(ID와 제목이 있음)라면 확보!
        if seq_key and subj_key:
            found_posts.append({
                'id': str(data[seq_key]),
                'title': data[subj_key],
                'date': data.get('regdate') or data.get('REGDATE') or '날짜 미상'
            })
            return 

        # 게시글이 아니면 더 깊이 탐색
        for v in data.values():
            find_posts_recursively(v, found_posts)
            
    elif isinstance(data, list):
        for item in data:
            find_posts_recursively(item, found_posts)

def run():
    print(f"🚀 행복기숙사 공지 스캔 시작...")

    # [설정] 일반 공지는 20개만 요청 (고정 공지는 서버가 주는 대로 다 받음)
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
        session = create_session()
        session.headers.update(headers)
        res = session.post(API_URL, data=data, timeout=10)
        res.raise_for_status()
        
        try:
            result = res.json()
        except ValueError:
            print(f"❌ 응답이 JSON이 아닙니다!")
            return

        # 1. 성공했던 방식(재귀 탐색)으로 모든 게시글 긁어오기
        all_found_posts = []
        find_posts_recursively(result, all_found_posts)
        
        print(f"🔍 발견된 전체 데이터: {len(all_found_posts)}개 (고정+일반 포함)")

        # 2. 데이터 정제 및 리스트 생성
        current_posts = []
        for post in all_found_posts:
            if not post['id']: continue
            
            # 링크 추가
            post['link'] = VIEW_URL
            current_posts.append(post)

        # 3. 중복 제거 (ID 기준)
        # 딕셔너리 컴프리헨션을 이용해 중복 ID 제거
        unique_posts_dict = {p['id']: p for p in current_posts}
        unique_posts = list(unique_posts_dict.values())

        # 4. [핵심] ID 내림차순 정렬 (최신글이 맨 위로)
        # 8340(고정)이 8335(일반)보다 숫자가 크므로, 정렬하면 자연스럽게 맨 위로 옵니다.
        unique_posts.sort(key=lambda x: int(x['id']), reverse=True)

        # 5. [설정 적용] 상위 20개만 자르기
        final_posts = unique_posts[:20]

        if final_posts:
            print(f"📝 저장 범위: 상단 {final_posts[0]['id']} ... 하단 {final_posts[-1]['id']} (총 {len(final_posts)}개)")
        
        old_posts = read_state("dorm_data.txt")

        save_data = list(old_posts)
        
        # 알림 전송 및 저장
        for post in final_posts:
            if not old_posts:
                save_data.append(post["id"])
                continue
            
            if post["id"] not in old_posts:
                print(f"🚀 새 기숙사 공지: {post['title']} (ID: {post['id']})")
                if notify_post(session, post['title'], post['date'], post['link']):
                    save_data.append(post["id"])

        if not old_posts:
             print("🚀 첫 실행: 기준점 잡기 완료")

        write_state("dorm_data.txt", save_data[-100:])
        
        print("💾 dorm_data.txt 업데이트 완료")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    run()
