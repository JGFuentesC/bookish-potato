#!/usr/bin/env python3
"""Estimación de costo mensual del dashboard en Cloud Run (us-central1).

Precios unitarios 2026 (us-central1, request-based billing, sin CUD):

    vCPU/sec activo ......... $0.000024   (gratis 180.000 vCPU-s/mes)
    GiB/sec activo .......... $0.0000025  (gratis 360.000 GiB-s/mes)
    Requests ................ $0.40 / 1M  (gratis 2M/mes)
    Egress internet .......... $0.12 / GB  (gratis 1 GB/mes)
    Artifact Registry ....... $0.10 / GB/mes (0.5 GB gratis)
    Secret Manager .......... $0.06 / versión activa/mes

Escenarios: contenedor 1 vCPU / 1 GiB, min=0, max=1, scale-to-zero.
"""

from __future__ import annotations

import argparse

CPU = 1
GIB = 1
P_VCPU = 0.000024
P_GIB = 0.0000025
P_REQ = 0.40
P_EGR = 0.12
P_AR = 0.10
P_SM = 0.06
FREE_VCPU = 180_000
FREE_GIB = 360_000
FREE_REQ = 2_000_000
FREE_EGR_GB = 1.0
AR_FREE_GB = 0.5

ESCENARIOS = {
    "básico (clase):      ~1800 cargas/semana": dict(
        horas=25, requests=25_000, imagen_gb=0.9, egress_gb=1.2
    ),
    "uso medio campus": dict(horas=60, requests=200_000, imagen_gb=0.9, egress_gb=4),
    "uso intensivo": dict(horas=150, requests=2_500_000, imagen_gb=0.9, egress_gb=20),
}


def calcular(horas: float, requests: int, imagen_gb: float, egress_gb: float) -> dict:
    vcpu_s = horas * 3600 * CPU
    gib_s = horas * 3600 * GIB
    cpu_pag = max(0, vcpu_s - FREE_VCPU) * P_VCPU
    mem_pag = max(0, gib_s - FREE_GIB) * P_GIB
    req_pag = max(0, requests - FREE_REQ) * P_REQ / 1_000_000
    egr_pag = max(0, egress_gb - FREE_EGR_GB) * P_EGR
    ar_pag = max(0, imagen_gb - AR_FREE_GB) * P_AR
    sm_pag = P_SM
    total = cpu_pag + mem_pag + req_pag + egr_pag + ar_pag + sm_pag
    return dict(
        vcpu_s=vcpu_s, gib_s=gib_s,
        cpu_pag=cpu_pag, mem_pag=mem_pag, req_pag=req_pag,
        egr_pag=egr_pag, ar_pag=ar_pag, sm_pag=sm_pag, total=total,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--horas", type=float, help="horas activas por mes")
    ap.add_argument("--requests", type=int, help="requests por mes")
    ap.add_argument("--imagen-gb", type=float, default=0.9, help="tamaño imagen AR (GB)")
    args = ap.parse_args()

    encabezado = "{:<32} {:>10} {:>10} {:>10} {:>10}".format("", "CPU($)", "RAM($)", "Req($)", "Total($)")

    if args.horas is not None:
        esc = dict(
            horas=args.horas,
            requests=args.requests or 0,
            imagen_gb=args.imagen_gb or 0.9,
            egress_gb=args.egress_gb if hasattr(args, "egress_gb") else 0,
        )
        if args.requests is None and args.horas <= 100:
            esc["requests"] = int(args.horas / 3600 * 1000)
        nombre = "personalizado"
        data = {nombre: esc}
    else:
        data = ESCENARIOS

    print("Escenario mensual — 1 vCPU, 1 GiB, min=0/max=1 (us-central1)\n")
    print(encabezado)
    for nombre, esc in data.items():
        r = calcular(esc["horas"], esc["requests"], esc["imagen_gb"], esc.get("egress_gb", 0))
        print(
            f"{nombre:<32} {r['cpu_pag']:>9.2f} {r['mem_pag']:>9.2f} "
            f"{r['req_pag']:>9.2f} {r['total']:>9.2f}"
        )

    r = calcular(60, 200_000, 0.9, 4)
    print(
        "\nDesglose (uso medio): "
        f"CPU ${r['cpu_pag']:.2f} · RAM ${r['mem_pag']:.2f} · "
        f"requests ${r['req_pag']:.2f} · egress ${r['egr_pag']:.2f} · "
        f"AR ${r['ar_pag']:.2f} · Secret Mgr ${r['sm_pag']:.2f} → TOTAL ${r['total']:.2f}/mes"
    )
    print("(No hay Cloud SQL, ni GCS, ni LB, ni min-instances → costo ~0 en uso moderado)")


if __name__ == "__main__":
    main()