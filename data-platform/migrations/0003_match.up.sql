CREATE TABLE oltp.match (
    match_id              integer PRIMARY KEY,
    competition_id        integer REFERENCES oltp.competition (competition_id) ON DELETE RESTRICT,
    season_id             integer REFERENCES oltp.season (season_id) ON DELETE RESTRICT,
    home_team_id          integer REFERENCES oltp.team (team_id) ON DELETE RESTRICT,
    away_team_id          integer REFERENCES oltp.team (team_id) ON DELETE RESTRICT,
    stadium_id            integer REFERENCES oltp.stadium (stadium_id) ON DELETE RESTRICT,
    referee_id            integer REFERENCES oltp.referee (referee_id) ON DELETE RESTRICT,
    competition_stage_id  integer REFERENCES oltp.competition_stage (competition_stage_id) ON DELETE RESTRICT,
    match_date            date,
    kick_off              timestamptz,
    home_score            integer,
    away_score            integer,
    match_week            integer
);

CREATE INDEX idx_match_competition_season ON oltp.match (competition_id, season_id);

CREATE INDEX idx_match_match_date ON oltp.match (match_date);

CREATE TABLE oltp.match_manager (
    match_id    integer REFERENCES oltp.match (match_id) ON DELETE RESTRICT,
    team_id     integer REFERENCES oltp.team (team_id) ON DELETE RESTRICT,
    manager_id  integer REFERENCES oltp.manager (manager_id) ON DELETE RESTRICT,
    PRIMARY KEY (match_id, team_id, manager_id)
);

CREATE TABLE oltp.match_player (
    match_id      integer REFERENCES oltp.match (match_id) ON DELETE RESTRICT,
    player_id     integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    team_id       integer REFERENCES oltp.team (team_id) ON DELETE RESTRICT,
    jersey_number integer,
    country_id    integer REFERENCES oltp.country (country_id) ON DELETE RESTRICT,
    PRIMARY KEY (match_id, player_id)
);

CREATE TABLE oltp.match_player_position (
    match_id    integer REFERENCES oltp.match (match_id) ON DELETE RESTRICT,
    player_id   integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    position_id integer REFERENCES oltp.position (position_id) ON DELETE RESTRICT,
    from_period integer,
    from_time   numeric(6,2),
    PRIMARY KEY (match_id, player_id, position_id, from_period, from_time)
);

CREATE TABLE oltp.match_player_card (
    match_id     integer REFERENCES oltp.match (match_id) ON DELETE RESTRICT,
    player_id    integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    card_seq     integer,
    card_type_id integer REFERENCES oltp.card_type (card_type_id) ON DELETE RESTRICT,
    minute       integer,
    reason       text,
    PRIMARY KEY (match_id, player_id, card_seq)
);