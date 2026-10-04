def sale_price(bought_price: int, current_price: int) -> int:
    profit = current_price - bought_price
    return bought_price + profit // 2 if profit > 0 else current_price


def compute_budget_timeline(picks, chips, stats,initial_budget: float = 100.0, free_hit_chip: str = "uteam") -> list[dict]:
    price = {k: round(v * 10) for k, v in stats.set_index(["player_id", "gw"])["price"].items()}
    chip_by_gw = chips.set_index("gw")["chip"].to_dict() if len(chips) else {}
    squads = picks.groupby("gw")["player_id"].apply(set).to_dict()

    bank = round(initial_budget * 10)
    bought_price = {}
    permanent = None
    timeline = []

    for gw in sorted(squads):
        squad = squads[gw]
        chip = chip_by_gw.get(gw, "none")
        sold, bought = [], []
        temporary = False

        if permanent is None:
            # initial squad: bought at this week's prices (not listed as transfers)
            for pid in squad:
                bought_price[pid] = price[(pid, gw)]
                bank -= price[(pid, gw)]
            cash_after = bank
            permanent = squad

        elif chip == free_hit_chip:
            temporary = True
            cash_after = bank
            for pid in permanent - squad:
                proceeds = sale_price(bought_price[pid], price[(pid, gw)])
                sold.append((pid, proceeds, bought_price[pid]))
                cash_after += proceeds
            for pid in squad - permanent:
                bought.append((pid, price[(pid, gw)]))
                cash_after -= price[(pid, gw)]
            # bank, bought_price and permanent are left untouched: next week reverts

        else:
            for pid in permanent - squad:
                proceeds = sale_price(bought_price[pid], price[(pid, gw)])
                sold.append((pid, proceeds, bought_price[pid]))
                bank += proceeds
                del bought_price[pid]
            for pid in squad - permanent:
                bought.append((pid, price[(pid, gw)]))
                bought_price[pid] = price[(pid, gw)]
                bank -= price[(pid, gw)]
            cash_after = bank
            permanent = squad

        timeline.append({
            "gw": gw,
            "chip": chip,
            "temporary": temporary,
            "squad_value": sum(price[(pid, gw)] for pid in squad),  # market value of the fielded squad
            "bank": bank,              # the permanent bank (unchanged on a uteam week)
            "cash_after": cash_after,  # what must be >= 0 (temp_bank on a uteam week)
            "sold": sold,              # (player_id, proceeds, bought_price)
            "bought": bought,          # (player_id, price)
        })

    return timeline