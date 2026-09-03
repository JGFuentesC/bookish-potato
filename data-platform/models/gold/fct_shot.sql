SELECT
    es.event_id,
    ev.match_id,
    m.match_date,
    m.competition_id,
    c.competition_name,
    m.season_id,
    s.season_name,
    ev.minute,
    ev.second,
    ev.period,
    ev.team_id,
    t.team_name,
    ev.player_id,
    p.player_name,
    ev.location_x,
    ev.location_y,
    es.xg,
    es.is_goal,
    st.shot_type_name,
    bp.body_part_name,
    tc.technique_name,
    oc.outcome_name,
    es.first_time,
    es.open_goal,
    es.deflected,
    ev.under_pressure,
    ev.play_pattern_id,
    pp.play_pattern_name
FROM pg.oltp.event_shot es
JOIN pg.oltp.event ev ON ev.event_id = es.event_id
JOIN pg.oltp.match m ON m.match_id = ev.match_id
JOIN pg.oltp.competition c ON c.competition_id = m.competition_id
JOIN pg.oltp.season s ON s.season_id = m.season_id
LEFT JOIN pg.oltp.team t ON t.team_id = ev.team_id
LEFT JOIN pg.oltp.player p ON p.player_id = ev.player_id
LEFT JOIN pg.oltp.shot_type st ON st.shot_type_id = es.shot_type_id
LEFT JOIN pg.oltp.body_part bp ON bp.body_part_id = es.body_part_id
LEFT JOIN pg.oltp.technique tc ON tc.technique_id = es.technique_id
LEFT JOIN pg.oltp.outcome oc ON oc.outcome_id = es.outcome_id
LEFT JOIN pg.oltp.play_pattern pp ON pp.play_pattern_id = ev.play_pattern_id