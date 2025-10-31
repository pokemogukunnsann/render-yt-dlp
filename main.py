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
    """動画の直接ストリームリンクを取得するAPIエンドポイント"""

    # サーバーが利用可能かチェック
    if SERVER_STATUS != 'ACTIVE':
        return jsonify({"status": "error", "message": "サーバーが現在利用できません。/healthを確認してください。"}), 503
    
    data = request.form
    url = data.get('url')
    print_value_with_label("url", url)
    
    format_selector = '18' 
    print_value_with_label("format_selector", format_selector)

    if not url:
        return jsonify({"status": "error", "message": "動画のURLが指定されていません。"})
    
    # yt-dlp オプションの設定
    ydl_opts = {
        'format': format_selector,
        'quiet': True,              
        'simulate': True,           
        'skip_download': True,      
        'noplaylist': True,
        'default_search': 'ytsearch',
    }

    try:
        # 同期処理のため、処理中にユーザーがリロードするとエラーになる可能性がある
        # 実際にはここに CURRENT_TASKS にタスクIDを登録する処理を入れる（非同期の場合）
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
        
        # itag:18 のストリームを探す
        target_format = None
        for fmt in info_dict.get('formats', []):
            if str(fmt.get('format_id')) == format_selector:
                target_format = fmt
                break
        
        # リンクの決定
        if target_format:
            final_link = target_format.get('url')
        else:
            final_link = info_dict.get('url') # 代替リンク
            if not final_link:
                 return jsonify({
                    "status": "error", 
                    "message": "ストリームリンクが見つかりませんでした。動画IDを確認してください。"
                }), 404
        
        download_title = info_dict.get('title', '不明な動画')
        print_value_with_label("Final Link", final_link)
        
        response = {
            "status": "success",
            "title": download_title,
            "stream_link": final_link,
            "message": f"動画ストリームリンクを取得しました。このリンクをcurlで使用できます。"
        }
        
        print(f"Response data (raw):{response}")
        return jsonify(response)

    except yt_dlp.utils.DownloadError as e:
        return jsonify({"status": "error", "message": f"動画情報の取得中にエラーが発生しました: {e}"}), 400
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return jsonify({"status": "error", "message": f"サーバーエラー: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
