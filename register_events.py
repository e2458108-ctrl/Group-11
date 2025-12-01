import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
# エラーハンドリング用にインポートを追加
from google.auth.exceptions import RefreshError

# 【重要】書き込みを行うため、権限を 'calendar' に変更（.readonly を削除）
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """認証を行ってAPIサービスを返す関数"""
    creds = None
    # token.json があれば読み込む
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 期限切れや権限変更時、初回はログイン画面を出す
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # スコープ変更などでリフレッシュに失敗した場合は、再認証するためにcredsを破棄
                print("権限が変更されたため、再認証を行います。")
                creds = None
        
        # credsがない（初回、またはリフレッシュ失敗時）場合は新規ログイン
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 新しい権限で保存
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('calendar', 'v3', credentials=creds)

def register_assignment(service, title, deadline_str):
    """
    課題をカレンダーに登録する関数
    title: 課題名（例: "数学レポート"）
    deadline_str: 締め切り日時（文字列形式: "2025-11-28T23:55:00"）
    """
    
    # 1. 文字列の日時を、Pythonが扱える「日付データ」に変換
    # ※受け取るデータ形式に合わせて調整が必要ですが、今回はISO形式を想定
    try:
        deadline_dt = datetime.datetime.fromisoformat(deadline_str)
    except ValueError:
        # 万が一 "2025/11/28 23:55" のような形式が来た場合の対応例
        deadline_dt = datetime.datetime.strptime(deadline_str, '%Y/%m/%d %H:%M')

    # 2. 開始時間を決める（締め切りの1時間前に設定してみる）
    start_dt = deadline_dt - datetime.timedelta(hours=1)

    # 3. Googleカレンダー用のデータを作成
    event_body = {
        'summary': f"【課題】{title}",  # タイトル
        'description': 'ポータルサイトから自動連携',
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Asia/Tokyo',
        },
        'end': {
            'dateTime': deadline_dt.isoformat(),
            'timeZone': 'Asia/Tokyo',
        },
        # オプション: 色を変える（"11"は赤色など、IDで指定）
        'colorId': '11', 
        # オプション: 通知設定（締め切りの24時間前と、1時間前に通知）
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 60 * 24}, # 1日前
                {'method': 'popup', 'minutes': 60},      # 1時間前
            ],
        },
    }

    # 4. カレンダーに登録（API実行）
    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        print(f"登録成功！: {title} (期限: {deadline_str})")
        print(f"URL: {event.get('htmlLink')}")
    except Exception as e:
        print(f"登録エラー: {e}")

# --- メイン処理 ---
if __name__ == '__main__':
    service = get_calendar_service()

    # --- ポータルサイトから取得したと仮定するデータ ---
    # 本当はここで scraper.py からデータを貰いますが、今はテストデータを使います
    portal_data = [
        {
            "title": "線形代数 第3回レポート",
            "deadline": "2025-11-28T23:59:00" 
        },
        {
            "title": "プログラミング演習 課題B",
            "deadline": "2025-11-30T17:00:00"
        }
    ]

    print("--- ポータルサイトのデータをカレンダーに反映します ---")
    
    for task in portal_data:
        register_assignment(service, task['title'], task['deadline'])
        
    print("--- 全件処理完了 ---")