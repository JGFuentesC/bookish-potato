import os

from superset import db
from superset.app import create_app

DB_USER = os.environ.get("MYSQL_DASHBOARDS_USER", "dashboards")
DB_HOST = os.environ.get("MYSQL_HOST", "mysql")
DB_PASSWORD = os.environ.get("MYSQL_DASHBOARDS_PASSWORD", "dash_dev_password")

CONNECTIONS = [
    {"name": "Finanzas OLAP", "db": "finanzas_olap"},
    {"name": "Finanzas MySQL", "db": "finanzas"},
]


def main() -> None:
    app = create_app()
    with app.app_context():
        from superset.models.core import Database

        for conexion in CONNECTIONS:
            uri = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{conexion['db']}"
            existente = (
                db.session.query(Database)
                .filter_by(database_name=conexion["name"])
                .first()
            )
            if existente is None:
                db.session.add(
                    Database(database_name=conexion["name"], sqlalchemy_uri=uri)
                )
                db.session.commit()
                print(f"Database connection '{conexion['name']}' created")
            elif existente.sqlalchemy_uri != uri:
                existente.sqlalchemy_uri = uri
                db.session.commit()
                print(f"Database connection '{conexion['name']}' updated (read-only user)")
            else:
                print(f"Database connection '{conexion['name']}' already correct")


if __name__ == "__main__":
    main()
