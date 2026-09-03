"""Genera el HTML autocontenido del demo (sidebar escenarios + canvas + GIF)."""

from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVID = ROOT / "docs" / "evidence" / "E2-H1-adk"
SHOTS = EVID / "screenshots"


def b64(path: Path, mime: str) -> str:
    return "data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode()


SCENARIOS: list[dict[str, object]] = [
    {"id": "s1", "title": "Máximo goleador",
     "question": "¿Quién es el máximo goleador registrado en los datos?",
     "sql": "SELECT player_name, COUNT(CASE WHEN is_goal=TRUE THEN 1 ELSE NULL END) AS total_goals "
            "FROM fct_shot GROUP BY player_name ORDER BY total_goals DESC LIMIT 1",
     "answer": "Lionel Andrés Messi Cuccittini, con un total de 508 goles.",
     "shot": "01-goleador.jpeg"},
    {"id": "s2", "title": "xG promedio en La Liga",
     "question": "¿Cuál es el promedio de xG por disparo en La Liga?",
     "sql": "SELECT AVG(CAST(T1.xg AS REAL)) FROM fct_shot AS T1 "
            "INNER JOIN dim_match AS T2 ON T1.match_id = T2.match_id "
            "WHERE T2.competition_name LIKE '%La Liga%' LIMIT 1",
     "answer": "Aproximadamente 0.111.",
     "shot": None},
    {"id": "s3", "title": "Pases completados por Messi",
     "question": "¿Cuántos pases completó Lionel Messi en total?",
     "sql": "SELECT COUNT(*) FROM fct_pass WHERE player_name LIKE '%Messi%' AND outcome_name = 'Complete'",
     "answer": "33,031 pases registrados.",
     "shot": "02-pases-messi.jpeg"},
    {"id": "s4", "title": "Máximo asistidor",
     "question": "¿Qué jugador dio más asistencias de gol en los datos?",
     "sql": "SELECT player_name, COUNT(*) AS ast FROM fct_pass WHERE is_goal_assist = TRUE "
            "GROUP BY player_name ORDER BY ast DESC LIMIT 1",
     "answer": "Lionel Andrés Messi Cuccittini, con 220 asistencias.",
     "shot": "03-asistencias.jpeg"},
    {"id": "s5", "title": "Resultados temporada 2020/2021",
     "question": "Muéstrame los resultados de los partidos de la temporada 2020/2021",
     "sql": "SELECT home_team_name, home_score, away_score, away_team_name FROM dim_match "
            "WHERE season_name = '2020/2021' ORDER BY match_date LIMIT 5",
     "answer": "Varios: Granada 4-0 Barcelona; Real Madrid 2-1 Barcelona; Barcelona 1-0 Levante UD.",
     "shot": "04-resultados.jpeg"},
    {"id": "s6", "title": "Goles de penalty",
     "question": "¿Cuántos goles de penalty se marcaron en total?",
     "sql": "SELECT COUNT(*) FROM fct_shot WHERE shot_type_name = 'Penalty' AND is_goal = TRUE",
     "answer": "1,095 goles de penalty.",
     "shot": None},
    {"id": "s7", "title": "Tiros desde fuera del área",
     "question": "¿Qué jugador hizo más tiros desde fuera del área (location_x > 100)?",
     "sql": "SELECT player_name, COUNT(*) AS n FROM fct_shot WHERE location_x > 100 "
            "GROUP BY player_name ORDER BY n DESC LIMIT 1",
     "answer": "Lionel Andrés Messi Cuccittini, con 1,800 disparos.",
     "shot": "05-fuera-area.jpeg"},
    {"id": "s8", "title": "Equipo con más pases completados",
     "question": "¿Qué equipo realizó más pases completados en total?",
     "sql": "SELECT team_name, COUNT(*) AS n FROM fct_pass WHERE outcome_name = 'Complete' "
            "GROUP BY team_name ORDER BY n DESC LIMIT 1",
     "answer": "Barcelona, con 367,725 pases.",
     "shot": "06-pases-equipo.jpeg"},
]


def scenario_card(idx: int, s: dict[str, object]) -> str:
    sid = str(s["id"])
    title = str(s["title"])
    num = "{:02d}".format(idx)
    if s.get("shot"):
        img = ('<img class="shot" alt="captura ' + title + '" src="'
               + b64(SHOTS / str(s["shot"]), "image/jpeg") + '">')
    else:
        img = '<p class="noshot">(sin captura dedicada - respuesta del agente arriba)</p>'
    parts: list[str] = []
    parts.append('<article id="' + sid + '" class="card">')
    parts.append('<header><span class="num">' + num + '</span><h3>' + title + '</h3></header>')
    parts.append('<div class="grid"><div class="text">')
    parts.append('<p><strong>Pregunta</strong> ' + str(s["question"]) + '</p>')
    parts.append('<details><summary>SQL generado</summary><pre><code>' + str(s["sql"]) + '</code></pre></details>')
    parts.append('<p class="answer"><strong>Respuesta</strong> ' + str(s["answer"]) + '</p>')
    parts.append('</div><div class="img">' + img + '</div></div></article>')
    return "".join(parts)


