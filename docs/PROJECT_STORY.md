# Project Story — Football Scouting & Tactical Player Similarity Engine
## قصة بناء المشروع: ليه عملناه، إزاي اتبنى، وإيه الأسئلة والتحديات اللي واجهتنا؟

---

## 1. Why Did We Build This Project? (ليه عملنا المشروع ده؟)

Modern football recruitment departments (Brighton, Brentford, Liverpool, Bayer Leverkusen) don't start scouting by watching 500 random highlight reels. They start with a **Data-Driven Shortlist Funnel**:
- **Step 1 (Role Discovery):** Map every player's true on-pitch tactical DNA from event data — not just the position written on Transfermarkt.
- **Step 2 (Replacement Search):** When a key player leaves or ages out, mathematically retrieve the top 5–10 **"Statistical Twins"** playing the same tactical role, then hand that shortlist to video scouts!

**بالعربي:**
أندية زي برايتون وبرينتفورد وليفربول وباير ليفركوزن مش بتبدأ التعاقدات بفيديوهات يوتيوب عشوائية. بيبدأوا بـ **Scouting Engine**:
1. **يكتشفوا الدور التكتيكي الحقيقي لكل لاعب بالأرقام** (من 13 مؤشر لكل 90 دقيقة، مش مجرد "خط وسط" على الورق).
2. **لما نجم يمشي (زي فلوريان فيرتز أو جرانيت تشاكا)،** السيستم يطلعلك أوتوماتيك أقرب 5 بدائل بنفس البصمة التكتيكية (Cosine Similarity)، وبعدين كشافين الفيديو يركزوا وقتهم عليهم!

---

## 2. How Was It Built? (إزاي اتبنى خطوة بخطوة؟)

### Stage 1 — Event-Level Player Aggregation from Real StatsBomb Data
- Harvested **149 full matches** from official StatsBomb Open Data (FIFA World Cup 2022 + UEFA Euro 2024 + Bundesliga 2023/24 Bayer Leverkusen).
- Aggregated raw pass, carry, shot, dribble, pressure, tackle, interception, and recovery events into **1,305 unique real players** with true match minutes played.

### Stage 2 — SQLite Per-90 Scouting Mart (`sql/01_scouting_views.sql`)
- Built a clean SQLite view (`v_scouting_eligible`) that:
  - Normalizes all counting metrics to **per-90 minutes** (`metric * 90.0 / minutes`).
  - Excludes **81 Goalkeepers** (different metric distribution).
  - Applies a strict **minimum 270 minutes (3 full matches)** reliability gate, filtering **863 low-minute cameos** and retaining **361 statistically reliable outfield players**.
  - Maps StatsBomb's 25 granular positions into 5 clean recruitment role groups (`Center Back`, `Fullback / Wingback`, `Central Midfielder`, `Attacking Mid / Winger`, `Striker`).

### Stage 3 — Silhouette-Optimized K-Means & PCA (`src/run_pipeline.py`)
- Standardized all **13 per-90 KPIs** with `StandardScaler` so high-volume metrics (e.g., `60 passes/90`) don't drown out high-impact low-count metrics (e.g., `0.35 npxG/90`).
- Swept `k ∈ [4, 5, 6, 7, 8]` via **Silhouette Score** — **`k = 4`** won cleanly (`0.1961`), separating players into 4 intuitive archetypes without arbitrary guesswork.
- Projected the 13D tactical space into 2D via **PCA** (**56.3%** variance captured: PC1 `37.5%` Attacking Threat vs Depth, PC2 `18.8%` Progression & Circulation).

### Stage 4 — Role-Gated Cosine Similarity & Same-Role Percentiles
- Computed pairwise **Cosine Similarity** across standardized 13D vectors, gated strictly by `role_group` so a striker is never recommended to replace a central midfielder.
- Computed **0–100 Same-Role Percentile Ranks** for every KPI so scouts can immediately inspect head-to-head strengths (e.g., **Florian Wirtz vs Lamine Yamal — 96.0% match**).

---

## 3. Key Questions & Challenges We Faced (إيه الأسئلة والتحديات اللي واجهتنا؟)

### Challenge 1 — The "20-Minute Sub" Per-90 Explosion Trap
- **The Question:** Why did we drop **863** of the 1,305 raw players?
- **The Football Analytics Reality:** If a substitute plays 15 minutes and completes 2 dribbles, their per-90 explodes to **12.0 dribbles/90** — distorting both `StandardScaler` mean/std AND K-Means centroids! Setting a **270-minute (3-match) SQL gate** eliminated small-sample noise while preserving **361 genuine first-team players**.

### Challenge 2 — Cosine Similarity vs Euclidean Distance for Scouting
- **The Question:** Why use **Cosine Similarity** instead of Euclidean distance to find statistical twins?
- **The Insight:** Cosine Similarity measures the **angle (directional shape/style)** between two players' 13D tactical vectors, rather than just raw magnitude. That means a young talent playing for a slightly lower-possession team (like **Nico Williams** or **Amine Adli**) who creates and carries in the *exact same tactical proportions* as **Florian Wirtz** still surfaces at **94–95% similarity**!

### Challenge 3 — Why Did Granit Xhaka Cluster Near "Balanced Wide / Fullback" While His Twins Were Vitinha & Modrić?
- **The Question:** Looking at `metrics.json`, Xhaka's global `k=4` K-Means archetype fell into `Balanced Wide / Fullback`, yet his **same-role Cosine Similarity** twins were **Vitinha (92.2%)**, **McKennie (87.0%)**, **Modrić (86.7%)**, **Bernardo Silva (86.3%)**, and **Robert Andrich (86.2%)**! Why?
- **The Insight:** With `k = 4` across *all* 361 outfield players (CBs through Strikers), K-Means groups all hybrid "two-way progressive midfielders + fullbacks" into one mid-pitch cluster. That is **precisely why we built Role-Gated Cosine Similarity on top of K-Means** — K-Means gives macro-tactical mapping, while Role-Gated Cosine Similarity guarantees pinpoint position-true recruitment matches!

### Challenge 4 — Visual QA Caught Two Real Polish Details!
- **Issue A (`01_pca_tactical_map.png`):** StatsBomb stores Kylian Mbappé's legal full name as `Kylian Mbappé Lottin`, so taking `.split()[-1]` labeled him `"Lottin"` on the PCA map!
- **Issue B (`04_scouting_comparison_card.png`):** The bottom-right legend sat very close to the `Recoveries` horizontal bar.
- **The Fix:** Added a clean football display-name resolver (`"Mbappé"`) and moved the comparison legend cleanly above the plot (`bbox_to_anchor=(0.5, 1.07)`), then re-ran the full pipeline and verified every chart visually.

---

## 4. What Would We Build Next at a Club? (الخطوة الجاية لو ده سيستم في نادي)
- **Possession-Adjusted (PAdj) Defensive Metrics:** Adjust tackles, interceptions, and pressures for team possession share (a defender in a 70%-possession team naturally makes fewer raw tackles).
- **League Strength & Age Curves:** Combine multi-season StatsBomb/Wyscout leagues with age-curve projection and market value filters to find undervalued U-23 breakout twins before their fee doubles.
