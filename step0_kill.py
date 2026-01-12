import requests

URL = "https://api.dexscreener.com/latest/dex/search?q=doge"

def is_dead(pair):
    symbol = pair.get("baseToken", {}).get("symbol", "")
    fdv = pair.get("fdv") or 0
    liquidity = pair.get("liquidity", {}).get("usd") or 0

    # 対象外
    if symbol.upper() == "ETH":
        return True

    # 即死条件
    if fdv > 50_000_000:
        return True
    if fdv < 50_000:
        return True
    if liquidity < 20_000:
        return True

    return False


def main():
    res = requests.get(URL, timeout=10)
    pairs = res.json().get("pairs", [])

    alive = []
    dead = []

    for p in pairs:
        if is_dead(p):
            dead.append(p)
        else:
            alive.append(p)

    print(f"全体: {len(pairs)}")
    print(f"生存: {len(alive)}")
    print(f"即死: {len(dead)}\n")

    for p in alive:
        print(
            p.get("baseToken", {}).get("symbol"),
            "FDV:", p.get("fdv"),
            "LP:", p.get("liquidity", {}).get("usd")
        )

if __name__ == "__main__":
    main()
