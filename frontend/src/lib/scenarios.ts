export interface Scenario {
  id: string
  title: string
  question: string
  sql: string
  answer: string
}

export const SCENARIOS: Scenario[] = [
  {
    id: "s1",
    title: "Máximo goleador",
    question: "¿Quién es el máximo goleador registrado en los datos?",
    sql: "SELECT player_name, COUNT(CASE WHEN is_goal=TRUE THEN 1 ELSE NULL END) AS total_goals FROM fct_shot GROUP BY player_name ORDER BY total_goals DESC LIMIT 1",
    answer: "Lionel Andrés Messi Cuccittini, con un total de 508 goles.",
  },
  {
    id: "s2",
    title: "xG promedio en La Liga",
    question: "¿Cuál es el promedio de xG por disparo en La Liga?",
    sql: "SELECT AVG(CAST(T1.xg AS REAL)) FROM fct_shot AS T1 INNER JOIN dim_match AS T2 ON T1.match_id = T2.match_id WHERE T2.competition_name LIKE '%La Liga%' LIMIT 1",
    answer: "Aproximadamente 0.111.",
  },
  {
    id: "s3",
    title: "Pases por Messi",
    question: "¿Cuántos pases registró Lionel Messi en total?",
    sql: "SELECT COUNT(*) AS total FROM fct_pass WHERE player_name LIKE '%Messi%'",
    answer: "33,362 pases registrados.",
  },
  {
    id: "s4",
    title: "Máximo asistidor",
    question: "¿Qué jugador dio más asistencias de gol en los datos?",
    sql: "SELECT player_name, COUNT(*) AS ast FROM fct_pass WHERE is_goal_assist = TRUE GROUP BY player_name ORDER BY ast DESC LIMIT 1",
    answer: "Lionel Andrés Messi Cuccittini, con 220 asistencias.",
  },
  {
    id: "s5",
    title: "Resultados temporada 2020/2021",
    question: "Muéstrame los resultados de los partidos de la temporada 2020/2021",
    sql: "SELECT home_team_name, home_score, away_score, away_team_name FROM dim_match WHERE season_name = '2020/2021' ORDER BY match_date LIMIT 5",
    answer: "Ver tabla de resultados (primeros partidos de la temporada).",
  },
  {
    id: "s6",
    title: "Goles de penalty",
    question: "¿Cuántos goles de penalty se marcaron en total?",
    sql: "SELECT COUNT(*) AS total FROM fct_shot WHERE shot_type_name = 'Penalty' AND is_goal = TRUE",
    answer: "1,095 goles de penalty.",
  },
  {
    id: "s7",
    title: "Tiros desde fuera del área",
    question: "¿Qué jugador hizo más tiros desde fuera del área (location_x > 100)?",
    sql: "SELECT player_name, COUNT(*) AS n FROM fct_shot WHERE location_x > 100 GROUP BY player_name ORDER BY n DESC LIMIT 1",
    answer: "Lionel Andrés Messi Cuccittini, con 1,800 disparos.",
  },
  {
    id: "s8",
    title: "Equipo con más pases",
    question: "¿Qué equipo realizó más pases en total?",
    sql: "SELECT team_name, COUNT(*) AS n FROM fct_pass GROUP BY team_name ORDER BY n DESC LIMIT 1",
    answer: "Barcelona, con 367,725 pases.",
  },
]
