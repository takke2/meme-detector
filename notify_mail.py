import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# 環境変数からメール情報を取得
FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL   = os.getenv("TO_EMAIL")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def send_mail(
    symbol,      # コイン名
    score,       # スコア（0-100）
    growth,      # LP成長率(%)
    fdv,         # FDV(想定時価総額)
    lp,          # 流動性(USD)
    urgency,     # 緊急度（高/中）
    reason,      # 判定理由
    chain=None,  # ブロックチェーン名
    token=None   # トークンアドレス
):
    # メールヘッダー
    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = f"【ミーム検知】{symbol} | スコア{score} | 緊急度:{urgency}"

    # メール本文
    body = f"""
■ なぜこの通知が来た？
短時間で資金と取引が流入した「初動検知シグナル」です。

━━━━━━━━━━━━━━
■ コイン名
{symbol}

■ チェーン
{chain or "不明"}

■ コントラクトアドレス
{token or "不明"}

■ 緊急度
{urgency}

■ 期待スコア（最大100）
{score}

■ LP成長率
{growth:.1f} %

■ FDV（想定時価総額）
{fdv:,} USD

■ 流動性（LP）
{lp:,.0f} USD

■ 判断理由
{reason}

━━━━━━━━━━━━━━
※ 10倍候補でも必ず上がるわけではありません
※ ログは自動保存されています
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Gmail SSL で送信
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(FROM_EMAIL, EMAIL_PASS)
        server.send_message(msg)
