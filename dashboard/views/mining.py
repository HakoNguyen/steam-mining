"""Trang Khai phá dữ liệu: kết quả 5 kỹ thuật trong mining/ (Apriori, K-Means, CART, phân loại review, NMF),
mỗi kỹ thuật một tab gồm câu hỏi, phương pháp, chỉ số đánh giá và biểu đồ. Nguồn dữ liệu: xem lib/mining.py."""
import pandas as pd
import streamlit as st

from lib import fmt, metabase, mining
from lib import mining_charts as mc
from lib.i18n import lang, t, tab_labels
from lib.theme import palette, show

p = palette()
MIN_SUPPORT = 0.03  # mặc định của mining/association_rules.py
# Nhãn phân khúc do mining/kmeans_clustering.py ghép từ các mảnh cố định -> dịch từng mảnh
CLUSTER_WORDS = {"Trả phí giá rẻ": "Paid, low price", "Trả phí giá cao": "Paid, high price", "Miễn phí": "Free-to-play",
                 "đông người chơi": "many players", "ít người chơi": "few players", "khen cao": "well reviewed",
                 "khen thấp": "poorly reviewed", "khen trung bình": "average reviews", "cụm": "cluster"}


def cluster_name(label):
    if lang() == "vi":
        return label
    for vi, en in CLUSTER_WORDS.items():
        label = label.replace(vi, en)
    return label


def card(title, caption, fig=None, table=None, body=None):
    with st.container(border=True):
        st.markdown(f"#### {title}")
        if caption:
            st.caption(caption)
        if body:
            body()
        if fig is not None:
            show(fig)
        if table is not None:
            with st.expander(t("table_view")):
                st.dataframe(table, hide_index=True, width="stretch")


def intro(question_key, method_key, **kw):
    st.markdown(f"**{t('mn_question')}** {t(question_key)}")
    st.caption(f"**{t('mn_method')}** {t(method_key, **kw)}")


def missing(script):
    st.info(t("mn_missing", cmd=f"python -m mining.{script}"), icon=":material/hourglass_empty:")


def takeaways(lines):
    if lines:
        with st.container(border=True):
            st.markdown(f"**{t('insights')}**")
            st.markdown("\n".join(f"- {s}" for s in lines))


# ---------------------------------------------------------------- dữ liệu
try:
    rules_hp = metabase.run("[Streamlit] Mining luật khen cao")
    rules_tags = metabase.run("[Streamlit] Mining luật giữa các tag")
    rules_info = metabase.run("[Streamlit] Mining tổng quan luật").iloc[0]
    clusters = metabase.run("[Streamlit] Mining phân cụm game")
    db_ok = not clusters.empty and not rules_hp.empty
except Exception:  # bảng mining chưa có (chưa chạy script) hoặc Metabase không chạy
    db_ok = False

km, profile = mining.load_json("kmeans_metrics.json"), mining.load_csv("cluster_profile.csv")
cart = mining.load_json("cart_metrics.json")
clf = mining.load_json("review_metrics.json")
nmf, topics = mining.load_json("negative_topics_metrics.json"), mining.load_csv("negative_topics.csv")

st.title(t("nav_mining"))
updated = mining.updated_at()
st.caption(t("mn_caption") + (" · " + t("mn_updated", d=f"{updated:%d/%m/%Y %H:%M}") if updated else ""))

# ---------------------------------------------------------------- tổng quan 5 kỹ thuật
cols = st.columns(5)
overview = [
    ("mn_t_apriori", fmt.num(rules_info["n_high_positive_rules"]) if db_ok else "—", "mn_o_apriori"),
    ("mn_t_kmeans", f"k = {km['best_k']}" if km else "—", "mn_o_kmeans"),
    ("mn_t_cart", f"F1 {fmt.num(cart['test']['f1'], 3)}" if cart else "—", "mn_o_cart"),
    ("mn_t_clf", f"F1 {fmt.num(clf[clf['best_model']]['f1_macro'], 3)}" if clf else "—", "mn_o_clf"),
    ("mn_t_nmf", fmt.num(nmf["best_k"]) if nmf else "—", "mn_o_nmf"),
]
for col, (name, value, desc) in zip(cols, overview):
    col.metric(t(name), value, border=True, help=t(desc))

tabs = st.tabs(tab_labels("mn_tab", ["mn_t_apriori", "mn_t_kmeans", "mn_t_cart", "mn_t_clf", "mn_t_nmf"]),
               key="mn_tab", on_change="rerun")

