# SOLA SCRATCH

Scratchの公開作品URLから作品情報を確認し、.sb3形式でダウンロードできる非公式Webアプリ。

## Render
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`
- Health Check Path: `/health`
