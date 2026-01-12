import requests
import time
import os
from notify_mail import send_mail

DEX_API = "https://api.dexscreener.com/latest/dex/pairs/eth"

LP_GROWTH_THRESHOLD = 20      # LPが20%以上増えたら注目
MIN_LP_USD = 30_000           # 最低流動性
MIN_FDV = 50_000
MAX_FDV = 5_000_000

CHECK_INTERVAL = 300          # 5分（GitHub Actionsでは1回実行なのでOK）

NOTIFIED_FILE = "notified.txt"


def load_notified():
    if not os.path.exists(NOTIFIED_FILE):
        return set()
    with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)


def save_notified(symbol):
    with open(NOTIFIED_FILE, "a", encoding="utf-8") as f:
        f.write(symbol + "\n")


def fetch_pairs():
    url = "https://api.dexscreener.com/latest/dex/search?q=eth"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("pairs", [])


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


def calc_score(fdv, lp, growth):
    score = 0
    if growth >= 50:
        score += 50
    elif growth >= 20:
        score += 30

    if lp >= 300_000:
        score += 30
    elif lp >= 100_000:
        score += 20

    if fdv <= 500_000:
        score += 20
    elif fdv <= 2_000_000:
        score += 10

    return min(score, 100)


def main():
    print("⏱ デバッグ実行開始")

    notified = load_notified()

    pairs1 = filter_pairs(fetch_pairs())
    time.sleep(CHECK_INTERVAL)
    pairs2 = filter_pairs(fetch_pairs())

    dict1 = {p["symbol"]: p for p in pairs1}

    for p in pairs2:
        symbol = p["symbol"]
        if symbol not in dict1:
            continue

        lp_before = dict1[symbol]["lp"]
        lp_after = p["lp"]

        growth = ((lp_after - lp_before) / lp_before) * 100

        if growth >= LP_GROWTH_THRESHOLD and symbol not in notified:
            score = calc_score(p["fdv"], lp_after, growth)

            urgency = "高" if score >= 70 else "中" if score >= 50 else "低"

            reason = (
                f"LPが短時間で {growth:.1f}% 増加。\n"
                f"FDVが初期帯（{p['fdv']:,}$）。\n"
                "資金流入初期 → ミーム拡散前の可能性。"
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


if __name__ == "__main__":
    main()