# ---------------------------------------------------------------- Apriori
with tabs[0]:
    intro("mn_q_apriori", "mn_m_apriori", s=fmt.pct(MIN_SUPPORT * 100, 0))
    if not db_ok:
        missing("association_rules")
    else:
        base = float(rules_info["base_rate"])
        k = st.columns(4)
        k[0].metric(t("mn_k_transactions"), fmt.num(rules_info["n_transactions"]), border=True, help=t("mn_k_transactions_help"))
        k[1].metric(t("mn_k_rules"), fmt.num(rules_info["n_rules"]), border=True, help=t("mn_k_rules_help", s=fmt.pct(MIN_SUPPORT * 100, 0)))
        k[2].metric(t("mn_k_hp_rules"), fmt.num(rules_info["n_high_positive_rules"]), border=True, help=t("mn_k_hp_rules_help"))
        k[3].metric(t("mn_k_base_rate"), fmt.pct(base * 100), border=True, help=t("mn_k_base_rate_help"))

        top = rules_hp.sort_values("lift", ascending=False)
        multi = top[top["n_tags"] > 1]
        lines = [t("mn_i_apriori_top", combo=top.iloc[0]["combo"], c=fmt.pct(top.iloc[0]["confidence"] * 100),
                   x=fmt.num(top.iloc[0]["lift"], 2), b=fmt.pct(base * 100))]
        if not multi.empty:
            m = multi.sort_values("n_games_with_combo").iloc[0]
            lines.append(t("mn_i_apriori_niche", combo=m["combo"], n=fmt.num(m["n_games_with_combo"]),
                           c=fmt.pct(m["confidence"] * 100)))
        lines.append(t("mn_i_apriori_pair", a=rules_tags.iloc[0]["antecedent"], b=rules_tags.iloc[0]["consequent"],
                       c=fmt.pct(rules_tags.iloc[0]["confidence"] * 100), x=fmt.num(rules_tags.iloc[0]["lift"], 1)))
        takeaways(lines)

        card(t("mn_c_hp_title"), t("mn_c_hp_cap"), mc.rules_confidence(rules_hp, base, p),
             rules_hp.assign(confidence=(rules_hp["confidence"] * 100).round(1), support=(rules_hp["support"] * 100).round(1),
                             lift=rules_hp["lift"].round(2))
             .rename(columns={"combo": t("mn_col_combo"), "n_tags": t("mn_col_n_tags"), "confidence": t("mn_col_conf"),
                              "lift": "Lift", "support": t("mn_col_support"), "n_high_positive": t("mn_col_n_hp"),
                              "n_games_with_combo": t("mn_col_n_combo")}))

        def pairs_table():
            d = rules_tags.head(20).assign(rule=lambda x: x["antecedent"] + "  →  " + x["consequent"],
                                           confidence=lambda x: x["confidence"] * 100,
                                           support=lambda x: x["support"] * 100)
            st.dataframe(d[["rule", "confidence", "lift", "support"]], hide_index=True, width="stretch",
                         column_config={
                             "rule": st.column_config.TextColumn(t("mn_col_rule"), width="large"),
                             "confidence": st.column_config.ProgressColumn(t("mn_col_conf"), format="%.1f%%", min_value=0, max_value=100),
                             "lift": st.column_config.NumberColumn("Lift", format="%.2f"),
                             "support": st.column_config.NumberColumn(t("mn_col_support"), format="%.1f%%"),
                         })
        card(t("mn_c_pairs_title"), t("mn_c_pairs_cap"), body=pairs_table)
        with st.expander(t("mn_read_metrics")):
            st.markdown(t("mn_metrics_apriori"))

