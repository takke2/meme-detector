import requests
import json
import os
import copy
from datetime import datetime
from notify_mail import send_mail  # 既存の notify_mail.py を使用

STATE_FILE = "state.json"
LOG_FILE = "logs/debug_notifications.jsonl"
os.makedirs("logs", exist_ok=True)

# --- フィルタ条件 ---
MIN_LP_USD = 1000
MAX_LP_USD = 500_000
MIN_VOLUME_24H = 500
MAX_VOLUME_24H = 1_000_000_000
MIN_APY = 0
MAX_APY = 10_000

# --- 成長率判定 ---
WATCH_LP_GROWTH = 20
IMMEDIATE_LP_GROWTH = 50

DEX_API = "https://api.raydium.io/pairs"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens/"

# -----------------------------
# Dexscreener 詳細データ取得（通知対象だけ）
# -----------------------------
def fetch_dexscreener_details(mint):
    """Dexscreener から詳細データを取得（通知対象だけ呼ぶ）"""
    url = f"{DEXSCREENER_API}{mint}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        if not data or "pairs" not in data:
            return None

        pairs = data.get("pairs")
        if not isinstance(pairs, list) or len(pairs) == 0:
            return None

        p = pairs[0]
        if not isinstance(p, dict):
            return None

        return {
            "price": p.get("priceUsd"),
            "priceChange1m": p.get("priceChange", {}).get("m1"),
            "priceChange5m": p.get("priceChange", {}).get("m5"),
            "priceChange1h": p.get("priceChange", {}).get("h1"),

            "txns5m": p.get("txns", {}).get("m5", {}).get("txns"),
            "buys5m": p.get("txns", {}).get("m5", {}).get("buys"),
            "sells5m": p.get("txns", {}).get("m5", {}).get("sells"),

            "volume5m": p.get("volume", {}).get("m5"),
            "liquidity_usd": p.get("liquidity", {}).get("usd"),
            "fdv": p.get("fdv"),
            "marketcap": p.get("marketCap"),
            "contract_age_ms": p.get("pairCreatedAt"),
            "lp_mint": p.get("lpToken"),
        }

    except Exception as e:
        print("[Dexscreener 詳細取得エラー]", e)
        return None


# --- ログ読み込み ---
def load_logs():
    if not os.path.exists(LOG_FILE):
        return {}
    try:
        return json.load(open(LOG_FILE, "r", encoding="utf-8"))
    except:
        return {}


