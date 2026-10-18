"""
Task 6.4 - Luật kết hợp Apriori trên tag (câu hỏi 6): tag nào hay đi cùng nhau,
tổ hợp tag nào gắn với đánh giá tích cực cao (item ảo HIGH_POSITIVE).
Kết quả ghi vào mining.tag_rules cho Copilot (tag_opportunities).

    python mining/association_rules.py [min_support]
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

OUT_DIR = BASE_DIR / "mining" / "outputs"
HIGH_POSITIVE = "HIGH_POSITIVE"
HIGH_POSITIVE_RATIO = 0.9   # >= 90% review tích cực (mốc "Very Positive" của Steam là 80%)
MIN_LIFT = 1.2


def mine_rules(transactions, min_support=0.03, max_len=4):
    """transactions: list[list[str]] -> (frequent itemsets, rules sắp theo lift giảm dần)."""
    te = TransactionEncoder()
    onehot = pd.DataFrame(te.fit(transactions).transform(transactions), columns=te.columns_)
    itemsets = apriori(onehot, min_support=min_support, use_colnames=True, max_len=max_len)
    if itemsets.empty:
        return itemsets, pd.DataFrame(columns=["antecedents", "consequents", "support", "confidence", "lift"])
    rules = association_rules(itemsets, num_itemsets=len(onehot), metric="lift", min_threshold=MIN_LIFT)
    return itemsets, rules.sort_values(["lift", "confidence"], ascending=False).reset_index(drop=True)


def rule_label(row):
    return f"{' + '.join(sorted(row['antecedents']))} → {' + '.join(sorted(row['consequents']))}"


def plot_top_rules(rules, path, title, n=15):
    top = rules.head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(top) + 1.5))
    ax.barh([rule_label(r) for _, r in top.iterrows()], top["lift"], color="#4C72B0")
    for i, (_, r) in enumerate(top.iterrows()):
        ax.text(r["lift"], i, f"  conf {r['confidence']:.2f} · sup {r['support']:.3f}", va="center", fontsize=8)
    ax.set_xlabel("lift")
    ax.set_xlim(0, top["lift"].max() * 1.35)  # chừa chỗ cho nhãn conf/sup
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def run(transactions_by_game, high_positive_ids, out_dir=OUT_DIR, min_support=0.03):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    transactions = [tags + [HIGH_POSITIVE] if game_id in high_positive_ids else tags
                    for game_id, tags in transactions_by_game.items()]
    itemsets, rules = mine_rules(transactions, min_support)

    hp_rules = rules[rules["consequents"].apply(lambda c: c == frozenset([HIGH_POSITIVE]))]
    tag_rules = rules[rules.apply(lambda r: HIGH_POSITIVE not in r["antecedents"] | r["consequents"], axis=1)]

    cols = ["antecedents", "consequents", "support", "confidence", "lift"]
    for df, name in [(tag_rules, "rules"), (hp_rules, "rules_high_positive")]:
        df[cols].assign(antecedents=df["antecedents"].apply(lambda s: ", ".join(sorted(s))),
                        consequents=df["consequents"].apply(lambda s: ", ".join(sorted(s)))
                        ).to_csv(out_dir / f"{name}.csv", index=False)

    # 1 bảng cho Copilot: luật tag-tag và luật tag -> HIGH_POSITIVE (cờ is_high_positive), vế luật là mảng tag
    table = pd.concat([tag_rules.assign(is_high_positive=False), hp_rules.assign(is_high_positive=True)])[
        cols + ["is_high_positive"]].assign(antecedents=lambda d: d["antecedents"].apply(sorted),
                                            consequents=lambda d: d["consequents"].apply(sorted))
    table["n_games"] = (table["support"] * len(transactions)).round().astype(int)

    plot_top_rules(tag_rules, out_dir / "rules_top15_lift.png", "Top 15 luật tag theo lift")
    plot_top_rules(hp_rules, out_dir / "rules_high_positive_top15.png",
                   f"Tổ hợp tag → ≥{HIGH_POSITIVE_RATIO:.0%} review tích cực")

    base_rate = len(high_positive_ids & set(transactions_by_game)) / max(len(transactions), 1)
    return {"transactions": len(transactions), "min_support": min_support, "itemsets": len(itemsets),
            "tag_rules": len(tag_rules), "high_positive_rules": len(hp_rules),
            "high_positive_base_rate": round(base_rate, 3)}, table.reset_index(drop=True)


if __name__ == "__main__":
    from sqlalchemy.dialects.postgresql import ARRAY, TEXT

    from mining.prepare_data import load_games, load_tag_transactions, save_table

    games = load_games()
    high_positive = set(games.index[games["is_high_positive"]])  # >= 50 review và >= 90% khen (mart)
    summary, table = run(load_tag_transactions(top_k=10), high_positive,
                         min_support=float(sys.argv[1]) if len(sys.argv) > 1 else 0.03)
    save_table(table, "tag_rules", dtype={"antecedents": ARRAY(TEXT), "consequents": ARRAY(TEXT)})
    print(summary, f"-> mining.tag_rules ({len(table)} luật)")
    print(pd.read_csv(OUT_DIR / "rules.csv").head(10).to_string())
    print(pd.read_csv(OUT_DIR / "rules_high_positive.csv").head(10).to_string())
