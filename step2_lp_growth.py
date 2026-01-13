import requests, json, time, os
from datetime import datetime
from notify_mail import send_mail

STATE_FILE = "state.json"
LOG_FILE = "logs/detections.jsonl"

SEARCH_QUERY = "sol"
MIN_LP_USD = 30000
MIN_FDV = 50000
MAX_FDV = 5_000_000

WATCH_LP_GROWTH = 20
IMMEDIATE_LP_GROWTH = 35

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    return json.load(open(STATE_FILE, "r"))

def save_state(data):
    json.dump(data, open(STATE_FILE, "w"))

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
    pairs = fetch_pairs()

    for p in pairs:
        try:
            pair = p["pairAddress"]
            lp = p["liquidity"]["usd"]
            fdv = p.get("fdv") or 0
            tx = p["txns"]["m5"]
            buys, sells = tx["buys"], tx["sells"]

            if not (MIN_FDV <= fdv <= MAX_FDV):
                continue
            if lp < MIN_LP_USD:
                continue

            current[pair] = {
                "lp": lp,
                "fdv": fdv,
                "buys": buys,
                "sells": sells,
                "txns": tx["buys"] + tx["sells"],
                "symbol": p["baseToken"]["symbol"],
                "token": p["baseToken"]["address"],
                "chain": p["chainId"]
            }

            if pair not in prev:
                continue

            growth = (lp - prev[pair]["lp"]) / prev[pair]["lp"] * 100
            decision = None

            if growth >= IMMEDIATE_LP_GROWTH and sells > 0 and buys / sells >= 3 and tx["buys"] + tx["sells"] >= 20:
                decision = "IMMEDIATE_IN"
            elif growth >= WATCH_LP_GROWTH:
                decision = "WATCH"

            if decision:
                log = {
                    "detected_at": datetime.utcnow().isoformat(),
                    "symbol": current[pair]["symbol"],
                    "chain": current[pair]["chain"],
                    "pair": pair,
                    "token": current[pair]["token"],
                    "fdv": fdv,
                    "lp": lp,
                    "lp_growth": round(growth, 2),
                    "txns_5m": tx["buys"] + tx["sells"],
                    "buys": buys,
                    "sells": sells,
                    "decision": decision,
                    "x_mentions": None
                }
                log_detection(log)

                send_mail(
                    symbol=f'{log["symbol"]}',
                    score=80 if decision == "IMMEDIATE_IN" else 60,
                    growth=growth,
                    fdv=fdv,
                    lp=lp,
                    urgency="高" if decision == "IMMEDIATE_IN" else "中",
                    reason=f"{decision} 判定"
                )

        except Exception:
            continue

    save_state(current)

if __name__ == "__main__":
    main()
