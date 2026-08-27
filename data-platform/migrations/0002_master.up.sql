CREATE TABLE oltp.competition (
    competition_id       integer PRIMARY KEY,
    competition_name     text NOT NULL,
    country_id           integer REFERENCES oltp.country (country_id) ON DELETE RESTRICT,
    competition_gender   text,
    is_youth             boolean,
    is_international     boolean
);

CREATE TABLE oltp.season (
    season_id   integer PRIMARY KEY,
    season_name text NOT NULL
);

CREATE TABLE oltp.competition_season (
    competition_id  integer REFERENCES oltp.competition (competition_id) ON DELETE RESTRICT,
    season_id       integer REFERENCES oltp.season (season_id) ON DELETE RESTRICT,
    match_updated   timestamptz,
    match_available boolean,
    PRIMARY KEY (competition_id, season_id)
);

CREATE TABLE oltp.team (
    team_id     integer PRIMARY KEY,
    team_name   text NOT NULL,
    team_gender text,
    country_id  integer REFERENCES oltp.country (country_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.player (
    player_id       integer PRIMARY KEY,
    player_name     text NOT NULL,
    player_nickname text,
    country_id      integer REFERENCES oltp.country (country_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.manager (
    manager_id    integer PRIMARY KEY,
    name          text NOT NULL,
    nickname      text,
    date_of_birth date,
    country_id    integer REFERENCES oltp.country (country_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.stadium (
    stadium_id   integer PRIMARY KEY,
    stadium_name text NOT NULL,
    country_id   integer REFERENCES oltp.country (country_id) ON DELETE RESTRICT
);

CREATE TABLE oltp.referee (
    referee_id   integer PRIMARY KEY,
    referee_name text NOT NULL,
    country_id   integer REFERENCES oltp.country (country_id) ON DELETE RESTRICT
);