CREATE TABLE oltp.event (
    event_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id            integer NOT NULL REFERENCES oltp.match (match_id) ON DELETE RESTRICT,
    index               integer NOT NULL,
    period              integer NOT NULL,
    timestamp           timestamptz NOT NULL,
    minute              integer NOT NULL,
    second              numeric(6,2) NOT NULL,
    type_id             integer REFERENCES oltp.event_type (event_type_id) ON DELETE RESTRICT,
    possession          integer,
    possession_team_id  integer REFERENCES oltp.team (team_id) ON DELETE RESTRICT,
    play_pattern_id     integer REFERENCES oltp.play_pattern (play_pattern_id) ON DELETE RESTRICT,
    team_id             integer REFERENCES oltp.team (team_id) ON DELETE RESTRICT,
    player_id           integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    position_id         integer REFERENCES oltp.position (position_id) ON DELETE RESTRICT,
    location_x          numeric(6,2),
    location_y          numeric(6,2),
    duration            numeric(6,2),
    under_pressure      boolean,
    off_camera          boolean,
    out                 boolean
);

CREATE INDEX idx_event_match_index ON oltp.event (match_id, index);

CREATE INDEX idx_event_player ON oltp.event (player_id);

CREATE INDEX idx_event_team ON oltp.event (team_id);

CREATE INDEX idx_event_type ON oltp.event (type_id);

CREATE TABLE oltp.event_relation (
    event_id          uuid REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    related_event_id  uuid REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    PRIMARY KEY (event_id, related_event_id)
);