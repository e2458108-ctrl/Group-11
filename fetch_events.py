import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_calendar_service():
    """認証を行ってAPIサービスを返す関数"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def get_upcoming_assignments(service, max_results=10):
    """
    直近の予定を取得し、リマインダー担当に渡しやすいリスト形式で返す
    """
    # datetime.timezone.utc を使う現代的な書き方に変更
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    print("カレンダーから情報を取得中...")
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=now,
        maxResults=max_results, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    # リマインダー担当に渡すためのデータリストを作成
    assignment_list = []

    if not events:
        print('予定が見つかりませんでした。')
        return []

    for event in events:
        # 必要な情報だけを抽出する
        title = event['summary']
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        # 辞書型（キーと値のペア）にしてリストに追加
        assignment_data = {
            "title": title,
            "deadline": start
        }
        assignment_list.append(assignment_data)

    return assignment_list

# --- ここからメイン処理 ---
if __name__ == '__main__':
    # 1. サービスに接続
    service = get_calendar_service()
    
    # 2. 情報を取得（ここでカレンダーを見に行く）
    my_assignments = get_upcoming_assignments(service)
    
    # 3. リマインダー担当の人に渡すイメージでデータを表示
    print("\n--- リマインダー担当に渡すデータ ---")
    print(my_assignments)
    print("----------------------------------")
    
    # 確認用：中身をひとつずつ表示
    for item in my_assignments:
        print(f"課題名: {item['title']}, 期限: {item['deadline']}")