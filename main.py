# app.py (health, status, リンク取得対応版)
import os
import subprocess # 💡 subprocessを追加
import json
from flask import Flask, request, jsonify, render_template
import yt_dlp
import datetime
import sys
from urllib.parse import urlparse, parse_qs 
from innertube import InnerTube, Client

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
#']))))))'jihihihuhjhjhuhuhuhugygyggftftftdtdfdrdbh
@app.route('/get_download_link', methods=['POST'])
def get_download_link():
    client = InnerTube("WEB") 
    print_value_with_label("Innertube Client Initialized", "WEB")
    url = request.form['url']
    print_value_with_label("Received URL", url)

    # YouTube動画IDの抽出ロジック
    parsed_url = urlparse(url)
    video_id = ''
    
    # 標準URL (v=...) からの抽出
    if 'v' in parse_qs(parsed_url.query):
        video_id = parse_qs(parsed_url.query)['v'][0]
    # Shorts URL (/shorts/...) からの抽出
    elif parsed_url.path.startswith('/shorts/'):
        path_segments = parsed_url.path.split('/')
        if len(path_segments) > 2:
             video_id = path_segments[2]
    print_value_with_label("Video ID", video_id)
    
    if not video_id:
        return render_template('index.html', error_message="❌ 有効なYouTube URLではありませんでした。")

    download_title = 'video' 
    final_link = ''
    
    # 💡 Innertubeクライアントを初期化（WEBクライアントは最もブラウザに近い振る舞いをします）
    try:
        client = InnerTube(Client.WEB) 
        print_value_with_label("Innertube Client Initialized", Client.WEB.value)

        # 1. 動画情報の取得
        # Innertubeは自動的にAPIを叩き、ストリーミングデータを復号化してくれます。
        info = client.get_info(video_id=video_id)
        
        # 2. 動画タイトルの取得
        download_title = info.title
        print_value_with_label("Video Title", download_title)

        # 3. 最適なストリーミングフォーマットの選択
        # Innertubeの返却データは辞書構造です。hls_manifest_urlがあれば、これが最も確実です。
        stream_url = info.streaming_data.get('hls_manifest_url')
        
        # HLS manifestがない場合、formatsから最高のストリームを探す（通常はMP4）
        if not stream_url and info.streaming_data.get('formats'):
             # ここでは、品質を考慮せず、利用可能な最初のストリームURLをフォールバックとして使用
            stream_url = info.streaming_data['formats'][0].get('url')

        if not stream_url:
            # 💡 Innertubeが認証不要でも取得できない場合は、ストリーミングデータ自体が存在しない
            # (非公開、削除済み、または非常に厳格なDRMがかかっている)
            raise Exception("ストリーミングURLが見つかりませんでした。動画が非公開または削除されている可能性があります。")
        
        final_link = stream_url
        print_value_with_label("Final Stream URL", final_link)

    except Exception as e:
        error_message = f"🛑 Innertube処理中にエラーが発生しました: {e}"
        print(error_message)
        return render_template('index.html', error_message=error_message)

    # --- 成功時の処理 ---
    if final_link.endswith('.m3u8'):
        file_ext = 'm3u8'
    else:
        # Innertubeのストリームは通常MP4形式です
        file_ext = 'mp4' 
        
    # ファイル名のサニタイズ
    sanitized_title = "".join(c for c in download_title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    filename = f"{sanitized_title}.{file_ext}"
    
    # html以外でリクエストするときは絶対にcurlコマンドで実行する
    curl_command = f'curl -L -o "{filename}" "{final_link}"'

    print_value_with_label("File Name", filename)
    print_value_with_label("Curl Command", curl_command)

    return render_template('index.html', 
        download_link=final_link, 
        curl_command=curl_command, 
        filename=filename,
        title=download_title,
        message="✅ ダウンロードリンクの取得に成功しました。curlコマンドをコピーして実行してください。😊"
    )

if __name__ == '__main__':
    app.run(debug=True)
