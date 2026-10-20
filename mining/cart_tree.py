"""
Task 6.3 - Cây quyết định CART dự đoán game "hiệu suất cao trong thể loại" (câu hỏi 8).
Nhãn: owners_mid thuộc top 25% trong thể loại chính (hòa owners -> xếp theo tổng review). Đặc trưng CHỈ có trước phát hành
(không dùng CCU, review, owners, playtime -> tránh leakage).

    python mining/cart_tree.py
"""
import json
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

OUT_DIR = BASE_DIR / "mining" / "outputs"
META_GENRES = {"Indie", "Free To Play", "Free to Play", "Early Access"}  # không phải thể loại gameplay
MIN_GENRE_SIZE = 20     # thể loại ít game hơn -> gộp "Other" để phân vị có nghĩa
TOP_QUANTILE = 0.75
N_TOP_TAGS = 20
RANDOM_STATE = 42


def primary_genre(genres):
    """Thể loại chính = genre gameplay hiếm nhất (cụ thể nhất) của game, vd Action+RPG -> RPG."""
    gameplay = genres.drop(columns=[c for c in genres if c in META_GENRES])
    size = gameplay.sum()
    primary = gameplay.apply(lambda row: size[row == 1].idxmin() if row.any() else "Other", axis=1)
    counts = primary.value_counts()
    return primary.where(primary.map(counts) >= MIN_GENRE_SIZE, "Other")


def build_features(games, genres, tag_tx):
    """-> X (đặc trưng trước phát hành), y (top 25% owners trong thể loại chính), thể loại chính."""
    df = games.dropna(subset=["owners_mid", "release_date"]).join(genres, how="inner")
    df = df.assign(primary_genre=primary_genre(df[genres.columns]))

    # owners SteamSpy là khoảng rời rạc (1-2M, 2-5M...) -> nhiều game trùng mốc phân vị;
    # xếp hạng trong thể loại theo owners, hòa thì theo tổng review (proxy doanh số) -> đúng top 25%
    ranked = df.assign(reviews=df["total_reviews"].fillna(0)).sort_values(["owners_mid", "reviews"])         .groupby("primary_genre")
    pct = (ranked.cumcount() + 1) / ranked["owners_mid"].transform("size")
    y = (pct.reindex(df.index) > TOP_QUANTILE).astype(int)

    tag_counts = pd.Series([t for tags in tag_tx.values() for t in tags]).value_counts()
    top_tags = tag_counts.head(N_TOP_TAGS).index
    tag_onehot = pd.DataFrame([[int(t in tag_tx.get(g, [])) for t in top_tags] for g in df.index],
                              index=df.index, columns=[f"tag_{t}" for t in top_tags])

    X = pd.concat([
        df[["num_languages", "release_month"]].astype(float),
        df[["is_free", "is_multiplayer", "is_coop"]].eq(True).astype(int),  # NULL -> 0
        # mart đếm theo publisher_name nên game không rõ publisher bị gộp chung 1 nhóm -> 0
        df["publisher_prior_games"].where(df["publisher_name"].notna(), 0),
        df[genres.columns].add_prefix("genre_"),
        tag_onehot,
    ], axis=1).fillna(0)
    X["price_vnd"] = df["price_vnd"]  # NaN = không bán ở VN; cây sklearn >= 1.3 tự xử lý giá trị thiếu
    return X, y, df["primary_genre"]


def run(X, y, out_dir=OUT_DIR, depths=(3, 4, 5, 6)):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        DecisionTreeClassifier(class_weight="balanced", min_samples_leaf=10, random_state=RANDOM_STATE),
        {"max_depth": list(depths)}, scoring="f1", cv=cv)
    search.fit(X_train, y_train)
    tree = search.best_estimator_
    pred = tree.predict(X_test)
    baselines = {name: DummyClassifier(strategy=name, random_state=RANDOM_STATE).fit(X_train, y_train).predict(X_test)
                 for name in ("most_frequent", "stratified")}  # stratified = đoán ngẫu nhiên theo tỷ lệ lớp

    metrics = {
        "n_games": len(X), "positive_rate": round(float(y.mean()), 3), "n_features": X.shape[1],
        "best_max_depth": search.best_params_["max_depth"],
        "cv_f1_by_depth": dict(zip(map(str, depths), search.cv_results_["mean_test_score"].round(4).tolist())),
        "test": {
            "accuracy": round(accuracy_score(y_test, pred), 4),
            "precision": round(precision_score(y_test, pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, pred, zero_division=0), 4),
            "f1": round(f1_score(y_test, pred, zero_division=0), 4),
            "roc_auc": round(roc_auc_score(y_test, tree.predict_proba(X_test)[:, 1]), 4),
            "confusion_matrix [[TN, FP], [FN, TP]]": confusion_matrix(y_test, pred).tolist(),
        },
        **{f"baseline_{name}": {"accuracy": round(accuracy_score(y_test, b), 4),
                                "f1": round(f1_score(y_test, b, zero_division=0), 4)}
           for name, b in baselines.items()},
    }
    (out_dir / "cart_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    joblib.dump({"model": tree, "features": list(X.columns)}, out_dir / "cart.joblib")
    (out_dir / "tree_rules.txt").write_text(export_text(tree, feature_names=list(X.columns)), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(22, 10))
    plot_tree(tree, feature_names=list(X.columns), class_names=["thường", "top 25%"],
              filled=True, rounded=True, fontsize=8, ax=ax)
    fig.savefig(out_dir / "tree.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    imp = pd.Series(tree.feature_importances_, index=X.columns).sort_values()
    imp = imp[imp > 0].tail(15)
    fig, ax = plt.subplots(figsize=(8, 0.4 * len(imp) + 1.5))
    ax.barh(imp.index, imp.values, color="#55A868")
    ax.set_title("Mức quan trọng đặc trưng (CART)")
    fig.tight_layout()
    fig.savefig(out_dir / "feature_importance.png", dpi=120)
    plt.close(fig)
    return metrics


if __name__ == "__main__":
    from mining.prepare_data import load_games, load_genres, load_tag_transactions

    X, y, genre = build_features(load_games(), load_genres(), load_tag_transactions(top_k=10))
    print(pd.crosstab(genre, y).to_string())
    print(json.dumps(run(X, y), indent=2, ensure_ascii=False))
    print((OUT_DIR / "tree_rules.txt").read_text(encoding="utf-8"))
