"""
Football Scouting & Player Similarity Engine — PCA Archetypes + Cosine Recruitment Search
Author: Mostafa Saad
Data: Official StatsBomb Open Data (FIFA World Cup 2022, UEFA Euro 2024, Bundesliga 2023/24)
"""

import json
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "statsbomb_players_real.csv"
DB_PATH = ROOT / "data" / "scouting.db"
SQL_PATH = ROOT / "sql" / "01_scouting_views.sql"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

BG = "#000000"
CARD = "#0A0C12"
CYAN = "#00E5FF"
VIOLET = "#A78BFA"
EMERALD = "#10B981"
AMBER = "#F59E0B"
ROSE = "#F43F5E"
TEXT = "#FFFFFF"
MUTED = "#94A3B8"
GRID = "#1E2433"

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": CARD,
    "axes.edgecolor": "#262D3F",
    "axes.labelcolor": MUTED,
    "text.color": TEXT,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "grid.color": GRID,
    "font.family": "DejaVu Sans",
})

FEATURE_COLS = [
    "shots_p90", "npxg_p90", "xa_p90", "key_passes_p90",
    "pass_acc_pct", "prog_passes_p90", "box_passes_p90",
    "prog_carries_p90", "dribbles_p90", "pressures_p90",
    "tackles_int_p90", "recoveries_p90", "final_third_p90",
]

FEATURE_LABELS = {
    "shots_p90": "Shots / 90",
    "npxg_p90": "npxG / 90",
    "xa_p90": "xA / 90",
    "key_passes_p90": "Key Passes",
    "pass_acc_pct": "Pass Acc %",
    "prog_passes_p90": "Prog. Passes",
    "box_passes_p90": "Box Entries",
    "prog_carries_p90": "Prog. Carries",
    "dribbles_p90": "Dribbles",
    "pressures_p90": "Pressures",
    "tackles_int_p90": "Tkl + Int",
    "recoveries_p90": "Recoveries",
    "final_third_p90": "Final 3rd Act",
}


def name_archetype(centroid_series):
    """Assign an intuitive football archetype label from standardized cluster centroid."""
    if centroid_series["npxg_p90"] > 0.7 and centroid_series["shots_p90"] > 0.7:
        return "Penalty-Box Finisher / #9"
    if centroid_series["dribbles_p90"] > 0.55 and centroid_series["xa_p90"] > 0.45:
        return "Creative Winger / #10"
    if centroid_series["prog_passes_p90"] > 0.55 and centroid_series["pass_acc_pct"] > 0.35:
        return "Deep Playmaker / Metronome"
    if centroid_series["tackles_int_p90"] > 0.45 and centroid_series["recoveries_p90"] > 0.45 and centroid_series["final_third_p90"] < 0:
        return "Ball-Winning Defender"
    if centroid_series["pressures_p90"] > 0.35 and centroid_series["prog_carries_p90"] > 0.1:
        return "Box-to-Box Pressing Engine"
    return "Balanced Wide / Fullback"


