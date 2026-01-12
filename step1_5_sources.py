import requests

KEYWORDS = [
    "pepe", "dog", "cat", "inu", "frog",
    "baby", "coin", "ai", "x"
]

all_pairs = []

for kw in KEYWORDS:
    url = f"https://api.dexscreener.com/latest/dex/search?q={kw}"
    r = requests.get(url, timeout=10)

    if r.status_code != 200:
        continue

    data = r.json()
    pairs = data.get("pairs", [])

    all_pairs.extend(pairs)

print("総取得ペア数:", len(all_pairs))

survivors = []

for p in all_pairs:
    fdv = p.get("fdv")
    lp = p.get("liquidity", {}).get("usd")

    if not fdv or not lp:
        continue

    ratio = fdv / lp

    if 1.5 <= ratio <= 5 and lp > 30000:
        survivors.append({
            "symbol": p["baseToken"]["symbol"],
            "fdv": int(fdv),
            "lp": int(lp),
            "ratio": round(ratio, 2)
        })

print("STEP1.5 生存:", len(survivors))
print()

for s in survivors[:10]:
    print(f"{s['symbol']} FDV:{s['fdv']} LP:{s['lp']} 比率:{s['ratio']}")
