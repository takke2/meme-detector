import requests
import time
import os
from notify_mail import send_mail

# ===== 設定 =====
SEARCH_QUERY = "eth"
LP_GROWTH_THRESHOLD = 20        # LP成長率 %
MIN_LP_USD = 30_000             # 最低LP
MIN_FDV = 50_000
MAX_FDV = 5_000_000

CHECK_INTERVAL = 300            # 5分
NOTIFIED_FILE = "notified.txt"

# 除外トークン（本物ETH系）
EXCLUDE_SYMBOLS = {"ETH", "WETH"}

# =================


def load_notified():
    if not os.path.exists(NOTIFIED_FILE):
        return set()
    with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)


def save_notified(pair_address):
    with open(NOTIFIED_FILE, "a", encoding="utf-8") as f:
        f.write(pair_address + "\n")


def fetch_pairs():
    url = f"https://api.dexscreener.com/latest/dex/search?q={SEARCH_QUERY}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json().get("pairs", [])


def filter_pairs(pairs):
    result = []

    for p in pairs:
        try:
            symbol = p["baseToken"]["symbol"]
            token_address = p["baseToken"]["address"]
            pair_address = p["pairAddress"]

            # ETH / WETH 除外
            if symbol in EXCLUDE_SYMBOLS:
                continue

            fdv = p.get("fdv") or 0
            lp = p["liquidity"]["usd"]

            if not (MIN_FDV <= fdv <= MAX_FDV):
                continue
            if lp < MIN_LP_USD:
                continue

            result.append({
                "pair": pair_address,
                "symbol": symbol,
                "token": token_address,
                "fdv": fdv,
                "lp": lp
            })

        except Exception:
            continue

    return result


def calc_score(fdv, lp, growth):
    score = 0

    # LP成長
    if growth >= 50:
        score += 50
    elif growth >= 20:
        score += 30

    # LP規模
    if lp >= 300_000:
        score += 30
    elif lp >= 100_000:
        score += 20

    # FDV
    if fdv <= 500_000:
        score += 20
    elif fdv <= 2_000_000:
        score += 10

    return min(score, 100)


def main():
    print("⏱ 実行開始")

    notified = load_notified()

    pairs1 = filter_pairs(fetch_pairs())
    time.sleep(CHECK_INTERVAL)
    pairs2 = filter_pairs(fetch_pairs())

    before = {p["pair"]: p for p in pairs1}

    for p in pairs2:
        pair = p["pair"]

        if pair not in before:
            continue
        if pair in notified:
            continue

        lp_before = before[pair]["lp"]
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
            f"FDV {p['fdv']:,} USD の初期帯。\n"
            "資金流入初期 → 拡散前の可能性。"
        )

        send_mail(
            symbol=f"{p['symbol']} ({p['token'][:6]}…)",
            score=score,
            growth=growth,
            fdv=p["fdv"],
            lp=lp_after,
            urgency=urgency,
            reason=reason
        )

        save_notified(pair)


if __name__ == "__main__":
    main()
