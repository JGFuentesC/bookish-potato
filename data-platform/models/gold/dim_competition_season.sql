SELECT
    cs.competition_id,
    cs.season_id,
    c.competition_name,
    s.season_name,
    co.country_name,
    c.competition_gender,
    c.is_youth,
    c.is_international,
    cs.match_updated
FROM pg.oltp.competition_season cs
JOIN pg.oltp.competition c ON c.competition_id = cs.competition_id
JOIN pg.oltp.season s ON s.season_id = cs.season_id
LEFT JOIN pg.oltp.country co ON co.country_id = c.country_id