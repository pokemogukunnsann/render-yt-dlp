# app.py (health, status, リンク取得対応版)

from flask import Flask, request, jsonify, render_template
import yt_dlp
import datetime

app = Flask(__name__)

# サーバーの状態を管理する変数
# 実際には、この変数ではなく、データベースやキャッシュサービスで管理します。
# 'ACTIVE' | 'MAINTENANCE' | 'DEGRADED' など
SERVER_STATUS = 'ACTIVE' 

# 実行中のタスク（同期処理なので、常にクリアされる）
# 非同期処理（Celery）を導入すれば、ここにタスクリストが溜まります。
CURRENT_TASKS = {} 

# --- ユーザー情報に基づく出力ガイドラインを適用 ---
def print_value_with_label(label, value):
    """変数の値を確定時に表示するヘルパー関数"""
    print(f"{label}:{value}")
# ----------------------------------------------------

@app.route('/')
def index():
    """index.html をレンダリングするエンドポイント"""
    # 実際には templates/index.html が必要です
    return render_template('index.html')

@app.route('/home')
def home():
    """index.html をレンダリングするエンドポイント"""
    # 実際には templates/index.html が必要です
    return render_template('home.html')

@app.route('/YouTubeMP3modoki/')
def YouTubeMP3modoki():
    """index.html をレンダリングするエンドポイント"""
    # 実際には templates/index.html が必要です
    return render_template('YouTubeMP3modoki.html')
# ----------------------------------------------------
## 🩺 ヘルスチェックエンドポイント
# ----------------------------------------------------

@app.route('/health')
def health_check():
    """
    サーバーの状態をチェックし、応答可能かどうかを示すエンドポイント。
    更新やメンテナンスで使えない場合は、ステータスコード 503 を返します。
    """
    if SERVER_STATUS == 'ACTIVE':
        # サーバーが正常に稼働している場合
        return jsonify({
            "status": "ok",
            "uptime": str(datetime.datetime.now()),
            "message": "サーバーは正常に稼働しています。",
        }), 200
    else:
        # メンテナンス中などで利用できない場合
        return jsonify({
            "status": "error",
            "message": "現在、サーバーはメンテナンス中のため、サービスを利用できません。",
        }), 503

# ----------------------------------------------------
## 📊 ステータスエンドポイント
# ----------------------------------------------------

@app.route('/status')
def get_realtime_status():
    """
    リアルタイムの取得状況（処理キューの状態など）を返すエンドポイント。
    今回は同期処理のため、機能の骨格のみを提供します。
    """
    
    # 実際には Celery や Redis を使って、実行中、待機中のタスク数を取得します。
    
    response = {
        "server_status": SERVER_STATUS,
        "api_ready": True,
        "current_time": str(datetime.datetime.now()),
        "task_queue": {
            "pending_tasks": 0,  # 非同期処理がないため 0
            "running_tasks": len(CURRENT_TASKS), # 現在の同期処理リクエスト数
            "message": "このサーバーは同期処理で動いています。リアルタイムステータスは非同期ワーカー導入時に有効になります。",
        }
    }
    
    return jsonify(response)

# ----------------------------------------------------
## 🔗 ダウンロードリンク取得エンドポイント (本処理)
# ----------------------------------------------------
@app.route('/get_download_link', methods=['POST'])
def get_download_link():
    """動画の直接ストリームリンクを取得し、結果HTMLを返すエンドポイント"""

    if SERVER_STATUS != 'ACTIVE':
        return render_template('error.html', message="サーバーが現在利用できません。/healthを確認してください。")
    
    data = request.form
    url = data.get('url')
    user_filename = data.get('filename', '').strip() # ユーザー入力を取得
    cookies_str = data.get('cookies_str')
    
    print_value_with_label("url", url)
    print_value_with_label("user_filename", user_filename)
    print_value_with_label("cookies_str received", bool(cookies_str))

    if not url:
        return render_template('error.html', message="動画のURLが指定されていません。")
    
    format_selector = '18' 
    ydl_opts = {
        'format': format_selector,
        'quiet': True,              
        'simulate': True,           
        'skip_download': True,      
        'noplaylist': True,
        'no_warnings': True,        
        'no_cache_dir': True,       # Read-only file system対策
        'default_search': 'ytsearch',
        'cookiefile': None, 
    }

    temp_cookie_file = None
    if cookies_str:
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, dir='/tmp', encoding='utf-8') as tmp_file:
                tmp_file.write(cookies_str)
                temp_cookie_file = tmp_file.name
                
            ydl_opts['cookiefile'] = temp_cookie_file
            print_value_with_label("temp_cookie_file path", temp_cookie_file)
            
        except Exception as e:
            print(f"一時クッキーファイルの作成に失敗しました: {e}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
        
        target_format = next((fmt for fmt in info_dict.get('formats', []) if str(fmt.get('format_id')) == format_selector), None)
        
        if target_format and target_format.get('url'):
            final_link = target_format.get('url')
        else:
            final_link = info_dict.get('url')
            if not final_link:
                 return render_template('error.html', message="ストリームリンクが見つかりませんでした。動画IDを確認してください。")

        # --- 💡 ファイル名優先順位ロジック ---
        download_title = info_dict.get('title', 'video')

        if user_filename:
            base_name = user_filename
        else:
            base_name = download_title

        safe_filename = "".join(c for c in base_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        
        if not safe_filename:
             safe_filename = 'video'
             print_value_with_label("Filename Source", "Default 'video'")
        # --------------------------------------

        curl_command = f"curl -L '{final_link}' -o '{safe_filename}.mp4'"
        
        print_value_with_label("Download Title", download_title)
        print_value_with_label("Final Filename (safe)", safe_filename)
        print_value_with_label("Curl Command", curl_command)

        return render_template('result.html', title=download_title, stream_link=final_link, curl_command=curl_command)

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm you’re not a bot" in error_msg:
             display_msg = "🚫 YouTubeによる認証エラーが発生しました。クッキーを入力して再試行するか、別の動画を試してください。"
        else:
             display_msg = f"動画情報の取得中にエラーが発生しました: {error_msg}"
        return render_template('error.html', message=display_msg)
    
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return render_template('error.html', message=f"サーバー側で予期せぬエラーが発生しました: {e}")

    finally:
        if temp_cookie_file and os.path.exists(temp_cookie_file):
            os.unlink(temp_cookie_file)
            print_value_with_label("Deleted temp_cookie_file", temp_cookie_file)

if __name__ == '__main__':
    app.run(debug=True)