CSS = """\
:root { --bg:#0f1115; --panel:#171a21; --line:#262b35; --fg:#e6e8ee; --mut:#8a93a6; --acc:#7cc4ff; }
* { box-sizing: border-box; }
html,body { margin:0; padding:0; background:var(--bg); color:var(--fg);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif; }
header.top { padding:20px 28px; border-bottom:1px solid var(--line); display:flex;
  justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; }
header.top h1 { margin:0; font-size:18px; font-weight:600; }
header.top .sub { color:var(--mut); font-size:12px; }
.layout { display:grid; grid-template-columns:260px 1fr; min-height:calc(100vh - 65px); }
aside { background:var(--panel); border-right:1px solid var(--line); padding:18px 0;
  position:sticky; top:0; align-self:start; height:100vh; overflow:auto; }
aside h2 { font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--mut); margin:0 20px 10px; }
aside ul { list-style:none; padding:0; margin:0; }
aside li a { display:flex; gap:10px; align-items:baseline; padding:8px 20px; color:var(--fg);
  text-decoration:none; border-left:3px solid transparent; font-size:13px; }
aside li a:hover { background:#1e2330; }
aside li a .n { color:var(--mut); font-variant-numeric:tabular-nums; min-width:22px; }
main { padding:24px 28px; max-width:1100px; }
.demo { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; margin-bottom:24px; }
.demo h2 { margin:0 0 6px; font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--mut); }
.demo img { max-width:100%; border-radius:6px; display:block; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:18px 20px; margin-bottom:16px; }
.card header { display:flex; gap:12px; align-items:baseline; margin-bottom:10px; }
.card .num { color:var(--acc); font-weight:600; font-variant-numeric:tabular-nums; }
.card h3 { margin:0; font-size:15px; font-weight:600; }
.grid { display:grid; grid-template-columns:1fr 360px; gap:20px; }
@media (max-width:820px) { .grid { grid-template-columns:1fr; } }
.text p { margin:8px 0; }
.answer { background:#1a2230; border-left:3px solid var(--acc); padding:8px 12px; border-radius:4px; }
.shot { max-width:100%; border-radius:6px; border:1px solid var(--line); }
.noshot { color:var(--mut); font-style:italic; padding:18px; text-align:center; border:1px dashed var(--line); border-radius:6px; }
details { margin:8px 0; }
details pre { background:#0c0e13; border:1px solid var(--line); border-radius:6px; padding:10px 12px; overflow:auto; font-size:12px; }
code { font-family:"SF Mono",Menlo,Consolas,monospace; }
.meta { color:var(--mut); font-size:12px; }
"""


def main() -> int:
    gif_uri = b64(EVID / "ui-demo.gif", "image/gif")
    cards = "\n".join(scenario_card(i, s) for i, s in enumerate(SCENARIOS, start=1))

    nav: list[str] = []
    for i, s in enumerate(SCENARIOS, start=1):
        nav.append('<li><a href="#' + str(s["id"]) + '"><span class="n">'
                   + "{:02d}".format(i) + '</span> ' + str(s["title"]) + '</a></li>')

    html = (
        "<!doctype html>\n<html lang=\"es\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>GenBI Fútbol - Demo ADK (talk-to-your-data)</title>\n"
        "<style>\n" + CSS + "</style>\n</head>\n<body>\n"
        "<header class=\"top\"><div>\n"
        "<h1>GenBI Fútbol — talk-to-your-data (ADK 2.8 + Ollama + gold)</h1>\n"
        "<div class=\"sub\">Agente ADK 2.0 sobre gemma4:latest (platypy) · tool "
        "<code>query_gold</code> → sidecar · capa gold (DuckDB sobre Parquet, derivada de Postgres)</div>\n"
        "</div><div class=\"meta\">8 escenarios · GIF incluido</div></header>\n"
        "<div class=\"layout\"><aside><h2>Escenarios</h2><ul>\n"
        + "\n".join(nav) + "\n</ul></aside>\n<main>\n"
        "<section class=\"demo\"><h2>Demo en vivo (ADK Dev UI)</h2>\n"
        "<img src=\"" + gif_uri + "\" alt=\"ADK Dev UI funcionando\">\n"
        "<p class=\"meta\">GIF generado con Chrome DevTools MCP + ffmpeg a partir de las capturas de la "
        "sesión <code>adk web</code> (gemma4:latest vía túnel SSH a platypy).</p></section>\n"
        + cards + "\n</main></div>\n</body>\n</html>\n"
    )
    out = EVID / "report.html"
    out.write_text(html)
    print("HTML escrito:", out, "(", len(html), "bytes )")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())