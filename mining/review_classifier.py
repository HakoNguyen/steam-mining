"""
Câu hỏi 9 - Phân loại văn bản review (khen/chê) trong dw.fact_game_reviews (đã khử trùng).
TF-IDF + LogisticRegression so với Naive Bayes (ComplementNB); lớp lệch -> báo F1-macro, không chỉ accuracy.

    python mining/review_classifier.py
"""
import json
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import make_pipeline

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

OUT_DIR = BASE_DIR / "mining" / "outputs"
RANDOM_STATE = 42


def make_tfidf():
    return TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, max_features=50_000, sublinear_tf=True)


def run(reviews, out_dir=OUT_DIR):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = reviews[reviews["text"].str.strip().str.len() > 0]
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"], df["voted_up"], test_size=0.2, stratify=df["voted_up"], random_state=RANDOM_STATE)

    models = {
        "logreg": make_pipeline(make_tfidf(), LogisticRegression(class_weight="balanced", max_iter=1000)),
        "naive_bayes": make_pipeline(make_tfidf(), ComplementNB()),  # MultinomialNB đoán toàn lớp đa số khi lệch 87/13
    }
    metrics = {"n_reviews": len(df), "positive_rate": round(float(df["voted_up"].mean()), 3),
               "baseline_majority": {"accuracy": round(max(y_test.mean(), 1 - y_test.mean()), 4),
                                     "f1_macro": round(f1_score(y_test, [int(y_train.mean() >= .5)] * len(y_test),
                                                                average="macro"), 4)}}
    for name, model in models.items():
        pred = model.fit(X_train, y_train).predict(X_test)
        metrics[name] = {
            "accuracy": round(accuracy_score(y_test, pred), 4),
            "f1_macro": round(f1_score(y_test, pred, average="macro"), 4),
            "confusion_matrix [[TN, FP], [FN, TP]]": confusion_matrix(y_test, pred).tolist(),
            "report": classification_report(y_test, pred, target_names=["chê", "khen"], output_dict=True,
                                            zero_division=0),
        }
    best = max(models, key=lambda n: metrics[n]["f1_macro"])
    metrics["best_model"] = best
    (out_dir / "review_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    joblib.dump(models[best], out_dir / "review_clf.joblib")

    # từ/cụm từ đẩy mạnh nhất về khen/chê (hệ số LogisticRegression) -> gợi ý cho câu hỏi 10
    tfidf, lr = models["logreg"].named_steps.values()
    coef = pd.Series(lr.coef_[0], index=tfidf.get_feature_names_out()).sort_values()
    top = pd.concat([coef.head(15), coef.tail(15)])
    fig, ax = plt.subplots(figsize=(8, 9))
    ax.barh(top.index, top.values, color=["#C44E52" if v < 0 else "#55A868" for v in top.values])
    ax.set_title("Từ khoá quyết định: chê (đỏ) / khen (xanh)")
    fig.tight_layout()
    fig.savefig(out_dir / "review_top_terms.png", dpi=120)
    plt.close(fig)
    return metrics


if __name__ == "__main__":
    from mining.prepare_data import load_reviews

    reviews = load_reviews()
    if reviews.empty:
        sys.exit("Chưa có review trong dw.fact_game_reviews - DAG universe đã crawl review chưa (cần VPN)?")
    m = run(reviews)
    print(json.dumps({k: v for k, v in m.items() if k not in ("logreg", "naive_bayes")}, indent=2))
    for name in ("logreg", "naive_bayes"):
        print(name, {k: m[name][k] for k in ("accuracy", "f1_macro")})
