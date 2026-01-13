import requests, json, os
from datetime import datetime

LOG_FILE = "logs/detections.jsonl"
TRACK_HOURS_LIMIT = 72
TEN_X = 10.0


def fetch_price(chain, pair):
    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair}"
    r = requests.get(url, timeout=20)
    data = r.json()
    if not data.get("pairs"):
        return None
    return float(data["pairs"][0]["priceUsd"])


def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def save_logs(logs):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for log in logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")


def main():
    logs = load_logs()
    now = datetime.utcnow()

    updated = False

    for log in logs:
        if "auto_result" in log:
            continue

        detected_at = datetime.fromisoformat(log["detected_at"])
        hours_passed = (now - detected_at).total_seconds() / 3600

        if hours_passed > TRACK_HOURS_LIMIT:
            log["auto_result"] = {
                "status": "expired",
                "hours_tracked": round(hours_passed, 1)
            }
            updated = True
            continue

        price = fetch_price(log["chain"], log["pair"])
        if price is None:
            continue

        if "tracking" not in log:
            log["tracking"] = {
                "base_price": price,
                "max_price": price
            }

        log["tracking"]["max_price"] = max(
            log["tracking"]["max_price"], price
        )

        max_x = log["tracking"]["max_price"] / log["tracking"]["base_price"]

        if max_x >= TEN_X:
            log["auto_result"] = {
                "hit_10x": True,
                "max_x": round(max_x, 2),
                "time_to_10x_min": int(
                    (now - detected_at).total_seconds() / 60
                )
            }
            updated = True

    if updated:
        save_logs(logs)


if __name__ == "__main__":
    main()
