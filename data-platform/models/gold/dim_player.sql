SELECT
    p.player_id,
    p.player_name,
    p.player_nickname,
    co.country_name AS player_country_name
FROM pg.oltp.player p
LEFT JOIN pg.oltp.country co ON co.country_id = p.country_id