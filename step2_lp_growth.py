import requests
import json
import os
import copy
from datetime import datetime
from notify_mail import send_mail  # 既存のnotify_mail.pyを使用

STATE_FILE = "state.json"
SEARCH_QUERY = "sol"

# --- フィルタ条件 ---
MIN_LP_USD = 1000
MAX_LP_USD = 500_000
MIN_VOLUME_24H = 500
MAX_VOLUME_24H = 1_000_000_000
MIN_APY = 0
MAX_APY = 10_000

# --- 成長率判定 ---
WATCH_LP_GROWTH = 20
IMMEDIATE_LP_GROWTH = 35

DEX_API = "https://api.raydium.io/pairs"

# --- デバッグログ ---
DEBUG_FILE = "logs/debug_notifications.jsonl"
os.makedirs("logs", exist_ok=True)

def fetch_raydium_pairs():
    try:
        resp = requests.get(DEX_API, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"[Raydium] 取得件数: {len(data)}")
        return data
    except Exception as e:
        print("[Raydium] API取得エラー:", e)
        return []

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    return json.load(open(STATE_FILE, "r", encoding="utf-8"))

def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2)
    print(f"state.json 更新完了。対象ペア数: {len(state)}")

def filter_pairs(pairs):
    filtered = []
    for p in pairs:
        try:
            lp_usd = p.get("liquidity", 0)
            volume_24h = p.get("volume_24h_quote") or 0
            apy = p.get("apy") or 0
            if (
                MIN_LP_USD <= lp_usd <= MAX_LP_USD and
                MIN_VOLUME_24H <= volume_24h <= MAX_VOLUME_24H and
                MIN_APY <= apy <= MAX_APY
            ):
                filtered.append(p)
        except Exception:
            continue
    print(f"フィルタ後ヒット件数: {len(filtered)}")
    return filtered

def log_debug(entry):
    with open(DEBUG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def main():
    prev_state = load_state()
    # 前回 state を deepcopy して保持、lpだけ更新する
    current_state = copy.deepcopy(prev_state)

    all_pairs = fetch_raydium_pairs()
    if not all_pairs:
        return

    filtered_pairs = filter_pairs(all_pairs)
    notification_count = 0

    for p in filtered_pairs:
        try:
            pair_id = p.get("pair_id")
            if not pair_id:
                continue

            lp_usd = p.get("liquidity", 0)
            fdv = p.get("fdv") or 0
            buys = p.get("txns", {}).get("m5", {}).get("buys", 0)
            sells = p.get("txns", {}).get("m5", {}).get("sells", 0)

            # state に必ず存在させ、lpだけ更新
            if pair_id not in current_state:
                current_state[pair_id] = {
                    "lp": lp_usd,
                    "notified": {}
                }
            else:
                current_state[pair_id]["lp"] = lp_usd

            prev_lp = prev_state.get(pair_id, {}).get("lp", 0)
            prev_notified = prev_state.get(pair_id, {}).get("notified", {})

            decision = None
            growth = (lp_usd - prev_lp) / prev_lp * 100 if prev_lp > 0 else 0

            if prev_lp > 0:
                if growth >= IMMEDIATE_LP_GROWTH and sells > 0 and buys / max(sells, 1) >= 3 and (buys + sells) >= 20:
                    decision = "IMMEDIATE_IN"
                elif growth >= WATCH_LP_GROWTH:
                    decision = "WATCH"

            sent_mail = False
            if decision and not current_state[pair_id]["notified"].get(decision):
                # メール送信
                send_mail(
                    symbol=f'{p.get("name")}',
                    score=80 if decision == "IMMEDIATE_IN" else 60,
                    growth=growth,
                    fdv=fdv,
                    lp=lp_usd,
                    urgency="高" if decision == "IMMEDIATE_IN" else "中",
                    reason=f"{decision} 判定",
                    chain=p.get("chainId"),
                    token=p.get("lp_mint")
                )
                current_state[pair_id]["notified"][decision] = True
                notification_count += 1
                sent_mail = True

            # デバッグログ
            log_debug({
                "name": p.get("name"),
                "pair_id": pair_id,
                "lp_usd": lp_usd,
                "prev_lp": prev_lp,
                "buys": buys,
                "sells": sells,
                "prev_notified": prev_notified,
                "growth": growth,
                "decision": decision,
                "sent_mail": sent_mail
            })

        except Exception as e:
            print("Error:", e)
            continue

    save_state(current_state)
    print(f"通知対象件数: {notification_count}")

if __name__ == "__main__":
    main()
