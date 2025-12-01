import datetime
import os.path
import time
import json

# --- Google Calendar API関連のインポート ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

# --- Selenium関連のインポート ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 1. Google Calendar API 設定エリア
# ==========================================
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'

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

def parse_deadline_str(date_str):
    """
    ポータルから取得した日付文字列（例: '11/27 23:55'）を
    カレンダー登録用のdatetimeオブジェクトに変換する補助関数
    """
    # 余計な文字（〜など）が含まれている場合に備えてクリーニング
    # "11/20 10:30 ～ 11/27 23:55" のような形式の場合、後ろの時間を取る
    if "～" in date_str:
        date_str = date_str.split("～")[-1].strip()
    
    now = datetime.datetime.now()
    current_year = now.year

    try:
        # 年が含まれていない場合（例: 11/27 23:55）、現在の年を補完する
        # フォーマットが "11/27 23:55" であると仮定
        dt = datetime.datetime.strptime(f"{current_year}/{date_str}", '%Y/%m/%d %H:%M')
        
        # もし「今の時期が12月」で「課題期限が1月」なら、来年のことなので年を+1する
        if now.month == 12 and dt.month == 1:
            dt = dt.replace(year=current_year + 1)
        return dt
    except ValueError:
        # 解析失敗時は、とりあえず現在時刻の翌日を返す（エラー回避）
        print(f"⚠️ 日付変換エラー: {date_str} -> 明日の日付で登録します")
        return now + datetime.timedelta(days=1)

def register_assignment(service, subject, title, deadline_str):
    """
    課題をカレンダーに登録する関数
    """
    # 文字列の日時を変換
    deadline_dt = parse_deadline_str(deadline_str)

    # 開始時間を決める（締め切りの1時間前に設定）
    start_dt = deadline_dt - datetime.timedelta(hours=1)

    # Googleカレンダー用のデータを作成
    event_body = {
        'summary': f"【{subject}】{title}",  # タイトル
        'description': f'ポータルサイトから自動連携\n元の期限表記: {deadline_str}',
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Asia/Tokyo',
        },
        'end': {
            'dateTime': deadline_dt.isoformat(),
            'timeZone': 'Asia/Tokyo',
        },
        'colorId': '11',  # 赤色
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 60 * 24}, # 1日前
                {'method': 'popup', 'minutes': 60},      # 1時間前
            ],
        },
    }

    # カレンダーに登録
    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        print(f"📅 登録成功！: {title} (期限: {deadline_str})")
    except Exception as e:
        print(f"❌ 登録エラー: {e}")


