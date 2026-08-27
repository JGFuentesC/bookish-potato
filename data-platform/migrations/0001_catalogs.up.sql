CREATE SCHEMA IF NOT EXISTS oltp;

CREATE TABLE oltp.country (
    country_id   integer PRIMARY KEY,
    country_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.competition_stage (
    competition_stage_id   integer PRIMARY KEY,
    competition_stage_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.event_type (
    event_type_id   integer PRIMARY KEY,
    event_type_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.play_pattern (
    play_pattern_id   integer PRIMARY KEY,
    play_pattern_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.position (
    position_id   integer PRIMARY KEY,
    position_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.body_part (
    body_part_id   integer PRIMARY KEY,
    body_part_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.outcome (
    outcome_id   integer PRIMARY KEY,
    outcome_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.technique (
    technique_id   integer PRIMARY KEY,
    technique_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.pass_height (
    pass_height_id   integer PRIMARY KEY,
    pass_height_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.pass_type (
    pass_type_id   integer PRIMARY KEY,
    pass_type_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.shot_type (
    shot_type_id   integer PRIMARY KEY,
    shot_type_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.duel_type (
    duel_type_id   integer PRIMARY KEY,
    duel_type_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.goalkeeper_type (
    goalkeeper_type_id   integer PRIMARY KEY,
    goalkeeper_type_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.card_type (
    card_type_id   integer PRIMARY KEY,
    card_type_name text NOT NULL UNIQUE
);

CREATE TABLE oltp.formation (
    formation_id   integer PRIMARY KEY,
    formation_name text NOT NULL UNIQUE
);-- country
INSERT INTO oltp.country (country_id, country_name) VALUES (214, 'Spain');
-- competition_stage
INSERT INTO oltp.competition_stage (competition_stage_id, competition_stage_name) VALUES (1, 'Regular Season');
INSERT INTO oltp.competition_stage (competition_stage_id, competition_stage_name) VALUES (26, 'Final');
-- event_type
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (2, 'Ball Recovery');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (3, 'Dispossessed');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (4, 'Duel');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (6, 'Block');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (8, 'Offside');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (9, 'Clearance');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (10, 'Interception');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (14, 'Dribble');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (16, 'Shot');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (17, 'Pressure');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (18, 'Half Start');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (19, 'Substitution');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (20, 'Own Goal Against');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (21, 'Foul Won');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (22, 'Foul Committed');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (23, 'Goal Keeper');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (24, 'Bad Behaviour');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (25, 'Own Goal For');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (26, 'Player On');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (27, 'Player Off');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (28, 'Shield');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (30, 'Pass');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (33, '50/50');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (34, 'Half End');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (35, 'Starting XI');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (36, 'Tactical Shift');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (37, 'Error');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (38, 'Miscontrol');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (39, 'Dribbled Past');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (40, 'Injury Stoppage');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (41, 'Referee Ball-Drop');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (42, 'Ball Receipt*');
INSERT INTO oltp.event_type (event_type_id, event_type_name) VALUES (43, 'Carry');
-- play_pattern
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (1, 'Regular Play');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (2, 'From Corner');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (3, 'From Free Kick');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (4, 'From Throw In');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (5, 'Other');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (6, 'From Counter');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (7, 'From Goal Kick');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (8, 'From Keeper');
INSERT INTO oltp.play_pattern (play_pattern_id, play_pattern_name) VALUES (9, 'From Kick Off');
-- position
INSERT INTO oltp.position (position_id, position_name) VALUES (0, 'Substitute');
INSERT INTO oltp.position (position_id, position_name) VALUES (1, 'Goalkeeper');
INSERT INTO oltp.position (position_id, position_name) VALUES (2, 'Right Back');
INSERT INTO oltp.position (position_id, position_name) VALUES (3, 'Right Center Back');
INSERT INTO oltp.position (position_id, position_name) VALUES (4, 'Center Back');
INSERT INTO oltp.position (position_id, position_name) VALUES (5, 'Left Center Back');
INSERT INTO oltp.position (position_id, position_name) VALUES (6, 'Left Back');
INSERT INTO oltp.position (position_id, position_name) VALUES (7, 'Right Wing Back');
INSERT INTO oltp.position (position_id, position_name) VALUES (8, 'Left Wing Back');
INSERT INTO oltp.position (position_id, position_name) VALUES (9, 'Right Defensive Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (10, 'Center Defensive Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (11, 'Left Defensive Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (12, 'Right Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (13, 'Right Center Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (15, 'Left Center Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (16, 'Left Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (17, 'Right Wing');
INSERT INTO oltp.position (position_id, position_name) VALUES (18, 'Right Attacking Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (19, 'Center Attacking Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (20, 'Left Attacking Midfield');
INSERT INTO oltp.position (position_id, position_name) VALUES (21, 'Left Wing');
INSERT INTO oltp.position (position_id, position_name) VALUES (22, 'Right Center Forward');
INSERT INTO oltp.position (position_id, position_name) VALUES (23, 'Center Forward');
INSERT INTO oltp.position (position_id, position_name) VALUES (24, 'Left Center Forward');
-- body_part
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (35, 'Both Hands');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (36, 'Chest');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (37, 'Head');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (38, 'Left Foot');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (39, 'Left Hand');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (40, 'Right Foot');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (41, 'Right Hand');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (68, 'Drop Kick');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (69, 'Keeper Arm');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (70, 'Other');
INSERT INTO oltp.body_part (body_part_id, body_part_name) VALUES (106, 'No Touch');
-- outcome
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (1, 'Lost');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (2, 'Success To Opposition');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (3, 'Success To Team');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (4, 'Won');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (9, 'Incomplete');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (13, 'Lost In Play');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (14, 'Lost Out');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (15, 'Success');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (16, 'Success In Play');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (17, 'Success Out');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (47, 'Claim');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (48, 'Clear');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (49, 'Collected Twice');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (50, 'Fail');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (52, 'In Play Danger');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (53, 'In Play Safe');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (55, 'No Touch');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (56, 'Saved Twice');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (58, 'Touched In');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (59, 'Touched Out');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (74, 'Injury Clearance');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (75, 'Out');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (76, 'Pass Offside');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (77, 'Unknown');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (96, 'Blocked');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (97, 'Goal');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (98, 'Off T');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (99, 'Post');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (100, 'Saved');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (101, 'Wayward');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (102, 'Injury');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (103, 'Tactical');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (115, 'Saved Off Target');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (116, 'Saved to Post');
INSERT INTO oltp.outcome (outcome_id, outcome_name) VALUES (117, 'Punched out');
-- technique
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (89, 'Backheel');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (90, 'Diving Header');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (91, 'Half Volley');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (92, 'Lob');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (93, 'Normal');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (94, 'Overhead Kick');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (95, 'Volley');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (104, 'Inswinging');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (105, 'Outswinging');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (107, 'Straight');
INSERT INTO oltp.technique (technique_id, technique_name) VALUES (108, 'Through Ball');
-- pass_height
INSERT INTO oltp.pass_height (pass_height_id, pass_height_name) VALUES (1, 'Ground Pass');
INSERT INTO oltp.pass_height (pass_height_id, pass_height_name) VALUES (2, 'Low Pass');
INSERT INTO oltp.pass_height (pass_height_id, pass_height_name) VALUES (3, 'High Pass');
-- pass_type
INSERT INTO oltp.pass_type (pass_type_id, pass_type_name) VALUES (61, 'Corner');
INSERT INTO oltp.pass_type (pass_type_id, pass_type_name) VALUES (62, 'Free Kick');
INSERT INTO oltp.pass_type (pass_type_id, pass_type_name) VALUES (63, 'Goal Kick');
INSERT INTO oltp.pass_type (pass_type_id, pass_type_name) VALUES (64, 'Interception');
INSERT INTO oltp.pass_type (pass_type_id, pass_type_name) VALUES (65, 'Kick Off');
INSERT INTO oltp.pass_type (pass_type_id, pass_type_name) VALUES (66, 'Recovery');
INSERT INTO oltp.pass_type (pass_type_id, pass_type_name) VALUES (67, 'Throw-in');
-- shot_type
INSERT INTO oltp.shot_type (shot_type_id, shot_type_name) VALUES (62, 'Free Kick');
INSERT INTO oltp.shot_type (shot_type_id, shot_type_name) VALUES (87, 'Open Play');
INSERT INTO oltp.shot_type (shot_type_id, shot_type_name) VALUES (88, 'Penalty');
-- duel_type
INSERT INTO oltp.duel_type (duel_type_id, duel_type_name) VALUES (10, 'Aerial Lost');
INSERT INTO oltp.duel_type (duel_type_id, duel_type_name) VALUES (11, 'Tackle');
-- goalkeeper_type
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (25, 'Collected');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (26, 'Goal Conceded');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (27, 'Keeper Sweeper');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (28, 'Penalty Conceded');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (29, 'Penalty Saved');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (30, 'Punch');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (31, 'Save');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (32, 'Shot Faced');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (33, 'Shot Saved');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (113, 'Shot Saved Off Target');
INSERT INTO oltp.goalkeeper_type (goalkeeper_type_id, goalkeeper_type_name) VALUES (114, 'Shot Saved to Post');
-- card_type
INSERT INTO oltp.card_type (card_type_id, card_type_name) VALUES (5, 'Red Card');
INSERT INTO oltp.card_type (card_type_id, card_type_name) VALUES (6, 'Second Yellow');
INSERT INTO oltp.card_type (card_type_id, card_type_name) VALUES (7, 'Yellow Card');
-- formation
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (343, '3-4-3');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (352, '3-5-2');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (433, '4-3-3');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (442, '4-4-2');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (3421, '3-4-2-1');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (3511, '3-5-1-1');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (4141, '4-1-4-1');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (4222, '4-2-2-2');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (4231, '4-2-3-1');
INSERT INTO oltp.formation (formation_id, formation_name) VALUES (41221, '4-1-2-2-1');
