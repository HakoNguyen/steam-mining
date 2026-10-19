"""
Task 6.2 - Phân cụm K-Means game theo mức phổ biến, giá, đánh giá (câu hỏi 7).
Chọn k = 3..10 theo silhouette (k=2 chỉ tách free/paid); tên cụm tự đặt từ trung vị so với toàn tập
(xem lại cluster_profile.csv). Kết quả ghi vào mining.game_clusters cho Copilot.

    python mining/kmeans_clustering.py
"""
import json
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

OUT_DIR = BASE_DIR / "mining" / "outputs"
# playtime bị loại: SteamSpy luôn trả 0. Game trả phí không có giá VN / < 50 review bị loại khỏi phân cụm
FEATURES = ["log_owners", "log_avg_ccu", "log_price", "positive_ratio"]
PROFILE_COLS = ["owners_mid", "avg_ccu", "price_vnd", "positive_ratio"]
RANDOM_STATE = 42


def label_clusters(profile, df):
    """Tên cụm từ trung vị của cụm so với toàn tập: giá (miễn phí / rẻ / cao so với trung vị game trả phí),
    CCU (trên / dưới trung vị) và tỷ lệ khen (chênh > 2 điểm % mới gọi cao / thấp, còn lại "trung bình")."""
    paid = df.loc[df["price_vnd"] > 0, "price_vnd"].median()
    ccu, ratio = df["avg_ccu"].median(), df["positive_ratio"].median()

    def label(r):
        price = "Miễn phí" if r["price_vnd"] == 0 else ("Trả phí giá rẻ" if r["price_vnd"] <= paid else "Trả phí giá cao")
        players = "đông người chơi" if r["avg_ccu"] > ccu else "ít người chơi"
        praise = ("khen cao" if r["positive_ratio"] > ratio + 0.02 else
                  "khen thấp" if r["positive_ratio"] < ratio - 0.02 else "khen trung bình")
        return " · ".join([price, players, praise])

    labels = profile.apply(label, axis=1)
    dup = labels.duplicated(keep=False)
    return labels.where(~dup, labels + " (cụm " + labels.index.astype(str) + ")")


def run(games, out_dir=OUT_DIR, k_range=range(2, 11), min_k=3):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = games.dropna(subset=FEATURES)

    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURES])

    ks = [k for k in k_range if k < len(df)]
    models = {k: KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(X) for k in ks}
    inertia = {k: m.inertia_ for k, m in models.items()}
    silhouette = {k: silhouette_score(X, m.labels_, random_state=RANDOM_STATE) for k, m in models.items()}
    # k=2 chỉ tách miễn phí / trả phí (log giá 2 đỉnh: 0 và ~12) -> chọn silhouette cao nhất với k >= min_k
    best_k = max((k for k in silhouette if k >= min_k), key=silhouette.get)
    model = models[best_k]
    df = df.assign(cluster=model.labels_)

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.plot(ks, [inertia[k] for k in ks], "o-", color="#4C72B0")
    ax1.set_xlabel("k")
    ax1.set_ylabel("Inertia (elbow)", color="#4C72B0")
    ax2 = ax1.twinx()
    ax2.plot(ks, [silhouette[k] for k in ks], "s--", color="#DD8452")
    ax2.set_ylabel("Silhouette", color="#DD8452")
    ax1.axvline(best_k, color="grey", linestyle=":")
    ax1.set_title(f"Chọn k: elbow + silhouette (chọn k={best_k})")
    fig.tight_layout()
    fig.savefig(out_dir / "elbow_silhouette.png", dpi=120)
    plt.close(fig)

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    xy = pca.fit_transform(X)
    fig, ax = plt.subplots(figsize=(8, 6))
    for c in range(best_k):
        ax.scatter(*xy[df["cluster"] == c].T, s=10, alpha=0.6, label=f"Cụm {c}")
    centers = pca.transform(model.cluster_centers_)
    ax.scatter(*centers.T, marker="X", s=150, c="black")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.0%})")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.0%})")
    ax.set_title(f"K-Means k={best_k} trên PCA 2D")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "clusters_pca.png", dpi=120)
    plt.close(fig)

    profile = df.groupby("cluster")[PROFILE_COLS].median().round(3)
    profile.insert(0, "n_games", df["cluster"].value_counts().sort_index())
    profile.insert(0, "cluster_label", label_clusters(profile, df))
    if "game_title" in df:
        profile["examples"] = df.sort_values("owners_mid", ascending=False).groupby("cluster")["game_title"] \
            .apply(lambda s: "; ".join(s.head(5)))
    profile.to_csv(out_dir / "cluster_profile.csv", encoding="utf-8-sig")
    df = df.assign(cluster_label=df["cluster"].map(profile["cluster_label"]))
    df[["cluster", "cluster_label"]].to_csv(out_dir / "game_clusters.csv", encoding="utf-8-sig")

    joblib.dump({"scaler": scaler, "model": model, "features": FEATURES}, out_dir / "kmeans.joblib")
    metrics = {"n_games": len(df), "features": FEATURES, "best_k": best_k,
               "silhouette": {k: round(v, 4) for k, v in silhouette.items()},
               "inertia": {k: round(v, 1) for k, v in inertia.items()}}
    (out_dir / "kmeans_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics, profile, df


if __name__ == "__main__":
    from mining.prepare_data import load_games, save_table

    metrics, profile, df = run(load_games())
    save_table(df.reset_index()[["game_id", "cluster", "cluster_label"]].rename(columns={"cluster": "cluster_id"}),
               "game_clusters")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(profile.to_string())