# ==========================================
# 2. メイン実行ブロック (Seleniumスクレイピング + 登録)
# ==========================================
if __name__ == '__main__':
    print("--- 自動課題登録システム起動 ---")

    # Chrome起動
    driver = webdriver.Chrome()

    # データを格納するリスト
    all_assignments_data = []

    try:
        # PLASログインページへアクセス
        driver.get("https://plas.soka.ac.jp/csp/plassm/index.csp")
        
        # 数秒待つ（ページ読み込み）
        time.sleep(3)
        
        target_style_value ="margin-top:40px;text-align:center;font-size:18px;"
        # CSSセレクタを使用して、style属性が完全に一致する div 要素を指定します。
        css_selector = f'div[style="{target_style_value}"]'
        
        try:
            # 最大10秒間、要素がクリック可能になるまで待機
            wait = WebDriverWait(driver, 10)
            
            # 要素がDOMに存在し、画面上でクリック可能になるまで待つ
            element_to_click = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
            )
            
            # クリックの実行
            element_to_click.click()
        except Exception as e:
            print(f"❌ 要素が見つからなかったか、クリックできませんでした。エラー: {e}")

        # ---------------------------------------------------------
        # ユーザー入力 (ブラウザ操作の途中で入力を求める仕様を遵守)
        # ---------------------------------------------------------
        
        # ユーザーIDの入力欄を見つけて入力
        print("ユーザーIDを入力してください")
        username_input = (input())
        
        try:
            wait = WebDriverWait(driver, 10)
            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "plas-username"))
            )
            username_field.clear() 
            username_field.send_keys(username_input)
            print(f"✅ ユーザーIDを入力しました。")
        except Exception as e:
            print(f"❌ ユーザー名フィールドが見つかりませんでした。エラー: {e}")

        # パスワードの入力欄を見つけて入力
        print('パスワードを入力してください')
        password_input = (input())
        
        try:
            wait = WebDriverWait(driver, 10)
            password_field = wait.until(
                EC.presence_of_element_located((By.ID, "plas-password"))
            )
            password_field.clear() 
            password_field.send_keys(password_input)
            print(f"✅ パスワードを入力しました。")
        except Exception as e:
            print(f"❌ パスワードフィールドが見つかりませんでした。エラー: {e}")
        
        # ログインボタンを押す
        try:
            wait = WebDriverWait(driver, 10)
            css_selector = 'button[type="submit"]' 
            login_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
            )
            login_button.click()
            print("✅ ログインボタンをクリックしました。")
        except Exception as e:
            print(f"❌ ログインボタンが見つからなかったか、クリックできませんでした。エラー: {e}")

        # ---------------------------------------------------------
        # 課題ページへの移動
        # ---------------------------------------------------------
        try:
            wait = WebDriverWait(driver, 10)
            css_selector = 'a.btn-func4' 
            assignment_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
            )
            assignment_button.click()
            print("✅ 「授業課題」ボタンをクリックしました。課題一覧ページへ遷移します。")
        except Exception as e:
            print(f"❌ 「授業課題」ボタンが見つからなかったか、クリックできませんでした。エラー: {e}")

        # ---------------------------------------------------------
        # データ抽出
        # ---------------------------------------------------------
        # 課題コンテナのCSSセレクタ
        assignment_containers_selector = 'div.box-div.contents-box' 
        try:
            wait = WebDriverWait(driver, 15) 
            
            # コンテナが表示されるまで待機
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, assignment_containers_selector))
            )
            
            # 全ての科目コンテナを取得
            assignment_containers = driver.find_elements(By.CSS_SELECTOR, assignment_containers_selector)
            print(f"✅ 合計 {len(assignment_containers)} 個の科目コンテナが見つかりました。解析を開始します...")

            for container in assignment_containers:
                # 1. 科目名を取得
                try:
                    kamokuname = container.find_element(By.CSS_SELECTOR, '.header-kamokuname').text.strip()
                except Exception:
                    kamokuname = "【科目名不明】"
                
                # 2. 課題名要素を取得
                assignment_name_selector = '.kamoku-info.col-sm-5.text-contents.contents-flex'
                assignment_name_elements = container.find_elements(By.CSS_SELECTOR, assignment_name_selector)

                # 3. 提出期限要素を取得
                end_date_elements = container.find_elements(By.CSS_SELECTOR, 'span.em')

                # 4. 課題名と期限をペアにしてリストに追加
                for assign_el, date_el in zip(assignment_name_elements, end_date_elements):
                    try:
                        assignment_name = assign_el.text.strip()
                        end_date = date_el.text.strip()
                        
                        all_assignments_data.append({
                            'subject': kamokuname,
                            'title': assignment_name,
                            'deadline': end_date
                        })
                    except Exception as e:
                        print(f"⚠️ データ抽出中にエラーが発生しました: {e}")
        except Exception as e:
            print(f"❌ 課題データの取得中にエラーが発生しました: {e}")

    finally:
        # スクレイピング終了後、ブラウザを閉じる
        driver.quit()

    # ==========================================
    # 3. カレンダーへの登録処理
    # ==========================================
    print("\n" + "="*50)
    print(f"抽出完了: {len(all_assignments_data)} 件の課題が見つかりました。")
    print("Googleカレンダーへの登録を開始します...")
    print("="*50)

    if all_assignments_data:
        # カレンダーサービスへの接続
        service = get_calendar_service()

        for data in all_assignments_data:
            register_assignment(
                service,
                data['subject'],  # 科目名
                data['title'],    # 課題名
                data['deadline']  # 期限
            )
    else:
        print("登録する課題がありませんでした。")
    
    print("--- 全ての処理が完了しました ---")