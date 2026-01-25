import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL   = os.getenv("TO_EMAIL")
EMAIL_PASS = os.getenv("EMAIL_PASS")


def send_mail(
    symbol, score, growth, fdv, lp, urgency, reason,
    chain=None, token=None, mint=None, pair_id=None,

    # --- Dexscreener 詳細データ（Bot側で取得） ---
    price=None,
    priceChange1m=None,
    priceChange5m=None,
    priceChange1h=None,
    txns5m=None,
    buys5m=None,
    sells5m=None,
    volume5m=None,
    liquidity_usd=None,
    fdv_dex=None,
    marketcap=None,
    contract_age_ms=None,
    lp_mint=None
):

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

    # None を見やすく
    def fmt(v, default="-"):
        return default if v is None else v

    # --- コパイロット向け解析依頼プロンプト（本文） ---
    body = f"""
以下の Solana トークンについて、投資価値をプロレベルで総合評価してください。

【対象トークン】
- Symbol: {symbol}
- Chain: {chain or "Solana"}
- Token Mint: {token or mint or "不明"}
- Dexscreener URL: {link_dexscreener}


「token」で Solana チェーンについて、「link_dexscreener」でスクレイピングして、
コインを買う価値があるかに関わる、少なくとも以下の項目の値を取得してください。
必要なら追加しても構いません。

==============================
[基本情報]
- Price (USD): {fmt(price)}
- Liquidity: {fmt(liquidity_usd)}
- FDV: {fmt(fdv_dex or fdv)}
- Market Cap: {fmt(marketcap)}

[価格変化]
- Price Change 5m: {fmt(priceChange5m)}
- Price Change 1h: {fmt(priceChange1h)}
- Price Change 6h:
- Price Change 24h:

[取引データ（全期間）]
- Total Txns:
- Total Volume:
- Total Buys:
- Total Sells:
- Buy Volume:
- Sell Volume:
- Buyers:
- Sellers:

[LPプール構成]
- Pooled Token:
- Pooled SOL:

[ペア情報]
- DEX:
- Pair Age (ms / 人間がわかる単位に変換してもよい): {fmt(contract_age_ms)}
- Token Mint: {token or mint or "不明"}
==============================

【Bot がリアルタイムで取得した重要データ】
以下は、Bot がリアルタイムで取得した指標です。
これらも必ず投資判断に反映してください。

- LP Growth (%): {growth:.1f}
- Current LP (USD): {lp:,.0f}
- FDV (Raydium): {fdv:,}
- Price (Dexscreener): {fmt(price)}
- Price Change 1m: {fmt(priceChange1m)}
- Price Change 5m: {fmt(priceChange5m)}
- Price Change 1h: {fmt(priceChange1h)}
- Txns 5m: {fmt(txns5m)}
- Buys 5m: {fmt(buys5m)}
- Sells 5m: {fmt(sells5m)}
- Volume 5m: {fmt(volume5m)}
- Market Cap (Dexscreener): {fmt(marketcap)}
- LP Mint: {fmt(lp_mint)}

==============================
⑤ 総合判定カテゴリ
==============================
以下のいずれかで判定し、理由を明確に説明してください：

- ENTRY（今入る価値が高い）
- WATCH（監視対象）
- NO（触る必要なし）
- RUG RISK（詐欺・危険）
- BOT（botトークン）
- 初動ではない
- EXIT ZONE（すでに利確帯）
- FAKE PUMP（出来高だけ作っている）
- DEV SELLING（開発者売却を検知）

==============================
⑥ 倍率予測（主観でよい）
==============================
※ 倍率は「今からエントリーした場合」を基準としてください。

- 2倍の可能性
- 10倍の可能性
- 100倍の可能性
- 1000倍以上の可能性

==============================
⑦ 投資判断（プロレベルで具体的に）
==============================
以下を必ず答えてください：

- 今入るべきか
- 触る価値があるか
- 本気度（低 / 中 / 高）
- 推奨資産割合（%）
- 想定保有時間（分 / 時間 / 日）
- 買い戦略（例：3分割、初回は成長確認後）
- 売り戦略（利確ライン・損切りライン）
- 失敗パターン（どうなったら即撤退か）
- 再エントリー条件
  例:
  - 「5分以内に volume が半減 → 即撤退」
  - 「LP が -10% → 成行売り」

==============================
【出力フォーマット】
==============================
以下の形式で出力してください：

■ 総合判定：
■ 理由：

■ 倍率予測（今からエントリーした場合）：
- 2倍：
- 10倍：
- 100倍：
- 1000倍：

■ 投資判断：
- 今入るべきか：
- 触る価値があるか：
- 本気度：
- 推奨資産割合：
- 想定保有時間：
- 買い戦略：
- 売り戦略：
- 失敗パターン：
- 再エントリー条件：

■ 取得データ一覧（DexScreener / Birdeye / X / Contract）：
（取得した生データをすべて記載）

以上のルールに従って、指定されたトークンを総合評価してください。
"""

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(FROM_EMAIL, EMAIL_PASS)
        server.send_message(msg)