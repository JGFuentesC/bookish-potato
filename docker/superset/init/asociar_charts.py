import json

from superset import db
from superset.app import create_app

DASHBOARDS = {
    "finanzas-overview": "Market Overview",
    "finanzas-performance": "Performance",
    "finanzas-volatilidad": "Volatilidad",
    "finanzas-liquidez": "Liquidez",
    "finanzas-estacionalidad": "Estacionalidad",
}


def main() -> None:
    app = create_app()
    with app.app_context():
        from superset.models.dashboard import Dashboard
        from superset.models.slice import Slice

        for slug, titulo in DASHBOARDS.items():
            dash = db.session.query(Dashboard).filter_by(slug=slug).first()
            if dash is None:
                print(f"[asociar] dashboard '{slug}' no encontrado", flush=True)
                continue
            posicion = json.loads(dash.position_json or "{}")
            ids = []
            for comp in posicion.values():
                if isinstance(comp, dict) and comp.get("type") == "CHART":
                    cid = comp.get("meta", {}).get("chartId")
                    if cid:
                        ids.append(int(cid))
            slices = db.session.query(Slice).filter(Slice.id.in_(ids)).order_by(Slice.id).all()
            dash.slices = slices
            db.session.commit()
            print(f"[asociar] '{titulo}': {len(slices)} charts asociados", flush=True)


if __name__ == "__main__":
    main()