# ---------------------------------------------------------------- K-Means
with tabs[1]:
    intro("mn_q_kmeans", "mn_m_kmeans")
    if not (km and db_ok and profile is not None):
        missing("kmeans_clustering")
    else:
        chosen, sil = km["best_k"], km["silhouette"]
        best_sil_k = max(sil, key=sil.get)
        k = st.columns(4)
        k[0].metric(t("mn_k_games"), fmt.num(km["n_games"]), border=True)
        k[1].metric(t("mn_k_features"), fmt.num(len(km["features"])), border=True, help=", ".join(km["features"]))
        k[2].metric(t("mn_k_k"), chosen, border=True)
        k[3].metric("Silhouette", fmt.num(sil[str(chosen)], 3), border=True, help=t("mn_k_silhouette_help"))
        if int(best_sil_k) != chosen:
            st.caption(t("mn_k_note", k2=best_sil_k, s2=fmt.num(sil[best_sil_k], 3), k=chosen, s=fmt.num(sil[str(chosen)], 3)))

        left, right = st.columns(2)
        with left:
            card(t("mn_c_sil_title"), t("mn_c_sil_cap"), mc.silhouette(km, p))
        with right:
            card(t("mn_c_inertia_title"), t("mn_c_inertia_cap"), mc.inertia(km, p))

        names = {int(r["cluster"]): cluster_name(r["cluster_label"]) for _, r in profile.iterrows()}
        card(t("mn_c_scatter_title"), t("mn_c_scatter_cap"), mc.clusters_scatter(clusters, p, names),
             clusters.assign(cluster_label=clusters["cluster_id"].map(names), positive_ratio=(clusters["positive_ratio"] * 100).round(1))
             [["game_title", "cluster_label", "owners_mid", "avg_ccu", "price_vnd", "positive_ratio"]]
             .rename(columns={"game_title": t("col_game"), "cluster_label": t("mn_col_cluster"), "owners_mid": t("col_owners"),
                              "avg_ccu": "CCU TB", "price_vnd": t("col_price"), "positive_ratio": t("col_pos_pct")}))

        st.markdown(f"#### {t('mn_profiles')}")
        pcols = st.columns(len(profile))
        for col, (_, r) in zip(pcols, profile.sort_values("cluster").iterrows()):
            with col.container(border=True):
                st.markdown(f"**{names[int(r['cluster'])]}**")
                st.metric(t("mn_k_games"), fmt.num(r["n_games"]))
                st.metric(t("mn_p_owners"), fmt.compact(r["owners_mid"]))
                st.metric(t("mn_p_ccu"), fmt.num(r["avg_ccu"]))
                st.metric(t("mn_p_price"), t("free") if r["price_vnd"] == 0 else fmt.vnd(r["price_vnd"]))
                st.metric(t("mn_p_pos"), fmt.pct(r["positive_ratio"] * 100))
                st.caption(t("mn_p_examples", g=r["examples"]))
        st.caption(t("mn_profiles_note"))

# ---------------------------------------------------------------- CART
with tabs[2]:
    intro("mn_q_cart", "mn_m_cart")
    if not cart:
        missing("cart_tree")
    else:
        test = cart["test"]
        k = st.columns(4)
        k[0].metric(t("mn_k_games"), fmt.num(cart["n_games"]), border=True,
                    help=t("mn_k_pos_rate", r=fmt.pct(cart["positive_rate"] * 100)))
        k[1].metric(t("mn_k_features"), fmt.num(cart["n_features"]), border=True, help=t("mn_k_cart_features_help"))
        k[2].metric(t("mn_k_depth"), cart["best_max_depth"], border=True, help=t("mn_k_depth_help"))
        k[3].metric(t("mn_k_f1_test"), fmt.num(test["f1"], 3),
                    delta=t("mn_vs_baseline", v=fmt.num(cart["baseline_stratified"]["f1"], 3)), delta_color="off",
                    border=True, help=t("mn_k_f1_help"))
        imp = mining.cart_importance()
        takeaways([t("mn_i_cart_top", f=mc.feature_label(imp.iloc[0]["feature"]), v=fmt.pct(imp.iloc[0]["importance"] * 100)),
                   t("mn_i_cart_quality", f1=fmt.num(test["f1"], 3), b=fmt.num(cart["baseline_stratified"]["f1"], 3),
                     auc=fmt.num(test["roc_auc"], 3))] if imp is not None else [])
        left, right = st.columns([3, 2])
        with left:
            if imp is not None:
                card(t("mn_c_imp_title"), t("mn_c_imp_cap"), mc.importance(imp, p),
                     imp.assign(feature=imp["feature"].map(mc.feature_label), importance=(imp["importance"] * 100).round(1))
                     .rename(columns={"feature": t("mn_col_feature"), "importance": t("mn_col_importance")}))
        with right:
            cm_labels = [t("mn_cls_other"), t("mn_cls_top")]
            card(t("mn_c_cm_title"), t("mn_c_cm_cart_cap"), mc.confusion(test["confusion_matrix [[TN, FP], [FN, TP]]"], cm_labels, p),
                 pd.DataFrame([{t("mn_col_model"): "CART", "Accuracy": test["accuracy"], "Precision": test["precision"],
                                "Recall": test["recall"], "F1": test["f1"], "ROC-AUC": test["roc_auc"]}]
                              + [{t("mn_col_model"): t(f"mn_baseline_{n}"), "Accuracy": b["accuracy"], "F1": b["f1"]}
                                 for n, b in (("most", cart["baseline_most_frequent"]), ("strat", cart["baseline_stratified"]))]))
        rules_text = mining.load_text("tree_rules.txt")
        if rules_text:
            card(t("mn_c_tree_title"), t("mn_c_tree_cap"), body=lambda: st.code(rules_text, language="text"))

