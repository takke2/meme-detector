import requests
import time
import os
from notify_mail import send_mail

# =========================
# 設定値（ここだけ触ればOK）
# =========================

LP_GROWTH_THRESHOLD = 20      # LPが何％以上増えたら検知するか
MIN_LP_USD = 30_000           # 最低流動性（USD）
MIN_FDV = 50_000
MAX_FDV = 5_000_000

# GitHub Actionsでは1回実行なので0でOK
CHECK_INTERVAL = 0

NOTIFIED_FILE = "notified.txt"

# =========================
# 通知済み管理（一生に一度）
# =========================

def load_notified():
    if not os.path.exists(NOTIFIED_FILE):
        return set()
    with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_notified(symbol):
    with open(NOTIFIED_FILE, "a", encoding="utf-8") as f:
        f.write(symbol + "\n")

# =========================
# Dexscreener 取得（安定版）
# =========================

def fetch_pairs():
    url = "https://api.dexscreener.com/latest/dex/search?q=eth"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("pairs", [])

# =========================
# 数値フィルタ（初期帯）
# =========================

def filter_pairs(pairs):
    result = []
    for p in pairs:
        try:
            fdv = p.get("fdv") or 0
            lp = p["liquidity"]["usd"]
            symbol = p["baseToken"]["symbol"]

            if MIN_FDV <= fdv <= MAX_FDV and lp >= MIN_LP_USD:
                result.append({
                    "symbol": symbol,
                    "fdv": fdv,
                    "lp": lp
                })
        except Exception:
            continue
    return result

# =========================
# スコアリング（説明可能）
# =========================

def calc_score(fdv, lp, growth):
    score = 0

    # LP成長（最重要）
    if growth >= 50:
        score += 50
    elif growth >= 20:
        score += 30

    # 流動性
    if lp >= 300_000:
        score += 30
    elif lp >= 100_000:
        score += 20

    # FDV初期帯
    if fdv <= 500_000:
        score += 20
    elif fdv <= 2_000_000:
        score += 10

    return min(score, 100)

# =========================
# メイン処理
# =========================

def main():
    print("⏱ 実行開始")

    notified = load_notified()

    # 1回目取得
    pairs1 = filter_pairs(fetch_pairs())

    if CHECK_INTERVAL > 0:
        time.sleep(CHECK_INTERVAL)

    # 2回目取得
    pairs2 = filter_pairs(fetch_pairs())

    before = {p["symbol"]: p for p in pairs1}

    for p in pairs2:
        symbol = p["symbol"]

        if symbol not in before:
            continue

        if symbol in notified:
            continue

        lp_before = before[symbol]["lp"]
        lp_after = p["lp"]

        if lp_before <= 0:
            continue

        growth = ((lp_after - lp_before) / lp_before) * 100

        if growth < LP_GROWTH_THRESHOLD:
            continue

        score = calc_score(p["fdv"], lp_after, growth)

        urgency = "高" if score >= 70 else "中" if score >= 50 else "低"

        reason = (
            f"LPが短時間で {growth:.1f}% 増加。\n"
            f"FDVが初期帯（{p['fdv']:,}$）。\n"
            "初期資金流入が確認され、拡散前段階の可能性。"
        )

        send_mail(
            symbol=symbol,
            score=score,
            growth=growth,
            fdv=p["fdv"],
            lp=lp_after,
            urgency=urgency,
            reason=reason
        )

        save_notified(symbol)

        print(f"📧 通知送信: {symbol}（スコア {score}）")

    print("✅ 実行終了")

# =========================

if __name__ == "__main__":
    main()
