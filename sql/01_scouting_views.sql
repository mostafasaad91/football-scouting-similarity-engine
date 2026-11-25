-- ============================================================================
-- Football Scouting & Player Similarity Engine — SQLite Per-90 Views
-- Data: Official StatsBomb Open Data (WC 2022, Euro 2024, Bundesliga 2023/24)
-- Author: Mostafa Saad
-- ============================================================================

DROP VIEW IF EXISTS vw_scouting_qa;
CREATE VIEW vw_scouting_qa AS
SELECT
    COUNT(*) AS total_players,
    SUM(CASE WHEN primary_position = 'Goalkeeper' THEN 1 ELSE 0 END) AS goalkeepers_excluded,
    SUM(CASE WHEN primary_position != 'Goalkeeper' AND minutes < 270 THEN 1 ELSE 0 END) AS low_minutes_excluded,
    SUM(CASE WHEN primary_position != 'Goalkeeper' AND minutes >= 270 THEN 1 ELSE 0 END) AS eligible_outfield_players
FROM raw_statsbomb_players;

DROP VIEW IF EXISTS vw_player_per90;
CREATE VIEW vw_player_per90 AS
SELECT
    player_id,
    player_name,
    team,
    competitions,
    primary_position,
    CASE
        WHEN primary_position LIKE '%Center Back%' THEN 'Center Back'
        WHEN primary_position LIKE '%Back%' OR primary_position LIKE '%Wing Back%' THEN 'Fullback / Wingback'
        WHEN primary_position LIKE '%Center Forward%' THEN 'Striker'
        WHEN primary_position LIKE '%Wing%' OR primary_position LIKE '%Attacking Midfield%' THEN 'Attacking Mid / Winger'
        ELSE 'Central Midfielder'
    END AS role_group,
    matches,
    minutes,
    ROUND(90.0 * shots / minutes, 3) AS shots_p90,
    ROUND(90.0 * npxg / minutes, 3) AS npxg_p90,
    ROUND(90.0 * xa / minutes, 3) AS xa_p90,
    ROUND(90.0 * key_passes / minutes, 3) AS key_passes_p90,
    ROUND(100.0 * passes_cmp / NULLIF(passes_att, 0), 2) AS pass_acc_pct,
    ROUND(90.0 * prog_passes / minutes, 3) AS prog_passes_p90,
    ROUND(90.0 * box_passes / minutes, 3) AS box_passes_p90,
    ROUND(90.0 * prog_carries / minutes, 3) AS prog_carries_p90,
    ROUND(90.0 * dribbles_succ / minutes, 3) AS dribbles_p90,
    ROUND(90.0 * pressures / minutes, 3) AS pressures_p90,
    ROUND(90.0 * tackles_interceptions / minutes, 3) AS tackles_int_p90,
    ROUND(90.0 * recoveries / minutes, 3) AS recoveries_p90,
    ROUND(90.0 * final_third_actions / minutes, 3) AS final_third_p90
FROM raw_statsbomb_players
WHERE primary_position != 'Goalkeeper'
  AND minutes >= 270.0;
