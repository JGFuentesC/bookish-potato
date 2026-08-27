CREATE TABLE oltp.event_pass (
    event_id        uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    pass_length     numeric(6,2),
    pass_angle      numeric(6,2),
    pass_height_id  integer REFERENCES oltp.pass_height (pass_height_id) ON DELETE RESTRICT,
    pass_type_id    integer REFERENCES oltp.pass_type (pass_type_id) ON DELETE RESTRICT,
    technique_id    integer REFERENCES oltp.technique (technique_id) ON DELETE RESTRICT,
    body_part_id    integer REFERENCES oltp.body_part (body_part_id) ON DELETE RESTRICT,
    outcome_id      integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT,
    recipient_id    integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    is_assist       boolean,
    is_shot_assist  boolean,
    is_goal_assist  boolean
);

CREATE TABLE oltp.event_shot (
    event_id        uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    xg              numeric(6,2),
    is_goal         boolean,
    shot_type_id    integer REFERENCES oltp.shot_type (shot_type_id) ON DELETE RESTRICT,
    body_part_id    integer REFERENCES oltp.body_part (body_part_id) ON DELETE RESTRICT,
    technique_id    integer REFERENCES oltp.technique (technique_id) ON DELETE RESTRICT,
    outcome_id      integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT,
    first_time      boolean,
    open_goal       boolean,
    deflected       boolean
);

CREATE TABLE oltp.event_dribble (
    event_id    uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    outcome_id  integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT,
    overrun     boolean,
    nutmeg      boolean,
    no_touch    boolean
);

CREATE TABLE oltp.event_carry (
    event_id       uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    end_location_x numeric(6,2),
    end_location_y numeric(6,2)
);

CREATE TABLE oltp.event_duel (
    event_id      uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    duel_type_id  integer REFERENCES oltp.duel_type (duel_type_id) ON DELETE RESTRICT,
    outcome_id    integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_goalkeeper (
    event_id            uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    goalkeeper_type_id  integer REFERENCES oltp.goalkeeper_type (goalkeeper_type_id) ON DELETE RESTRICT,
    outcome_id          integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT,
    technique_id        integer REFERENCES oltp.technique (technique_id) ON DELETE RESTRICT,
    body_part_id        integer REFERENCES oltp.body_part (body_part_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_foul_committed (
    event_id     uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    card_type_id integer REFERENCES oltp.card_type (card_type_id) ON DELETE RESTRICT,
    foul_type    text,
    advantage    boolean,
    penalty      boolean
);

CREATE TABLE oltp.event_foul_won (
    event_id   uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    defensive  boolean,
    advantage  boolean,
    penalty    boolean
);

CREATE TABLE oltp.event_interception (
    event_id    uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    outcome_id  integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_clearance (
    event_id        uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    body_part_id    integer REFERENCES oltp.body_part (body_part_id) ON DELETE RESTRICT,
    outcome_id      integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT,
    under_pressure  boolean
);

CREATE TABLE oltp.event_block (
    event_id      uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    body_part_id  integer REFERENCES oltp.body_part (body_part_id) ON DELETE RESTRICT,
    deflection    boolean,
    offensive     boolean,
    saved_shot    boolean
);

CREATE TABLE oltp.event_ball_receipt (
    event_id    uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    outcome_id  integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_miscontrol (
    event_id    uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    outcome_id  integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_substitution (
    event_id        uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    replacement_id  integer REFERENCES oltp.player (player_id) ON DELETE RESTRICT,
    outcome_id      integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_bad_behaviour (
    event_id     uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    card_type_id integer REFERENCES oltp.card_type (card_type_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_50_50 (
    event_id    uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    outcome_id  integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.event_half_start (
    event_id          uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    late_video_start  boolean
);

CREATE TABLE oltp.event_player_off (
    event_id    uuid PRIMARY KEY REFERENCES oltp.event (event_id) ON DELETE RESTRICT,
    permanent   boolean,
    outcome_id  integer REFERENCES oltp.outcome (outcome_id) ON DELETE RESTRICT
);