import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scouting_engine():
    m = json.loads((ROOT / "outputs" / "metrics.json").read_text(encoding="utf-8"))
    assert m["qa_summary"]["total_players"] >= 800
    assert m["eligible_players"] >= 200
    assert m["optimal_k"] >= 4
    assert len(m["sample_shortlists"]) == 4

    conn = sqlite3.connect(ROOT / "data" / "scouting.db")
    min_mins = conn.execute("SELECT MIN(minutes) FROM vw_player_per90").fetchone()[0]
    gks = conn.execute("SELECT COUNT(*) FROM vw_player_per90 WHERE primary_position = 'Goalkeeper'").fetchone()[0]
    conn.close()
    assert min_mins >= 270.0
    assert gks == 0

    for fig in [
        "01_pca_tactical_map.png",
        "02_silhouette_archetypes.png",
        "03_similarity_shortlist.png",
        "04_scouting_comparison_card.png",
    ]:
        p = ROOT / "outputs" / "figures" / fig
        assert p.exists() and p.stat().st_size > 20_000, f"Missing figure {fig}"

    print("ALL FOOTBALL SCOUTING SIMILARITY TESTS PASSED!")


if __name__ == "__main__":
    test_scouting_engine()
