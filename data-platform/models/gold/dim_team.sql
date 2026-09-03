SELECT
    t.team_id,
    t.team_name,
    t.team_gender,
    co.country_name AS team_country_name
FROM pg.oltp.team t
LEFT JOIN pg.oltp.country co ON co.country_id = t.country_id