# ---------------------------------------------------------------- Phân loại review
with tabs[3]:
    intro("mn_q_clf", "mn_m_clf")
    if not clf:
        missing("review_classifier")
    else:
        best = clf["best_model"]
        k = st.columns(4)
        k[0].metric(t("mn_k_reviews"), fmt.num(clf["n_reviews"]), border=True)
        k[1].metric(t("mn_k_pos_share"), fmt.pct(clf["positive_rate"] * 100), border=True, help=t("mn_k_pos_share_help"))
        k[2].metric(t("mn_k_f1_macro"), fmt.num(clf[best]["f1_macro"], 3),
                    delta=t("mn_vs_baseline", v=fmt.num(clf["baseline_majority"]["f1_macro"], 3)), delta_color="off", border=True)
        k[3].metric("Accuracy", fmt.pct(clf[best]["accuracy"] * 100), border=True)
        names = {"logreg": "Logistic Regression", "naive_bayes": "Naive Bayes (Complement)"}
        rows = [{"name": t("mn_baseline_majority"), **clf["baseline_majority"]}] + \
               [{"name": names[m] + (" ★" if m == best else ""), "accuracy": clf[m]["accuracy"], "f1_macro": clf[m]["f1_macro"]}
                for m in ("naive_bayes", "logreg") if m in clf]
        rows = [{"name": r["name"], "f1": r["f1_macro"], "accuracy": r["accuracy"]} for r in rows]
        report = clf[best]["report"]
        takeaways([t("mn_i_clf_best", m=names.get(best, best), f1=fmt.num(clf[best]["f1_macro"], 3),
                     b=fmt.num(clf["baseline_majority"]["f1_macro"], 3)),
                   t("mn_i_clf_neg", r=fmt.pct(report["chê"]["recall"] * 100), p=fmt.pct(report["chê"]["precision"] * 100))])
        left, right = st.columns([3, 2])
        with left:
            card(t("mn_c_models_title"), t("mn_c_models_cap"), mc.model_compare(rows, p))
        with right:
            card(t("mn_c_cm_title"), t("mn_c_cm_clf_cap"),
                 mc.confusion(clf[best]["confusion_matrix [[TN, FP], [FN, TP]]"], [t("mn_cls_neg"), t("mn_cls_pos")], p))
        terms = mining.review_terms()
        if terms is not None:
            card(t("mn_c_terms_title"), t("mn_c_terms_cap"), mc.review_terms(terms, p),
                 terms.rename(columns={"term": t("mn_col_term"), "coef": t("mn_col_coef")}))

# ---------------------------------------------------------------- NMF
with tabs[4]:
    intro("mn_q_nmf", "mn_m_nmf")
    if not (nmf and topics is not None):
        missing("negative_topics")
    else:
        k = st.columns(4)
        k[0].metric(t("mn_k_neg_reviews"), fmt.num(nmf["n_reviews"]), border=True)
        k[1].metric(t("mn_k_vocab"), fmt.num(nmf["vocab"]), border=True)
        k[2].metric(t("mn_k_topics"), nmf["best_k"], border=True)
        k[3].metric("UMass coherence", fmt.num(nmf["umass_coherence"][str(nmf["best_k"])], 3), border=True,
                    help=t("mn_k_coherence_help"))
        top = topics.sort_values("share", ascending=False)
        takeaways([t("mn_i_nmf", a=mc.topic_label(top.iloc[0]["top_words"]), ap=fmt.pct(top.iloc[0]["share"] * 100),
                     b=mc.topic_label(top.iloc[1]["top_words"]), bp=fmt.pct(top.iloc[1]["share"] * 100))])
        left, right = st.columns([3, 2])
        with left:
            card(t("mn_c_topics_title"), t("mn_c_topics_cap"), mc.topics(topics, p),
                 top.assign(share=(top["share"] * 100).round(1), examples=top["examples"].str.slice(0, 300))
                 [["top_words", "n_reviews", "share", "examples"]]
                 .rename(columns={"top_words": t("mn_col_words"), "n_reviews": t("mn_col_reviews"),
                                  "share": t("mn_col_share"), "examples": t("mn_col_examples")}))
        with right:
            card(t("mn_c_coh_title"), t("mn_c_coh_cap"), mc.coherence(nmf, p))

st.caption(t("mn_footer"))
