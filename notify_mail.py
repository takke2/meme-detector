import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL   = os.getenv("TO_EMAIL")
EMAIL_PASS = os.getenv("EMAIL_PASS")


def send_mail(symbol, score, growth, fdv, lp, urgency, reason,
              chain=None, token=None, mint=None, pair_id=None):

    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = f"【ミーム検知】{symbol} | 緊急度:{urgency}"

    # --- 各種リンク ---
    link_dexscreener = f"https://dexscreener.com/solana/{mint}" if mint else "不明"
    link_x1 = f"https://twitter.com/search?q=%24{symbol}"
    link_x2 = f"https://twitter.com/search?q={symbol}%20solana"
    link_x3 = f"https://twitter.com/search?q={symbol}%20token"
    link_dextools = f"https://www.dextools.io/app/en/solana/pair-explorer/{pair_id}" if pair_id else "不明"
    link_birdeye = f"https://birdeye.so/token/{mint}" if mint else "不明"

    # --- SNSチェック手順（意味付き） ---
    sns_check = f"""
━━━━━━━━━━━━━━
【SNSチェック手順（手動）】

① DEXScreener（最重要）
● txns5m（直近5分の取引数）
　→ SNSで話題になると最初に跳ねる指標
　→ Botではなく「人間の売買」が増えるため
　→ 50以上：話題化の兆候
　→ 100以上：初動の初動（最速シグナル）

● priceChange5m（直近5分の価格変動）
　→ SNSバズの直後に最も反応する
　→ +10%以上：買い圧が強い

● liquidity（LP）の急増
　→ 運営が広告を打つ前兆
　→ マーケティング開始の合図になることが多い

② X（Twitter）
● 「${symbol}」で検索
　→ 直近1時間の投稿が10件以上：話題化
　→ インフルエンサーが触れる：強い
　→ ミーム画像が増える：強い
　→ チャート画像を貼る人が増える：強い

③ DEXTools
● Hype Score
　→ SNSでの言及数・検索数・アクセス数を元に算出
　→ 50以上：SNSで話題化
　→ 70以上：バズ状態

● Social Mentions
　→ X・Telegram・Discordでの言及数
　→ 急増していればSNSバズの兆候

④ Birdeye
● trendScore
　→ Solana内での注目度
　→ 上昇していれば初動

● holders の増加
　→ コミュニティが育っている証拠

● volume の急増
　→ SNSバズの直後に最も反応する

● None
　→ 新規すぎる or まだ誰も見ていない（初動の可能性）
"""

    # --- 買い判断基準（意味付き） ---
    buy_rules = f"""
【買い判断の基準（意味付き）】

以下のうち 2つ以上 当てはまったら「買い候補」。

● txns5m が 100以上
　→ SNSバズの最速シグナル

● priceChange5m が +10%以上
　→ 買い圧が強く、初動の可能性

● X で直近1時間の投稿が増えている
　→ 人間の関心が急増している

● インフルエンサーが触れている
　→ その後の拡散が期待できる

● DEXTools の Hype Score が高い
　→ SNSでの注目度が高い

● Birdeye の trendScore が上昇
　→ Solana内での注目度が上昇

● LP が急増している
　→ 運営が広告を打つ前兆

● SNSリンクが急に追加された
　→ マーケティング開始の合図
"""

    # --- メール本文 ---
    body = f"""
■ コイン名
{symbol}

■ チェーン
{chain or "不明"}

■ コントラクトアドレス（Phantom検索用）
{token or "不明"}

■ 緊急度
{urgency}

■ LP成長率
{growth:.1f} %

■ FDV
{fdv:,} USD

■ 流動性（LP）
{lp:,.0f} USD

■ 判定理由
{reason}

━━━━━━━━━━━━━━
▼ 各種リンク
DEXScreener:
{link_dexscreener}

X検索:
{link_x1}
{link_x2}
{link_x3}

DEXTools:
{link_dextools}

Birdeye:
{link_birdeye}
━━━━━━━━━━━━━━

{sns_check}

{buy_rules}

━━━━━━━━━━━━━━
※ 10倍候補でも必ず上がるわけではありません
※ ログは自動保存されています
"""

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(FROM_EMAIL, EMAIL_PASS)
        server.send_message(msg)