# --- ログ保存 ---
def save_logs(log_dict):
    json.dump(log_dict, open(LOG_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def fetch_price_usd(mint):
    """通知対象だけ DEXScreener から価格取得"""
    try:
        url = f"{DEXSCREENER_API}{mint}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "pairs" in data and len(data["pairs"]) > 0:
            return float(data["pairs"][0].get("priceUsd") or 0)
    except:
        pass
    return 0.0


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
                if "WSOL" in p.get("name", ""):
                    filtered.append(p)

        except:
            continue

    print(f"[FILTER] フィルタ後ヒット件数: {len(filtered)}")
    return filtered


def extract_non_wsol_token(name, pair_id):
    parts_name = name.split("/")
    parts_id = pair_id.split("-")
    if len(parts_name) != 2 or len(parts_id) != 2:
        return parts_id[0]
    return parts_id[1] if parts_name[0] == "WSOL" else parts_id[0]


# -----------------------------
# main()
# -----------------------------
def main():
    prev_state = load_state()
    current_state = copy.deepcopy(prev_state)
    logs = load_logs()

    all_pairs = fetch_raydium_pairs()
    filtered_pairs = filter_pairs(all_pairs)

    notification_count = 0

    for p in filtered_pairs:
        try:
            pair_id = p.get("pair_id")
            if not pair_id:
                continue

            name = p.get("name")
            lp_usd = p.get("liquidity", 0)
            fdv = p.get("fdv") or 0
            mint = extract_non_wsol_token(name, pair_id)

            # --- state 初期化 ---
            if pair_id not in current_state:
                current_state[pair_id] = {
                    "lp": lp_usd,
                    "max_lp": lp_usd,
                    "last_notified_lp": lp_usd,
                    "initial_price": None
                }
            else:
                if "max_lp" not in current_state[pair_id]:
                    current_state[pair_id]["max_lp"] = current_state[pair_id].get("lp", lp_usd)

                current_state[pair_id]["lp"] = lp_usd
                if lp_usd > current_state[pair_id]["max_lp"]:
                    current_state[pair_id]["max_lp"] = lp_usd

                if "initial_price" not in current_state[pair_id]:
                    current_state[pair_id]["initial_price"] = None

            prev_lp = prev_state.get(pair_id, {}).get("lp", lp_usd)
            last_notified_lp = current_state[pair_id].get("last_notified_lp", prev_lp)
            initial_price = current_state[pair_id]["initial_price"]

            growth = (lp_usd - prev_lp) / max(prev_lp, 1) * 100
            growth_since_last_mail = (lp_usd - last_notified_lp) / max(last_notified_lp, 1) * 100

            # --- 通知判定 ---
            decision = None
            if growth_since_last_mail >= IMMEDIATE_LP_GROWTH:
                decision = "IMMEDIATE"
            elif growth_since_last_mail >= WATCH_LP_GROWTH:
                decision = "WATCH"

            sent_mail = False
            price_usd = None
            hundred_x = False
            dex_details = None  # ← ここで初期化（通知対象だけ取得するため）

            if decision:
                # --- Dexscreener 詳細データは通知対象だけ取得 ---
                dex_details = fetch_dexscreener_details(mint)

                price_usd = fetch_price_usd(mint)

                if initial_price is None:
                    current_state[pair_id]["initial_price"] = price_usd
                    initial_price = price_usd

                if initial_price and initial_price > 0 and price_usd and price_usd / initial_price >= 100:
                    hundred_x = True

                # --- send_mail 呼び出し（詳細データを全部渡す） ---
                send_mail(
                    symbol=name,
                    score=0,
                    growth=growth_since_last_mail,
                    fdv=fdv,
                    lp=lp_usd,
                    urgency="高" if decision == "IMMEDIATE" else "中",
                    reason=f"{decision} 判定（LP成長）",
                    chain="Solana",
                    token=mint,
                    mint=mint,
                    pair_id=pair_id,

                    # --- Dexscreener 詳細データ ---
                    price=dex_details.get("price") if dex_details else None,
                    priceChange1m=dex_details.get("priceChange1m") if dex_details else None,
                    priceChange5m=dex_details.get("priceChange5m") if dex_details else None,
                    priceChange1h=dex_details.get("priceChange1h") if dex_details else None,
                    txns5m=dex_details.get("txns5m") if dex_details else None,
                    buys5m=dex_details.get("buys5m") if dex_details else None,
                    sells5m=dex_details.get("sells5m") if dex_details else None,
                    volume5m=dex_details.get("volume5m") if dex_details else None,
                    liquidity_usd=dex_details.get("liquidity_usd") if dex_details else None,
                    fdv_dex=dex_details.get("fdv") if dex_details else None,
                    marketcap=dex_details.get("marketcap") if dex_details else None,
                    contract_age_ms=dex_details.get("contract_age_ms") if dex_details else None,
                    lp_mint=dex_details.get("lp_mint") if dex_details else None
                )

                current_state[pair_id]["last_notified_lp"] = lp_usd
                notification_count += 1
                sent_mail = True

            # --- ログ保存 ---
            logs[pair_id] = {
                "time": datetime.utcnow().isoformat(),
                "name": name,
                "pair_id": pair_id,
                "mint": mint,
                "lp": lp_usd,
                "max_lp": current_state[pair_id]["max_lp"],
                "prev_lp": prev_lp,
                "last_notified_lp": last_notified_lp,
                "price_usd": price_usd,
                "initial_price": initial_price,
                "hundred_x": hundred_x,
                "growth": growth,
                "growth_since_last_mail": growth_since_last_mail,
                "decision": decision,
                "sent_mail": sent_mail,
                "dex_details": dex_details  # 通知対象だけ保存
            }

        except Exception as e:
            print("Error:", e)
            continue

    save_state(current_state)
    save_logs(logs)
    print(f"[SUMMARY] 通知対象件数: {notification_count}, 監視中ペア: {len(current_state)}")


if __name__ == "__main__":
    print("========== START ==========")
    main()
    print("=========== END ===========")