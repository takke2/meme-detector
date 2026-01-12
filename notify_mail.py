import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL   = os.getenv("TO_EMAIL")
EMAIL_PASS = os.getenv("EMAIL_PASS")


def send_mail(symbol, score, growth, fdv, lp, urgency, reason):
    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = f"【ミーム検知】{symbol} | スコア{score} | 緊急度:{urgency}"

    body = f"""
■ なぜこの通知が来た？
初心者向けに言うと「お金が入り始めた初期段階」だからです。

━━━━━━━━━━━━━━
■ コイン名
{symbol}

■ 緊急度
{urgency}

■ 期待スコア（最大100）
{score}

■ LP成長率
{growth:.1f} %

■ FDV（時価総額想定）
{fdv:,} USD

■ 流動性（LP）
{lp:,.0f} USD

■ 判断理由
{reason}

━━━━━━━━━━━━━━
※ 10倍候補でも必ず上がるわけではありません
※ 月1レベルで届く想定の強シグナルです
"""

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(FROM_EMAIL, EMAIL_PASS)
        server.send_message(msg)