def main():
    print("[1/5] Loading 1,305 real StatsBomb players into SQLite & building per-90 views...")
    df_raw = pd.read_csv(RAW_CSV)
    conn = sqlite3.connect(DB_PATH)
    df_raw.to_sql("raw_statsbomb_players", conn, if_exists="replace", index=False)
    conn.executescript(SQL_PATH.read_text(encoding="utf-8"))
    qa = pd.read_sql_query("SELECT * FROM vw_scouting_qa", conn).iloc[0].to_dict()
    df = pd.read_sql_query("SELECT * FROM vw_player_per90", conn)
    conn.close()
    print("QA Summary:", qa)

    # Impute any rare null pass_acc_pct with role median
    for col in FEATURE_COLS:
        df[col] = df[col].fillna(df.groupby("role_group")[col].transform("median")).fillna(df[col].median())

    # Compute Same-Role Percentiles (0-100) for every player
    for col in FEATURE_COLS:
        df[f"{col}_pctl"] = (df.groupby("role_group")[col].rank(pct=True) * 100).round(1)

    # Standardize features for PCA + K-Means + Cosine Similarity
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[FEATURE_COLS])

    print("[2/5] Selecting optimal K-Means clusters via Silhouette Score & running 2D PCA...")
    sil_scores = {}
    for k in range(4, 9):
        km_tmp = KMeans(n_clusters=k, n_init=25, random_state=42)
        lbl_tmp = km_tmp.fit_predict(X_scaled)
        sil_scores[k] = round(float(silhouette_score(X_scaled, lbl_tmp)), 4)
        print(f"  k={k} -> Silhouette={sil_scores[k]:.4f}")

    best_k = max(sil_scores, key=sil_scores.get)
    km = KMeans(n_clusters=best_k, n_init=30, random_state=42)
    df["cluster_id"] = km.fit_predict(X_scaled)

    # Label clusters from centroid Z-scores
    centroids = pd.DataFrame(km.cluster_centers_, columns=FEATURE_COLS)
    used_names = {}
    cluster_names = {}
    for cid in range(best_k):
        base_name = name_archetype(centroids.iloc[cid])
        if base_name in used_names:
            used_names[base_name] += 1
            cluster_names[cid] = f"{base_name} ({used_names[base_name]})"
        else:
            used_names[base_name] = 1
            cluster_names[cid] = base_name
    df["archetype"] = df["cluster_id"].map(cluster_names)

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X_scaled)
    df["pca_1"] = coords[:, 0].round(3)
    df["pca_2"] = coords[:, 1].round(3)
    var_exp = [round(float(v * 100), 1) for v in pca.explained_variance_ratio_]
    print(f"Optimal k={best_k} (Silhouette={sil_scores[best_k]}) | PCA 2D Variance Explained: {sum(var_exp):.1f}%")

    # [3/5] Weighted Cosine Similarity Recruitment Engine
    print("[3/5] Building Cosine Similarity 'Find a Replacement' Engine...")
    sim_matrix = cosine_similarity(X_scaled)

    def find_similar(query_substr, top_n=5, same_role=True):
        matches = df[df["player_name"].str.contains(query_substr, case=False, na=False)].sort_values("minutes", ascending=False)
        if matches.empty:
            return None
        idx = matches.index[0]
        target = df.loc[idx]
        sims = sim_matrix[idx]
        order = np.argsort(sims)[::-1]
        twins = []
        for j in order:
            if j == idx:
                continue
            cand = df.loc[j]
            if same_role and cand["role_group"] != target["role_group"]:
                continue
            # Convert cosine [-1, 1] -> intuitive 0-100% similarity score
            sim_pct = round(float((sims[j] + 1.0) / 2.0 * 100.0), 1)
            twins.append({
                "player_name": cand["player_name"],
                "team": cand["team"],
                "role_group": cand["role_group"],
                "archetype": cand["archetype"],
                "minutes": float(cand["minutes"]),
                "similarity_pct": sim_pct,
                "npxg_p90": float(cand["npxg_p90"]),
                "xa_p90": float(cand["xa_p90"]),
                "prog_passes_p90": float(cand["prog_passes_p90"]),
                "prog_carries_p90": float(cand["prog_carries_p90"]),
            })
            if len(twins) >= top_n:
                break
        return {
            "target_player": target["player_name"],
            "target_team": target["team"],
            "target_role": target["role_group"],
            "target_archetype": target["archetype"],
            "target_minutes": float(target["minutes"]),
            "top_matches": twins,
        }

    # Pick 4 iconic real stars present in our WC22 + Euro24 + Leverkusen 23/24 database
    star_queries = ["Wirtz", "Xhaka", "Mbappé", "Bellingham", "Rodri", "Messi", "Saka", "Gvardiol"]
    shortlists = []
    for q in star_queries:
        res = find_similar(q, top_n=5, same_role=True)
        if res and len(res["top_matches"]) == 5:
            shortlists.append(res)
        if len(shortlists) == 4:
            break

    df.to_csv(OUT_DIR / "scouting_database.csv", index=False)
    (OUT_DIR / "scouting_shortlists.json").write_text(json.dumps(shortlists, indent=2, ensure_ascii=False), encoding="utf-8")

    metrics_payload = {
        "dataset": "StatsBomb Open Data (FIFA World Cup 2022 + UEFA Euro 2024 + Bundesliga 2023/24)",
        "qa_summary": qa,
        "eligible_players": int(len(df)),
        "silhouette_scores": sil_scores,
        "optimal_k": int(best_k),
        "pca_variance_explained_pct": var_exp,
        "archetype_counts": df["archetype"].value_counts().to_dict(),
        "role_counts": df["role_group"].value_counts().to_dict(),
        "sample_shortlists": shortlists,
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # [4/5] 4 Publication-Grade AMOLED Figures
    print("[4/5] Rendering 4 AMOLED scouting & similarity visualizations...")
    cluster_palette = [EMERALD, CYAN, VIOLET, AMBER, ROSE, "#38BDF8", "#F472B6", "#34D399"]

    # Fig 1: 2D PCA Tactical Space
    fig, ax = plt.subplots(figsize=(11.5, 6.2), dpi=160)
    fig.patch.set_facecolor(BG)
    for cid in range(best_k):
        sub = df[df["cluster_id"] == cid]
        ax.scatter(sub["pca_1"], sub["pca_2"], s=36, color=cluster_palette[cid % len(cluster_palette)],
                   alpha=0.72, edgecolors="#000000", lw=0.4, label=f"{cluster_names[cid]} (n={len(sub)})")

    # Annotate featured stars (clean football display names)
    def short_star_label(full_name: str) -> str:
        for known in ("Mbappé", "Wirtz", "Xhaka", "Bellingham", "Rodri", "Messi", "Saka", "Gvardiol"):
            if known.lower() in full_name.lower():
                return known
        return full_name.split()[-1]

    for sl in shortlists:
        row = df[df["player_name"] == sl["target_player"]].iloc[0]
        ax.scatter([row["pca_1"]], [row["pca_2"]], s=140, color="#FFFFFF", edgecolor=EMERALD, lw=2.0, zorder=6)
        ax.annotate(short_star_label(row["player_name"]), (row["pca_1"], row["pca_2"]),
                    xytext=(8, 6), textcoords="offset points", color="#FFFFFF", fontsize=9.2, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#000000", ec=CYAN, alpha=0.85))

    ax.set_xlabel(f"PCA 1 — Attacking Threat vs Defensive Depth ({var_exp[0]}% var)")
    ax.set_ylabel(f"PCA 2 — Progression & Ball Circulation ({var_exp[1]}% var)")
    ax.set_title(f"Football Tactical Role Space — {len(df)} Real Outfield Players (Min. 270 mins)", color=TEXT, fontsize=13.8, fontweight="bold", pad=12)
    ax.grid(ls=":", alpha=0.5)
    ax.legend(frameon=False, fontsize=8.4, loc="upper left")
    plt.tight_layout()
    fig.savefig(FIG_DIR / "01_pca_tactical_map.png", facecolor=BG)
    plt.close(fig)

    # Fig 2: Silhouette Curve + Cluster Z-Score Heatmap
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4), dpi=160, gridspec_kw={"width_ratios": [0.85, 1.45]})
    fig.patch.set_facecolor(BG)
    fig.suptitle("Unsupervised Role Discovery — Silhouette Selection & Archetype DNA", color=TEXT, fontsize=14, fontweight="bold", y=0.97)

    ks = list(sil_scores.keys())
    vs = list(sil_scores.values())
    ax1.plot(ks, vs, marker="o", color=CYAN, lw=2.4, markersize=8, markerfacecolor=BG, markeredgewidth=2.2)
    ax1.scatter([best_k], [sil_scores[best_k]], color=EMERALD, s=130, zorder=6, label=f"Optimal k={best_k} ({sil_scores[best_k]:.3f})")
    ax1.set_xticks(ks); ax1.set_xlabel("Number of Clusters (k)"); ax1.set_ylabel("Silhouette Score")
    ax1.set_title("Silhouette Optimization", color=CYAN, fontweight="bold")
    ax1.grid(ls=":", alpha=0.5); ax1.legend(frameon=False, fontsize=8.8)

    hm_cols = ["npxg_p90", "xa_p90", "prog_passes_p90", "prog_carries_p90", "dribbles_p90", "pressures_p90", "tackles_int_p90", "recoveries_p90"]
    hm_mat = centroids[hm_cols].values
    im = ax2.imshow(hm_mat, cmap="coolwarm", vmin=-1.3, vmax=1.3, aspect="auto")
    ax2.set_xticks(range(len(hm_cols)))
    ax2.set_xticklabels([FEATURE_LABELS[c] for c in hm_cols], rotation=28, ha="right", fontsize=8.4, color=TEXT)
    ax2.set_yticks(range(best_k))
    ax2.set_yticklabels([cluster_names[i] for i in range(best_k)], fontsize=8.5, color=TEXT)
    for r_i in range(best_k):
        for c_i in range(len(hm_cols)):
            ax2.text(c_i, r_i, f"{hm_mat[r_i, c_i]:+.1f}", ha="center", va="center", color="#FFFFFF", fontsize=8, fontweight="bold")
    ax2.set_title("Cluster Centroid Z-Scores (Tactical Signature)", color=EMERALD, fontweight="bold")

    plt.tight_layout(rect=[0, 0.02, 1, 0.91])
    fig.savefig(FIG_DIR / "02_silhouette_archetypes.png", facecolor=BG)
    plt.close(fig)

    # Fig 3: "Find a Replacement" Top-5 Similarity Cards for First 2 Stars
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=160)
    fig.patch.set_facecolor(BG)
    fig.suptitle("Recruitment Search Engine — Top-5 Same-Role Statistical Twins (Cosine Similarity)", color=TEXT, fontsize=14, fontweight="bold", y=0.97)

    for ax, sl, accent in zip(axes, shortlists[:2], [EMERALD, CYAN]):
        twins = sl["top_matches"][::-1]
        names = [f"{t['player_name']}\n({t['team']})" for t in twins]
        sims = [t["similarity_pct"] for t in twins]
        bars = ax.barh(names, sims, color=accent, height=0.58, alpha=0.88)
        for b, s in zip(bars, sims):
            ax.text(s + 0.8, b.get_y() + b.get_height() / 2, f"{s:.1f}%", va="center", color=TEXT, fontsize=9, fontweight="bold", family="monospace")
        ax.set_xlim(50, 105)
        ax.set_xlabel("Cosine Similarity (%)")
        ax.set_title(f"Target: {sl['target_player']} ({sl['target_team']})", color=accent, fontweight="bold", fontsize=11)
        ax.grid(axis="x", ls=":", alpha=0.5)

    plt.tight_layout(rect=[0, 0.02, 1, 0.90])
    fig.savefig(FIG_DIR / "03_similarity_shortlist.png", facecolor=BG)
    plt.close(fig)

    # Fig 4: Head-to-Head Same-Role Percentile Comparison (Star #1 vs #1 Twin)
    star0 = shortlists[0]
    twin0 = star0["top_matches"][0]
    row_s = df[df["player_name"] == star0["target_player"]].iloc[0]
    row_t = df[df["player_name"] == twin0["player_name"]].iloc[0]

    cmp_cols = ["npxg_p90", "xa_p90", "key_passes_p90", "prog_passes_p90", "box_passes_p90", "prog_carries_p90", "dribbles_p90", "pressures_p90", "recoveries_p90"][::-1]
    s_pct = [row_s[f"{c}_pctl"] for c in cmp_cols]
    t_pct = [row_t[f"{c}_pctl"] for c in cmp_cols]
    y_c = np.arange(len(cmp_cols))

    fig, ax = plt.subplots(figsize=(10.8, 5.8), dpi=160)
    fig.patch.set_facecolor(BG)
    ax.barh(y_c + 0.18, s_pct, height=0.34, color=EMERALD, label=f"{row_s['player_name']} ({row_s['team']})")
    ax.barh(y_c - 0.18, t_pct, height=0.34, color=CYAN, alpha=0.88, label=f"#1 Twin: {row_t['player_name']} ({row_t['team']} · {twin0['similarity_pct']}% Match)")
    ax.set_yticks(y_c)
    ax.set_yticklabels([FEATURE_LABELS[c] for c in cmp_cols], color=TEXT, fontsize=9.4)
    ax.set_xlim(0, 108)
    ax.set_xlabel("Same-Role Percentile Rank (0–100)")
    ax.set_title(f"Head-to-Head Scouting Comparison ({row_s['role_group']})", color=TEXT, fontsize=13.5, fontweight="bold", pad=26)
    ax.grid(axis="x", ls=":", alpha=0.5)
    ax.legend(frameon=False, fontsize=9.0, loc="upper center", bbox_to_anchor=(0.5, 1.07), ncol=2)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "04_scouting_comparison_card.png", facecolor=BG)
    plt.close(fig)

    print("[5/5] Football Scouting Similarity Engine complete!")


if __name__ == "__main__":
    main()
