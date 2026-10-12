import numpy as np
import pandas as pd

from mining.prepare_data import add_features


def test_add_features():
    df = pd.DataFrame({
        "positive": [90.0, 3.0], "negative": [10.0, 1.0],
        "owners_min": [0.0, 1_000_000.0], "owners_max": [20_000.0, 2_000_000.0],
        "avg_playtime_forever": [0.0, 120.0], "median_playtime_forever": [0.0, 60.0],
        "avg_ccu": [5.0, np.nan], "peak_ccu": [9.0, np.nan],
        "release_date_iso": ["2020-03-15", None],
    })
    out = add_features(df)
    assert out["positive_ratio"].iloc[0] == 0.9
    assert np.isnan(out["positive_ratio"].iloc[1])        # < 50 review -> không tin cậy
    assert out["owners_mid"].tolist() == [10_000, 1_500_000]
    assert np.isnan(out["median_playtime_forever"].iloc[0])  # playtime 0 = thiếu
    assert out["log_owners_mid"].iloc[0] == np.log1p(10_000)
    assert out["release_month"].iloc[0] == 3


def test_association_rules(tmp_path):
    from mining.association_rules import run

    tx = {i: ["Roguelike", "Indie", "Pixel Graphics"] if i % 2 else ["FPS", "Shooter"] for i in range(40)}
    summary = run(tx, high_positive_ids={i for i in range(40) if i % 2}, out_dir=tmp_path, min_support=0.2)
    assert summary["high_positive_rules"] > 0 and summary["tag_rules"] > 0
    hp = pd.read_csv(tmp_path / "rules_high_positive.csv")
    assert set(hp["consequents"]) == {"HIGH_POSITIVE"}
    assert (hp["lift"] > 1.9).all()   # roguelike luôn HIGH_POSITIVE, tỷ lệ nền 50% -> lift 2
    for f in ["rules.csv", "rules_top15_lift.png", "rules_high_positive_top15.png"]:
        assert (tmp_path / f).exists()


def test_kmeans(tmp_path):
    from mining.kmeans_clustering import run

    rng = np.random.default_rng(0)
    # 2 nhóm tách bạch: game lớn miễn phí vs game nhỏ trả phí
    big = pd.DataFrame({"log_owners_mid": rng.normal(17, .2, 30), "log_avg_ccu": rng.normal(10, .2, 30),
                        "price_vnd": 0.0, "positive_ratio": rng.normal(.7, .02, 30)})
    small = pd.DataFrame({"log_owners_mid": rng.normal(12, .2, 30), "log_avg_ccu": rng.normal(4, .2, 30),
                          "price_vnd": 200_000.0, "positive_ratio": rng.normal(.95, .02, 30)})
    games = pd.concat([big, small], ignore_index=True)
    games[["owners_mid", "avg_ccu"]] = np.expm1(games[["log_owners_mid", "log_avg_ccu"]])
    metrics, profile = run(games, out_dir=tmp_path, k_range=range(2, 6), min_k=2)
    assert metrics["best_k"] == 2
    assert sorted(profile["n_games"]) == [30, 30]
    for f in ["kmeans.joblib", "elbow_silhouette.png", "clusters_pca.png", "cluster_profile.csv"]:
        assert (tmp_path / f).exists()


def test_cart(tmp_path):
    from mining.cart_tree import build_features, primary_genre, run

    n = 200
    rng = np.random.default_rng(0)
    multi = rng.integers(0, 2, n).astype(bool)
    games = pd.DataFrame({
        "owners_mid": np.where(multi, 5e6, 1e6), "positive": rng.integers(0, 1000, n), "negative": 0,  # multiplayer -> owners cao
        "release_date_iso": pd.date_range("2015-01-01", periods=n, freq="7D").date,
        "publisher_name": rng.choice(["A", "B", None], n),
        "price_vnd": rng.choice([0.0, 100_000.0], n), "languages_count": rng.integers(1, 20, n),
        "release_month": rng.integers(1, 13, n), "is_free": False,
        "has_multiplayer": multi, "has_coop": False,
    })
    genres = pd.DataFrame({"Action": 1, "RPG": (np.arange(n) % 2), "Indie": 1}, index=games.index)
    assert primary_genre(genres.head(2)).tolist() == ["Other", "Other"]   # nhóm < MIN_GENRE_SIZE
    assert primary_genre(genres).tolist()[:2] == ["Action", "RPG"]        # RPG hiếm hơn Action, bỏ Indie
    X, y, _ = build_features(games, genres, {i: ["Co-op"] for i in range(n) if multi[i]})
    assert "owners_mid" not in X and "publisher_prior_games" in X
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
