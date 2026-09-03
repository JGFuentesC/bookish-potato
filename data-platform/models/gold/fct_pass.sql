SELECT
    ep.event_id,
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
    ep.pass_length,
    ep.pass_angle,
    ph.pass_height_name,
    pt.pass_type_name,
    tc.technique_name,
    bp.body_part_name,
    oc.outcome_name,
    ep.is_assist,
    ep.is_shot_assist,
    ep.is_goal_assist,
    ep.recipient_id,
    rp.player_name AS recipient_name,
    ev.under_pressure,
    ev.play_pattern_id,
    pp.play_pattern_name
FROM pg.oltp.event_pass ep
JOIN pg.oltp.event ev ON ev.event_id = ep.event_id
JOIN pg.oltp.match m ON m.match_id = ev.match_id
JOIN pg.oltp.competition c ON c.competition_id = m.competition_id
JOIN pg.oltp.season s ON s.season_id = m.season_id
LEFT JOIN pg.oltp.team t ON t.team_id = ev.team_id
LEFT JOIN pg.oltp.player p ON p.player_id = ev.player_id
LEFT JOIN pg.oltp.pass_height ph ON ph.pass_height_id = ep.pass_height_id
LEFT JOIN pg.oltp.pass_type pt ON pt.pass_type_id = ep.pass_type_id
LEFT JOIN pg.oltp.technique tc ON tc.technique_id = ep.technique_id
LEFT JOIN pg.oltp.body_part bp ON bp.body_part_id = ep.body_part_id
LEFT JOIN pg.oltp.outcome oc ON oc.outcome_id = ep.outcome_id
LEFT JOIN pg.oltp.player rp ON rp.player_id = ep.recipient_id
LEFT JOIN pg.oltp.play_pattern pp ON pp.play_pattern_id = ev.play_pattern_id