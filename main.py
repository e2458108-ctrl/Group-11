import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_calendar_service():
    """認証を行ってAPIサービスを返す"""
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

def get_my_tasks(num_tasks=10):
    """  カレンダーから課題を取得してリストで返す関数。 """
    service = get_calendar_service()
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=num_tasks, singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    assignment_list = []
    for event in events:
        assignment_list.append({
            "title": event['summary'],
            "deadline": event['start'].get('dateTime', event['start'].get('date'))
        })

    return assignment_list

if __name__ == '__main__':
    print("--- テスト実行中 ---")
    tasks = get_my_tasks()
    print(tasks)