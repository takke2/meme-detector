import requests
import json
import os
import copy
from datetime import datetime
from notify_mail import send_mail  # 既存の notify_mail.py を使用

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
WATCH_LP_GROWTH = 50     # 通常ウォッチ
IMMEDIATE_LP_GROWTH = 80 # 緊急通知

DEX_API = "https://api.raydium.io/pairs"

# --- デバッグログ ---
DEBUG_FILE = "logs/debug_notifications.jsonl"
os.makedirs("logs", exist_ok=True)

# --- コンソールデバッグ最大件数 ---
MAX_DEBUG_DISPLAY = 10

def fetch_raydium_pairs():
    try:
        resp = requests.get(DEX_API, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"[API] ペア数: {len(data)}")
        return data
    except Exception as e:
        print("[API] 取得エラー:", e)
        return []

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    return json.load(open(STATE_FILE, "r", encoding="utf-8"))

def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2)
    print(f"[STATE] 更新完了。ペア数: {len(state)}")

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
    print(f"[FILTER] フィルタ後ヒット件数: {len(filtered)}")
    return filtered

def log_debug(entry):
    with open(DEBUG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def main():
    prev_state = load_state()
    current_state = copy.deepcopy(prev_state)

    all_pairs = fetch_raydium_pairs()
    if not all_pairs:
        return

    filtered_pairs = filter_pairs(all_pairs)
    notification_count = 0

    debug_display_count = 0

    for p in filtered_pairs:
        try:
            pair_id = p.get("pair_id")
            if not pair_id:
                continue

            lp_usd = p.get("liquidity", 0)
            fdv = p.get("fdv")
            buys = p.get("txns", {}).get("m5", {}).get("buys")
            sells = p.get("txns", {}).get("m5", {}).get("sells")
            mint_address = p.get("lp_mint")

            # state に必ず存在させ、LP と最大値を更新
            if pair_id not in current_state:
                current_state[pair_id] = {
                    "lp": lp_usd,
                    "max_lp": lp_usd,
                    "notified": {}
                }
            else:
                current_state[pair_id]["lp"] = lp_usd
                # 過去最大 LP 更新
                if lp_usd > current_state[pair_id].get("max_lp", 0):
                    current_state[pair_id]["max_lp"] = lp_usd

            prev_lp = prev_state.get(pair_id, {}).get("lp", 0)
            prev_max_lp = prev_state.get(pair_id, {}).get("max_lp", 0)
            prev_notified = prev_state.get(pair_id, {}).get("notified", {})

            decision = None
            growth = (lp_usd - prev_lp) / prev_lp * 100 if prev_lp > 0 else 0

            # 初動・緊急判定
            if prev_lp > 0:
                if growth >= IMMEDIATE_LP_GROWTH:
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
                    fdv=fdv or 0,
                    lp=lp_usd,
                    urgency="高" if decision == "IMMEDIATE_IN" else "中",
                    reason=f"{decision} 判定",
                    chain=p.get("chainId"),
                    token=mint_address
                )
                current_state[pair_id]["notified"][decision] = True
                notification_count += 1
                sent_mail = True

            # デバッグログは全件保存
            log_debug({
                "time": datetime.utcnow().isoformat(),
                "name": p.get("name"),
                "pair_id": pair_id,
                "lp": lp_usd,
                "max_lp": current_state[pair_id]["max_lp"],
                "prev_lp": prev_lp,
                "buys": buys,
                "sells": sells,
                "fdv": fdv,
                "growth": growth,
                "decision": decision,
                "sent_mail": sent_mail
            })

            # コンソールデバッグは最大 10 件まで
            if debug_display_count < MAX_DEBUG_DISPLAY:
                print(f"[DEBUG] {p.get('name')} | LP:{lp_usd:.2f} | maxLP:{current_state[pair_id]['max_lp']:.2f} | prevLP:{prev_lp:.2f} | buys:{buys} | sells:{sells} | fdv:{fdv} | decision:{decision} | sent_mail:{sent_mail}")
                debug_display_count += 1

        except Exception as e:
            print("Error:", e)
            continue

    save_state(current_state)
    print(f"[SUMMARY] 通知対象件数: {notification_count}, 監視中ペア: {len(current_state)}")

if __name__ == "__main__":
    print("========== START ==========")
    main()
    print("=========== END ===========")
