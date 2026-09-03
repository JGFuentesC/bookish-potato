SELECT
    m.match_id,
    m.competition_id,
    m.season_id,
    c.competition_name,
    s.season_name,
    m.match_date,
    m.match_week,
    m.home_team_id,
    ht.team_name AS home_team_name,
    m.away_team_id,
    aw.team_name AS away_team_name,
    m.home_score,
    m.away_score,
    CASE
        WHEN m.home_score > m.away_score THEN 'H'
        WHEN m.home_score < m.away_score THEN 'A'
        ELSE 'D'
    END AS home_result,
    st.stadium_name,
    r.referee_name,
    cs.competition_stage_name
FROM pg.oltp.match m
JOIN pg.oltp.competition c ON c.competition_id = m.competition_id
JOIN pg.oltp.season s ON s.season_id = m.season_id
LEFT JOIN pg.oltp.team ht ON ht.team_id = m.home_team_id
LEFT JOIN pg.oltp.team aw ON aw.team_id = m.away_team_id
LEFT JOIN pg.oltp.stadium st ON st.stadium_id = m.stadium_id
LEFT JOIN pg.oltp.referee r ON r.referee_id = m.referee_id
LEFT JOIN pg.oltp.competition_stage cs ON cs.competition_stage_id = m.competition_stage_id