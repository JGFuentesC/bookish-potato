CREATE TABLE oltp.shot_freeze_frame (
    event_id     uuid REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    frame_idx    integer,
    player_id    integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    is_teammate  boolean,
    is_actor     boolean,
    is_keeper    boolean,
    x            numeric(6,2),
    y            numeric(6,2),
    PRIMARY KEY (event_id, frame_idx)
);

CREATE TABLE oltp.tactics_lineup (
    event_id      uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    formation_id  integer REFERENCES oltp.formation (formation_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.tactics_player (
    event_id       uuid REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    player_id      integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    position_id    integer REFERENCES oltp.position (position_id) ON DELETE RESTRICT,
    jersey_number  integer,
    PRIMARY KEY (event_id, player_id)
);

CREATE TABLE oltp.three_sixty_frame (
    event_id      uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    visible_area  jsonb
);

CREATE TABLE oltp.three_sixty_actor (
    event_id     uuid REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    actor_idx    integer,
    is_teammate  boolean,
    is_actor     boolean,
    is_keeper    boolean,
    x            numeric(6,2),
    y            numeric(6,2),
    PRIMARY KEY (event_id, actor_idx)
);