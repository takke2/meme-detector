import requests

URL = "https://api.dexscreener.com/latest/dex/search?q=ethereum"

response = requests.get(URL, timeout=10)

print("HTTP:", response.status_code)

text = response.text.strip()

if not text.startswith("{"):
    print("JSONでないレスポンス")
    print(text[:200])
    exit()

data = response.json()
pairs = data.get("pairs", [])

print("取得ペア数:", len(pairs))

survivors = []

for p in pairs:
    fdv = p.get("fdv")
    liquidity = p.get("liquidity", {}).get("usd")

    if not fdv or not liquidity:
        continue

    ratio = fdv / liquidity

    if 1.5 <= ratio <= 5:
        survivors.append({
            "symbol": p["baseToken"]["symbol"],
            "fdv": int(fdv),
            "lp": int(liquidity),
            "ratio": round(ratio, 2)
        })

print("\nSTEP1 結果")
print("生存:", len(survivors))
print("即死:", len(pairs) - len(survivors))
print()

for s in survivors[:10]:
    print(f"{s['symbol']} FDV:{s['fdv']} LP:{s['lp']} 比率:{s['ratio']}")
