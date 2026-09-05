from fastapi.testclient import TestClient

from genbi_ai.api.main import app
from genbi_ai.api.nl2sql import _extract_sql
from genbi_ai.api.query import validate_sql
from genbi_ai.semantic.catalog import Catalog

client = TestClient(app)


def test_extract_sql_plain() -> None:
    text = "SELECT COUNT(*) FROM fct_shot WHERE is_goal = TRUE"
    assert _extract_sql(text) == "SELECT COUNT(*) FROM fct_shot WHERE is_goal = TRUE"


def test_extract_sql_fenced() -> None:
    text = 'Aquí tienes:\n```sql\nSELECT COUNT(*) AS n FROM fct_pass\n```\nListo.'
    sql = _extract_sql(text)
    assert sql == "SELECT COUNT(*) AS n FROM fct_pass"


def test_extract_sql_multiline() -> None:
    text = (
        "SELECT player_name, COUNT(CASE WHEN is_goal=TRUE THEN 1 ELSE NULL END) AS g "
        "FROM fct_shot WHERE player_name LIKE '%Messi%' GROUP BY player_name"
    )
    assert _extract_sql(text) == text


def test_extract_sql_strips_ansi() -> None:
    text = "SELECT COUNT(*) AS n FROM fct_pass \x1b[4m)foo\x1b[0m LIMIT 5"
    assert _extract_sql(text) == "SELECT COUNT(*) AS n FROM fct_pass )foo LIMIT 5"


def test_extract_sql_with_cte() -> None:
    text = (
        "WITH g AS (SELECT player_name FROM fct_shot) "
        "SELECT * FROM g LIMIT 5"
    )
    assert _extract_sql(text) == text


def test_extract_sql_fenced_with_prose() -> None:
    text = 'Aquí tienes:\n```sql\nSELECT COUNT(*) FROM fct_shot WHERE is_goal = TRUE\n```\nListo.'
    assert _extract_sql(text) == "SELECT COUNT(*) FROM fct_shot WHERE is_goal = TRUE"


def test_nl2sql_empty_question_422() -> None:
    resp = client.post("/api/v1/nl2sql", json={"question": "   "})
    assert resp.status_code == 422


def test_validate_sql_allows_cte_aliases() -> None:
    catalog = Catalog.model_validate(
        {
            "version": 1,
            "tables": [
                {
                    "name": "fct_shot",
                    "grain": "event_id",
                    "columns": [
                        {"name": "player_name", "type": "varchar"},
                        {"name": "is_goal", "type": "boolean"},
                    ],
                }
            ],
        }
    )
    sql = (
        "WITH goals AS (SELECT player_name FROM fct_shot WHERE is_goal = TRUE) "
        "SELECT player_name FROM goals LIMIT 5"
    )
    normalized = validate_sql(sql, catalog)
    assert "goals" in normalized