"""
Câu hỏi 10 (mở rộng) - Người chơi phàn nàn về những nhóm vấn đề nào?
NMF trên TF-IDF của review chê (voted_up = 0); số chủ đề chọn theo coherence (UMass trung bình);
tên chủ đề đặt SAU khi xem negative_topics.csv.

    python mining/negative_topics.py
"""
import json
import sys
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

OUT_DIR = BASE_DIR / "mining" / "outputs"
RANDOM_STATE = 42
MIN_WORDS = 5       # review quá ngắn ("no", "bad") không mang chủ đề
TOP_WORDS = 10
# từ xuất hiện ở mọi review game, không phân biệt chủ đề
DOMAIN_STOP_WORDS = {"game", "games", "play", "playing", "played", "just", "like", "really", "don", "doesn",
                     "didn", "isn", "ve", "ll", "people", "thing", "things", "make", "makes", "time", "good",
                     "bad", "way", "lot", "want", "got", "say", "know", "think", "steam", "review", "recommend"}


def umass_coherence(top_idx, X_bin):
    """UMass trung bình trên các cặp từ top: log((D(wi, wj) + 1) / D(wj)); càng gần 0 càng mạch lạc."""
    df = np.asarray(X_bin.sum(axis=0)).ravel()
    scores = []
    for words in top_idx:
        for i, j in combinations(words, 2):
            co = X_bin[:, i].multiply(X_bin[:, j]).sum()
            scores.append(np.log((co + 1) / max(df[j], 1)))
    return float(np.mean(scores))


def run(texts, out_dir=OUT_DIR, k_range=range(4, 13), game_ids=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = pd.Series(list(texts), index=game_ids)
    texts = texts[texts.str.split().str.len() >= MIN_WORDS]

    tfidf = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS | DOMAIN_STOP_WORDS), token_pattern=r"(?u)\b[a-z]{3,}\b",
                            lowercase=True, min_df=5, max_df=0.5, max_features=5_000, sublinear_tf=True)
    X = tfidf.fit_transform(texts)
    vocab = tfidf.get_feature_names_out()
    X_bin = (X > 0).astype(int).tocsc()

    models, coherence = {}, {}
    for k in k_range:
        models[k] = NMF(n_components=k, init="nndsvd", random_state=RANDOM_STATE, max_iter=400).fit(X)
        coherence[k] = umass_coherence(np.argsort(-models[k].components_, axis=1)[:, :TOP_WORDS], X_bin)
    best_k = max(coherence, key=coherence.get)
    nmf = models[best_k]

    W = nmf.transform(X)
    topic = W.argmax(axis=1)
    has_topic = W.max(axis=1) > 0
    rows = []
    for t in range(best_k):
        mask = (topic == t) & has_topic
        strength = np.where(mask, W[:, t], -1)
        examples = [texts.iloc[i][:160].replace("\n", " ") for i in np.argsort(-strength)[:3]]
        rows.append({"topic": t, "top_words": ", ".join(vocab[np.argsort(-nmf.components_[t])[:TOP_WORDS]]),
                     "n_reviews": int(mask.sum()), "share": round(mask.sum() / has_topic.sum(), 4),
                     "examples": " | ".join(examples)})
    topics = pd.DataFrame(rows).sort_values("share", ascending=False)
    topics.to_csv(out_dir / "negative_topics.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(10, 0.55 * best_k + 1.5))
    shown = topics.iloc[::-1]
    ax.barh([f"#{t}: {w.split(', ')[0:5]}".replace("'", "") for t, w in zip(shown["topic"], shown["top_words"])],
            shown["share"], color="#C44E52")
    ax.set_xlabel("tỷ lệ review chê")
    ax.set_title(f"Chủ đề phàn nàn trong review tiêu cực (NMF, k={best_k})")
    fig.tight_layout()
    fig.savefig(out_dir / "negative_topics.png", dpi=120)
    plt.close(fig)

    if game_ids is not None:
        pd.DataFrame({"game_id": texts.index[has_topic], "topic": topic[has_topic]}) \
            .to_csv(out_dir / "negative_review_topics.csv", index=False)

    metrics = {"n_reviews": int(has_topic.sum()), "vocab": len(vocab), "best_k": best_k,
               "umass_coherence": {str(k): round(v, 4) for k, v in coherence.items()}}
    (out_dir / "negative_topics_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics, topics


if __name__ == "__main__":
    from mining.prepare_data import load_reviews

    reviews = load_reviews()
    negative = reviews[reviews["voted_up"] == 0]
    metrics, topics = run(negative["text"], game_ids=negative["game_id"])
    print(json.dumps(metrics, indent=2))
    print(topics.drop(columns="examples").to_string(index=False))
