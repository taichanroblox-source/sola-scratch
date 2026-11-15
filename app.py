import os
import re
import io
import json
import zipfile
import requests
from flask import Flask, render_template, request, jsonify, Response
from urllib.parse import urlparse, quote

app = Flask(__name__)
S = requests.Session()
S.headers.update({"User-Agent": "SOLA-SCRATCH/1.0 (Scratch project downloader)"})

def project_id(url):
    if not isinstance(url, str):
        return None
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https") or p.hostname not in ("scratch.mit.edu", "www.scratch.mit.edu"):
        return None
    m = re.fullmatch(r"/projects/(\d+)/?", p.path)
    return m.group(1) if m else None

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.post("/api/info")
def info():
    pid = project_id((request.get_json(silent=True) or {}).get("url", ""))
    if not pid:
        return jsonify(error="Scratchの作品URLを入力してね。例：https://scratch.mit.edu/projects/123456789/"), 400
    try:
        r = S.get(f"https://api.scratch.mit.edu/projects/{pid}", timeout=15)
        if r.status_code == 404:
            return jsonify(error="作品が見つからないよ。公開されているか確認してね。"), 404
        r.raise_for_status()
        data = r.json()
        if not data.get("is_published", True):
            return jsonify(error="非公開作品はダウンロードできないよ。"), 403
        return jsonify(id=pid, title=data.get("title") or f"Scratch-{pid}", author=(data.get("author") or {}).get("username", "不明"), thumbnail=(data.get("images") or {}).get("282x218", ""))
    except (requests.RequestException, ValueError):
        return jsonify(error="Scratchの作品情報を取得できなかったよ。時間をおいて再試行してね。"), 502

@app.get("/api/download/<pid>")
def download(pid):
    if not pid.isdigit():
        return jsonify(error="無効な作品IDだよ。"), 400
    try:
        meta = S.get(f"https://api.scratch.mit.edu/projects/{pid}", timeout=15)
        if meta.status_code == 404:
            return jsonify(error="作品が見つからないよ。"), 404
        meta.raise_for_status()
        md = meta.json()
        if not md.get("is_published", True):
            return jsonify(error="非公開作品はダウンロードできないよ。"), 403
        token = md.get("project_token") or ""
        url = f"https://projects.scratch.mit.edu/{pid}"
        if token:
            url += f"?token={quote(str(token))}"
        r = S.get(url, timeout=45)
        r.raise_for_status()
        data = r.content
        try:
            project = json.loads(data)
        except ValueError:
            return jsonify(error="Scratchから作品データを取得できなかったよ。"), 502
        assets = {}
        for target in project.get("targets", []):
            for item in target.get("costumes", []) + target.get("sounds", []):
                name = item.get("md5ext")
                if name and re.fullmatch(r"[0-9a-fA-F]{32}\.[A-Za-z0-9]+", name):
                    assets[name] = True
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", data)
            for name in assets:
                asset = S.get(f"https://assets.scratch.mit.edu/internalapi/asset/{name}/get/", timeout=25)
                asset.raise_for_status()
                if len(asset.content) > 30 * 1024 * 1024:
                    raise ValueError("アセットが大きすぎるよ。")
                z.writestr(name, asset.content)
        title = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", md.get("title") or f"Scratch-{pid}").strip(" .")[:100] or f"Scratch-{pid}"
        payload = buf.getvalue()
        return Response(payload, headers={
            "Content-Type": "application/octet-stream",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(title + '.sb3')}",
            "Content-Length": str(len(payload))
        })
    except (requests.RequestException, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        return jsonify(error="作品ファイルを作成できなかったよ。Scratch側の制限や一時的な通信障害の可能性があるよ。"), 502

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
