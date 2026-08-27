# ERD OLTP — GenBI Fútbol

```mermaid
erDiagram
    BODY_PART {
        int body_part_id PK
        text body_part_name 
    }
    CARD_TYPE {
        int card_type_id PK
        text card_type_name 
    }
    COMPETITION {
        int competition_id PK
        text competition_name 
        int country_id FK
        text competition_gender 
        bool is_youth 
        bool is_international 
    }
    COMPETITION ||--o{ COUNTRY : "country_id"
    COMPETITION_SEASON {
        int competition_id PK FK
        int season_id PK FK
        timestamptz match_updated 
        bool match_available 
    }
    COMPETITION_SEASON ||--o{ COMPETITION : "competition_id"
    COMPETITION_SEASON ||--o{ SEASON : "season_id"
    COMPETITION_STAGE {
        int competition_stage_id PK
        text competition_stage_name 
    }
    COUNTRY {
        int country_id PK
        text country_name 
    }
    DUEL_TYPE {
        int duel_type_id PK
        text duel_type_name 
    }
    EVENT {
        uuid event_id PK
        int match_id FK
        int index 
        int period 
        timestamptz timestamp 
        int minute 
        num second 
        int type_id FK
        int possession 
        int possession_team_id FK
        int play_pattern_id FK
        int team_id FK
        int player_id FK
        int position_id FK
        num location_x 
        num location_y 
        num duration 
        bool under_pressure 
        bool off_camera 
        bool out 
    }
    EVENT ||--o{ MATCH : "match_id"
    EVENT ||--o{ EVENT_TYPE : "type_id"
    EVENT ||--o{ TEAM : "possession_team_id"
    EVENT ||--o{ PLAY_PATTERN : "play_pattern_id"
    EVENT ||--o{ TEAM : "team_id"
    EVENT ||--o{ PLAYER : "player_id"
    EVENT ||--o{ POSITION : "position_id"
    EVENT_50_50 {
        uuid event_id PK FK
        int outcome_id FK
    }
    EVENT_50_50 ||--o{ EVENT : "event_id"
    EVENT_50_50 ||--o{ OUTCOME : "outcome_id"
    EVENT_BAD_BEHAVIOUR {
        uuid event_id PK FK
        int card_type_id FK
    }
    EVENT_BAD_BEHAVIOUR ||--o{ EVENT : "event_id"
    EVENT_BAD_BEHAVIOUR ||--o{ CARD_TYPE : "card_type_id"
    EVENT_BALL_RECEIPT {
        uuid event_id PK FK
        int outcome_id FK
    }
    EVENT_BALL_RECEIPT ||--o{ EVENT : "event_id"
    EVENT_BALL_RECEIPT ||--o{ OUTCOME : "outcome_id"
    EVENT_BLOCK {
        uuid event_id PK FK
        int body_part_id FK
        bool deflection 
        bool offensive 
        bool saved_shot 
    }
    EVENT_BLOCK ||--o{ EVENT : "event_id"
    EVENT_BLOCK ||--o{ BODY_PART : "body_part_id"
    EVENT_CARRY {
        uuid event_id PK FK
        num end_location_x 
        num end_location_y 
    }
    EVENT_CARRY ||--o{ EVENT : "event_id"
    EVENT_CLEARANCE {
        uuid event_id PK FK
        int body_part_id FK
        int outcome_id FK
        bool under_pressure 
    }
    EVENT_CLEARANCE ||--o{ EVENT : "event_id"
    EVENT_CLEARANCE ||--o{ BODY_PART : "body_part_id"
    EVENT_CLEARANCE ||--o{ OUTCOME : "outcome_id"
    EVENT_DRIBBLE {
        uuid event_id PK FK
        int outcome_id FK
        bool overrun 
        bool nutmeg 
        bool no_touch 
    }
    EVENT_DRIBBLE ||--o{ EVENT : "event_id"
    EVENT_DRIBBLE ||--o{ OUTCOME : "outcome_id"
    EVENT_DUEL {
        uuid event_id PK FK
        int duel_type_id FK
        int outcome_id FK
    }
    EVENT_DUEL ||--o{ EVENT : "event_id"
    EVENT_DUEL ||--o{ DUEL_TYPE : "duel_type_id"
    EVENT_DUEL ||--o{ OUTCOME : "outcome_id"
    EVENT_FOUL_COMMITTED {
        uuid event_id PK FK
        int card_type_id FK
        text foul_type 
        bool advantage 
        bool penalty 
    }
    EVENT_FOUL_COMMITTED ||--o{ EVENT : "event_id"
    EVENT_FOUL_COMMITTED ||--o{ CARD_TYPE : "card_type_id"
    EVENT_FOUL_WON {
        uuid event_id PK FK
        bool defensive 
        bool advantage 
        bool penalty 
    }
    EVENT_FOUL_WON ||--o{ EVENT : "event_id"
    EVENT_GOALKEEPER {
        uuid event_id PK FK
        int goalkeeper_type_id FK
        int outcome_id FK
        int technique_id FK
        int body_part_id FK
    }
    EVENT_GOALKEEPER ||--o{ EVENT : "event_id"
    EVENT_GOALKEEPER ||--o{ GOALKEEPER_TYPE : "goalkeeper_type_id"
    EVENT_GOALKEEPER ||--o{ OUTCOME : "outcome_id"
    EVENT_GOALKEEPER ||--o{ TECHNIQUE : "technique_id"
    EVENT_GOALKEEPER ||--o{ BODY_PART : "body_part_id"
    EVENT_HALF_START {
        uuid event_id PK FK
        bool late_video_start 
    }
    EVENT_HALF_START ||--o{ EVENT : "event_id"
    EVENT_INTERCEPTION {
        uuid event_id PK FK
        int outcome_id FK
    }
    EVENT_INTERCEPTION ||--o{ EVENT : "event_id"
    EVENT_INTERCEPTION ||--o{ OUTCOME : "outcome_id"
    EVENT_MISCONTROL {
        uuid event_id PK FK
        int outcome_id FK
    }
    EVENT_MISCONTROL ||--o{ EVENT : "event_id"
    EVENT_MISCONTROL ||--o{ OUTCOME : "outcome_id"
    EVENT_PASS {
        uuid event_id PK FK
        num pass_length 
        num pass_angle 
        int pass_height_id FK
        int pass_type_id FK
        int technique_id FK
        int body_part_id FK
        int outcome_id FK
        int recipient_id FK
        bool is_assist 
        bool is_shot_assist 
        bool is_goal_assist 
    }
    EVENT_PASS ||--o{ EVENT : "event_id"
    EVENT_PASS ||--o{ PASS_HEIGHT : "pass_height_id"
    EVENT_PASS ||--o{ PASS_TYPE : "pass_type_id"
    EVENT_PASS ||--o{ TECHNIQUE : "technique_id"
    EVENT_PASS ||--o{ BODY_PART : "body_part_id"
    EVENT_PASS ||--o{ OUTCOME : "outcome_id"
    EVENT_PASS ||--o{ PLAYER : "recipient_id"
    EVENT_PLAYER_OFF {
        uuid event_id PK FK
        bool permanent 
        int outcome_id FK
    }
    EVENT_PLAYER_OFF ||--o{ EVENT : "event_id"
    EVENT_PLAYER_OFF ||--o{ OUTCOME : "outcome_id"
    EVENT_RELATION {
        uuid event_id PK FK
        uuid related_event_id PK FK
    }
    EVENT_RELATION ||--o{ EVENT : "event_id"
    EVENT_RELATION ||--o{ EVENT : "related_event_id"
    EVENT_SHOT {
        uuid event_id PK FK
        num xg 
        bool is_goal 
        int shot_type_id FK
        int body_part_id FK
        int technique_id FK
        int outcome_id FK
        bool first_time 
        bool open_goal 
        bool deflected 
    }
    EVENT_SHOT ||--o{ EVENT : "event_id"
    EVENT_SHOT ||--o{ SHOT_TYPE : "shot_type_id"
    EVENT_SHOT ||--o{ BODY_PART : "body_part_id"
    EVENT_SHOT ||--o{ TECHNIQUE : "technique_id"
    EVENT_SHOT ||--o{ OUTCOME : "outcome_id"
    EVENT_SUBSTITUTION {
        uuid event_id PK FK
        int replacement_id FK
        int outcome_id FK
    }
    EVENT_SUBSTITUTION ||--o{ EVENT : "event_id"
    EVENT_SUBSTITUTION ||--o{ PLAYER : "replacement_id"
    EVENT_SUBSTITUTION ||--o{ OUTCOME : "outcome_id"
    EVENT_TYPE {
        int event_type_id PK
        text event_type_name 
    }
    FORMATION {
        int formation_id PK
        text formation_name 
    }
    GOALKEEPER_TYPE {
        int goalkeeper_type_id PK
        text goalkeeper_type_name 
    }
    INGESTION_FILE {
        uuid run_id FK
        text source_path 
        text file_sha256 
        text entity 
        int rows 
        text status 
    }
    INGESTION_FILE ||--o{ INGESTION_RUN : "run_id"
    INGESTION_RUN {
        uuid run_id PK
        timestamptz started_at 
        timestamptz finished_at 
        text status 
        text scope 
        int files_processed 
        int rows_written 
        text error_summary 
    }
    MANAGER {
        int manager_id PK
        text name 
        text nickname 
        date date_of_birth 
        int country_id FK
    }
    MANAGER ||--o{ COUNTRY : "country_id"
    MATCH {
        int match_id PK
        int competition_id FK
        int season_id FK
        int home_team_id FK
        int away_team_id FK
        int stadium_id FK
        int referee_id FK
        int competition_stage_id FK
        date match_date 
        timestamptz kick_off 
        int home_score 
        int away_score 
        int match_week 
    }
    MATCH ||--o{ COMPETITION : "competition_id"
    MATCH ||--o{ SEASON : "season_id"
    MATCH ||--o{ TEAM : "home_team_id"
    MATCH ||--o{ TEAM : "away_team_id"
    MATCH ||--o{ STADIUM : "stadium_id"
    MATCH ||--o{ REFEREE : "referee_id"
    MATCH ||--o{ COMPETITION_STAGE : "competition_stage_id"
    MATCH_MANAGER {
        int match_id PK FK
        int team_id PK FK
        int manager_id PK FK
    }
    MATCH_MANAGER ||--o{ MATCH : "match_id"
    MATCH_MANAGER ||--o{ TEAM : "team_id"
    MATCH_MANAGER ||--o{ MANAGER : "manager_id"
    MATCH_PLAYER {
        int match_id PK FK
        int player_id PK FK
        int team_id FK
        int jersey_number 
        int country_id FK
    }
    MATCH_PLAYER ||--o{ MATCH : "match_id"
    MATCH_PLAYER ||--o{ PLAYER : "player_id"
    MATCH_PLAYER ||--o{ TEAM : "team_id"
    MATCH_PLAYER ||--o{ COUNTRY : "country_id"
    MATCH_PLAYER_CARD {
        int match_id PK FK
        int player_id PK FK
        int card_seq PK
        int card_type_id FK
        int minute 
        text reason 
    }
    MATCH_PLAYER_CARD ||--o{ MATCH : "match_id"
    MATCH_PLAYER_CARD ||--o{ PLAYER : "player_id"
    MATCH_PLAYER_CARD ||--o{ CARD_TYPE : "card_type_id"
    MATCH_PLAYER_POSITION {
        int match_id PK FK
        int player_id PK FK
        int position_id PK FK
        int from_period PK
        num from_time PK
    }
    MATCH_PLAYER_POSITION ||--o{ MATCH : "match_id"
    MATCH_PLAYER_POSITION ||--o{ PLAYER : "player_id"
    MATCH_PLAYER_POSITION ||--o{ POSITION : "position_id"
    OUTCOME {
        int outcome_id PK
        text outcome_name 
    }
    PASS_HEIGHT {
        int pass_height_id PK
        text pass_height_name 
    }
    PASS_TYPE {
        int pass_type_id PK
        text pass_type_name 
    }
    PLAY_PATTERN {
        int play_pattern_id PK
        text play_pattern_name 
    }
    PLAYER {
        int player_id PK
        text player_name 
        text player_nickname 
        int country_id FK
    }
    PLAYER ||--o{ COUNTRY : "country_id"
    POSITION {
        int position_id PK
        text position_name 
    }
    REFEREE {
        int referee_id PK
        text referee_name 
        int country_id FK
    }
    REFEREE ||--o{ COUNTRY : "country_id"
    SEASON {
        int season_id PK
        text season_name 
    }
    SEMANTIC_EMBEDDING {
        text entity_ref 
        text kind 
        USER-DEFINED embedding 
    }
    SHOT_FREEZE_FRAME {
        uuid event_id PK FK
        int frame_idx PK
        int player_id FK
        bool is_teammate 
        bool is_actor 
        bool is_keeper 
        num x 
        num y 
    }
    SHOT_FREEZE_FRAME ||--o{ EVENT : "event_id"
    SHOT_FREEZE_FRAME ||--o{ PLAYER : "player_id"
    SHOT_TYPE {
        int shot_type_id PK
        text shot_type_name 
    }
    STADIUM {
        int stadium_id PK
        text stadium_name 
        int country_id FK
    }
    STADIUM ||--o{ COUNTRY : "country_id"
    TACTICS_LINEUP {
        uuid event_id PK FK
        int formation_id FK
    }
    TACTICS_LINEUP ||--o{ EVENT : "event_id"
    TACTICS_LINEUP ||--o{ FORMATION : "formation_id"
    TACTICS_PLAYER {
        uuid event_id PK FK
        int player_id PK FK
        int position_id FK
        int jersey_number 
    }
    TACTICS_PLAYER ||--o{ EVENT : "event_id"
    TACTICS_PLAYER ||--o{ PLAYER : "player_id"
    TACTICS_PLAYER ||--o{ POSITION : "position_id"
    TEAM {
        int team_id PK
        text team_name 
        text team_gender 
        int country_id FK
    }
    TEAM ||--o{ COUNTRY : "country_id"
    TECHNIQUE {
        int technique_id PK
        text technique_name 
    }
    THREE_SIXTY_ACTOR {
        uuid event_id PK FK
        int actor_idx PK
        bool is_teammate 
        bool is_actor 
        bool is_keeper 
        num x 
        num y 
    }
    THREE_SIXTY_ACTOR ||--o{ EVENT : "event_id"
    THREE_SIXTY_FRAME {
        uuid event_id PK FK
        jsonb visible_area 
    }
    THREE_SIXTY_FRAME ||--o{ EVENT : "event_id"
```

**56 tablas** en esquema `oltp` · generado por `scripts/gen_erd.py` desde el esquema real.
