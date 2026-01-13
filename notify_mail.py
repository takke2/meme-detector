import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL   = os.getenv("TO_EMAIL")
EMAIL_PASS = os.getenv("EMAIL_PASS")


def send_mail(
    symbol,
    score,
    growth,
    fdv,
    lp,
    urgency,
    reason,
    chain=None,
    token=None
):
    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = f"【ミーム検知】{symbol} | スコア{score} | 緊急度:{urgency}"

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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(FROM_EMAIL, EMAIL_PASS)
        server.send_message(msg)
