import numpy as np
import pandas as pd

from mining.prepare_data import add_features


def test_add_features():
    df = pd.DataFrame({"is_free": [True, False, False], "price_vnd": [np.nan, 165_000.0, np.nan]})
    out = add_features(df)
    assert out["price_vnd"].iloc[0] == 0 and out["log_price"].iloc[0] == 0   # miễn phí -> giá 0
    assert out["log_price"].iloc[1] == np.log1p(165_000)
    assert np.isnan(out["log_price"].iloc[2])                                # không bán ở VN -> thiếu, không phải 0


def test_association_rules(tmp_path):
    from mining.association_rules import run

    tx = {i: ["Roguelike", "Indie", "Pixel Graphics"] if i % 2 else ["FPS", "Shooter"] for i in range(40)}
    summary, table = run(tx, high_positive_ids={i for i in range(40) if i % 2}, out_dir=tmp_path, min_support=0.2)
    assert summary["high_positive_rules"] > 0 and summary["tag_rules"] > 0
    assert len(table) == summary["tag_rules"] + summary["high_positive_rules"]
    hp_row = table[table["is_high_positive"]].iloc[0]
    assert hp_row["consequents"] == ["HIGH_POSITIVE"] and hp_row["n_games"] == 20
    hp = pd.read_csv(tmp_path / "rules_high_positive.csv")
    assert set(hp["consequents"]) == {"HIGH_POSITIVE"}
    assert (hp["lift"] > 1.9).all()   # roguelike luôn HIGH_POSITIVE, tỷ lệ nền 50% -> lift 2
    for f in ["rules.csv", "rules_top15_lift.png", "rules_high_positive_top15.png"]:
        assert (tmp_path / f).exists()


def test_kmeans(tmp_path):
    from mining.kmeans_clustering import run

    rng = np.random.default_rng(0)
    # 2 nhóm tách bạch: game lớn miễn phí vs game nhỏ trả phí
    big = pd.DataFrame({"log_owners": rng.normal(17, .2, 30), "log_avg_ccu": rng.normal(10, .2, 30),
                        "is_free": True, "price_vnd": np.nan, "positive_ratio": rng.normal(.7, .02, 30)})
    small = pd.DataFrame({"log_owners": rng.normal(12, .2, 30), "log_avg_ccu": rng.normal(4, .2, 30),
                          "is_free": False, "price_vnd": 200_000.0, "positive_ratio": rng.normal(.95, .02, 30)})
    unpriced = small.head(5).assign(price_vnd=np.nan)   # không có giá VN -> không phân cụm
    games = add_features(pd.concat([big, small, unpriced], ignore_index=True))
    games[["owners_mid", "avg_ccu"]] = np.expm1(games[["log_owners", "log_avg_ccu"]])
    metrics, profile, clustered = run(games, out_dir=tmp_path, k_range=range(2, 6), min_k=2)
    assert metrics["best_k"] == 2 and len(clustered) == 60
    assert sorted(profile["n_games"]) == [30, 30]
    assert set(profile["cluster_label"]) == {"Miễn phí · đông người chơi · khen thấp",
                                             "Trả phí giá rẻ · ít người chơi · khen cao"}
    for f in ["kmeans.joblib", "elbow_silhouette.png", "clusters_pca.png", "cluster_profile.csv"]:
        assert (tmp_path / f).exists()


def test_cart(tmp_path):
    from mining.cart_tree import build_features, primary_genre, run

    n = 200
    rng = np.random.default_rng(0)
    multi = rng.integers(0, 2, n).astype(bool)
    games = pd.DataFrame({
        "owners_mid": np.where(multi, 5e6, 1e6), "total_reviews": rng.integers(0, 1000, n),  # multiplayer -> owners cao
        "release_date": pd.date_range("2015-01-01", periods=n, freq="7D").date,
        "publisher_name": rng.choice(["A", "B", None], n), "publisher_prior_games": rng.integers(0, 5, n),
        "price_vnd": rng.choice([np.nan, 100_000.0], n), "num_languages": rng.integers(1, 20, n),
        "release_month": rng.integers(1, 13, n), "is_free": False,
        "is_multiplayer": multi, "is_coop": False,
    })
    genres = pd.DataFrame({"Action": 1, "RPG": (np.arange(n) % 2), "Indie": 1}, index=games.index)
    assert primary_genre(genres.head(2)).tolist() == ["Other", "Other"]   # nhóm < MIN_GENRE_SIZE
    assert primary_genre(genres).tolist()[:2] == ["Action", "RPG"]        # RPG hiếm hơn Action, bỏ Indie
    X, y, _ = build_features(games, genres, {i: ["Co-op"] for i in range(n) if multi[i]})
    assert "owners_mid" not in X and "publisher_prior_games" in X
    assert (X.loc[games["publisher_name"].isna(), "publisher_prior_games"] == 0).all()
    assert X["price_vnd"].isna().any()   # giá thiếu giữ NaN, không thành 0
    metrics = run(X, y, out_dir=tmp_path, depths=(2, 3))
    assert metrics["test"]["f1"] > metrics["baseline_most_frequent"]["f1"]
    for f in ["cart.joblib", "tree.png", "tree_rules.txt", "feature_importance.png", "cart_metrics.json"]:
        assert (tmp_path / f).exists()


def test_review_classifier(tmp_path):
    from mining.review_classifier import run

    rng = np.random.default_rng(0)
    good = ["great game love it", "amazing fun story", "best game ever fun", "love the music great"]
    bad = ["terrible bugs refund", "crashes constantly awful", "boring waste of money", "awful servers refund"]
    up = rng.random(300) < 0.75   # lệch lớp như review Steam thật
    reviews = pd.DataFrame({"text": [rng.choice(good if u else bad) for u in up] + ["  "], "voted_up": [*up.astype(int), 1]})
    metrics = run(reviews, out_dir=tmp_path)
    assert metrics["n_reviews"] == 300                      # review rỗng bị loại
    assert metrics[metrics["best_model"]]["f1_macro"] > 0.95
    assert metrics["baseline_majority"]["f1_macro"] < 0.5
    for f in ["review_metrics.json", "review_clf.joblib", "review_top_terms.png"]:
        assert (tmp_path / f).exists()


def test_negative_topics(tmp_path):
    from mining.negative_topics import run

    rng = np.random.default_rng(0)
    # 10 từ/nhóm = TOP_WORDS, để coherence đo đúng từng nhóm
    vocab = [["crash", "launch", "freeze", "driver", "error", "bug", "fps", "lag", "stutter", "server"],
             ["money", "price", "refund", "expensive", "microtransaction", "pay", "cash", "wallet", "cost", "dlc"],
             ["boring", "repetitive", "grind", "tedious", "dull", "slow", "shallow", "bland", "story", "quest"]]
    texts = [" ".join(rng.choice(vocab[i % 3], 8)) for i in range(150)] + ["too short"]
    # cố định k: UMass không phạt chủ đề bị bỏ sót (k=2 bỏ cả nhóm money vẫn mạch lạc hơn)
    metrics, topics = run(texts, out_dir=tmp_path, k_range=[3])
    assert metrics["n_reviews"] == 150      # review < 5 từ bị loại
    for words in vocab:   # mỗi chủ đề tìm được trùng đúng 1 nhóm từ
        assert any(set(t.split(", ")) == set(words) for t in topics["top_words"])
    for f in ["negative_topics.csv", "negative_topics.png", "negative_topics_metrics.json"]:
        assert (tmp_path / f).exists()
