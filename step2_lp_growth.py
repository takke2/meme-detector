import requests, json, os
from datetime import datetime
from notify_mail import send_mail

STATE_FILE = "state.json"
LOG_FILE = "logs/detections.jsonl"

SEARCH_QUERY = "sol"

MIN_LP_USD = 30_000
MIN_FDV = 50_000
MAX_FDV = 5_000_000

WATCH_LP_GROWTH = 20
IMMEDIATE_LP_GROWTH = 35

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    return json.load(open(STATE_FILE, "r", encoding="utf-8"))

def save_state(data):
    json.dump(data, open(STATE_FILE, "w", encoding="utf-8"), indent=2)

def log_detection(data):
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def fetch_pairs():
    url = f"https://api.dexscreener.com/latest/dex/search?q={SEARCH_QUERY}"
    return requests.get(url, timeout=20).json().get("pairs", [])

def main():
    prev = load_state()
    current = {}

    for p in fetch_pairs():
        try:
            pair = p["pairAddress"]
            lp = p["liquidity"]["usd"]
            fdv = p.get("fdv") or 0
            tx = p["txns"]["m5"]
            buys, sells = tx["buys"], tx["sells"]

            # state には必ず保存
            current[pair] = {
                "lp": lp,
                "notified": prev.get(pair, {}).get("notified", {})
            }

            # 初回比較不可
            prev_lp = prev.get(pair, {}).get("lp", 0)
            if prev_lp <= 0:
                continue

            if not (MIN_FDV <= fdv <= MAX_FDV):
                continue
            if lp < MIN_LP_USD:
                continue

            growth = (lp - prev_lp) / prev_lp * 100
            decision = None

            if (
                growth >= IMMEDIATE_LP_GROWTH
                and sells > 0
                and buys / sells >= 3
                and (buys + sells) >= 20
            ):
                decision = "IMMEDIATE_IN"
            elif growth >= WATCH_LP_GROWTH:
                decision = "WATCH"

            if not decision:
                continue

            # 通知済み防止
            if current[pair]["notified"].get(decision):
                continue

            log = {
                "detected_at": datetime.utcnow().isoformat(),
                "symbol": p["baseToken"]["symbol"],
                "chain": p["chainId"],
                "pair": pair,
                "token": p["baseToken"]["address"],
                "fdv": fdv,
                "lp": lp,
                "lp_growth": round(growth, 2),
                "txns_5m": buys + sells,
                "buys": buys,
                "sells": sells,
                "decision": decision
            }

            log_detection(log)

            send_mail(
                symbol=f'{log["symbol"]} ({log["chain"]})',
                score=80 if decision == "IMMEDIATE_IN" else 60,
                growth=growth,
                fdv=fdv,
                lp=lp,
                urgency="高" if decision == "IMMEDIATE_IN" else "中",
                reason=f"{decision} 判定"
            )

            current[pair]["notified"][decision] = True

        except Exception:
            continue

    save_state(current)

if __name__ == "__main__":
    main()
