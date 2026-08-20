#!/usr/bin/env python3
"""Banco de pruebas para el modelo local (E0-H3, ADR-002).

Mide VRAM ocupada (vía /api/ps), tokens/s, latencia de primera respuesta
(TTFT) y ventana de contexto efectiva. Emite un único JSON a stdout.

Uso:
  python3 scripts/bench_model.py --model gemma4:latest \
      --runs 20 --max-tokens 512 --num-ctx 8192 \
      --prompt "..." [--output bench.json]
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request


def post(url, payload, stream=False):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    return urllib.request.urlopen(req, timeout=1800)


def get(url):
    return urllib.request.urlopen(url, timeout=60)


def api_ps(host):
    with get(f"{host}/api/ps") as resp:
        data = json.loads(resp.read())
    out = {}
    if data.get("models"):
        m = data["models"][0]
        out = {
            "name": m.get("name"),
            "size": m.get("size"),
            "size_vram": m.get("size_vram"),
            "context_length": m.get("context_length"),
            "processor": m.get("processor"),
            "family": (m.get("details") or {}).get("family"),
            "parameter_size": (m.get("details") or {}).get("parameter_size"),
            "quantization": (m.get("details") or {}).get("quantization_level"),
        }
    return out


def run_generation(host, model, prompt, num_ctx, max_tokens, seed):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": {
            "temperature": 0,
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
            "seed": seed,
        },
    }
    started = time.monotonic()
    ttft = None
    chunks = 0
    done = None
    with post(f"{host}/api/chat", payload, stream=True) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line:
                continue
            if ttft is None:
                ttft = time.monotonic() - started
            chunks += 1
            chunk = json.loads(line)
            if chunk.get("done"):
                done = chunk
    total = time.monotonic() - started
    return {
        "ttft_s": round(ttft, 4) if ttft is not None else None,
        "total_s": round(total, 4),
        "eval_count": done.get("eval_count") if done else None,
        "prompt_eval_count": done.get("prompt_eval_count") if done else None,
        "eval_duration_ns": done.get("eval_duration") if done else None,
        "prompt_eval_duration_ns": done.get("prompt_eval_duration") if done else None,
        "done_reason": done.get("done_reason") if done else None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--output")
    args = ap.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as fh:
            prompt = fh.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = (
            "Eres un asistente de análisis de fútbol. Responde de forma concisa "
            "y en español. Pregunta: ¿cuántos goles marcó el Barcelona en 2022?"
        )

    with get(f"{args.host}/api/version") as resp:
        version = json.loads(resp.read()).get("version")

    # Carga en frío (no se mide).
    run_generation(args.host, args.model, "warmup", args.num_ctx, 8, args.seed)

    runs = []
    for i in range(args.runs):
        runs.append(run_generation(args.host, args.model, prompt, args.num_ctx, args.max_tokens, args.seed))

    ps = api_ps(args.host)

    ttft = [r["ttft_s"] for r in runs if r["ttft_s"] is not None]
    tps = []
    for r in runs:
        if r["eval_count"] and r["eval_duration_ns"]:
            tps.append(r["eval_count"] / (r["eval_duration_ns"] / 1e9))

    def agg(vals):
        if not vals:
            return None
        return {"min": round(min(vals), 4), "median": round(statistics.median(vals), 4), "max": round(max(vals), 4)}

    prompt_tokens = max(r["prompt_eval_count"] or 0 for r in runs) if runs else None
    report = {
        "bench": "E0-H3",
        "model": args.model,
        "ollama_version": version,
        "num_ctx": args.num_ctx,
        "max_tokens": args.max_tokens,
        "runs": args.runs,
        "seed": args.seed,
        "prompt_tokens": prompt_tokens,
        "prompt_fits_in_window": bool(prompt_tokens is not None and prompt_tokens < args.num_ctx),
        "ttft_s": agg(ttft),
        "tokens_per_s": agg(tps),
        "vram": ps,
        "fully_in_vram": bool(ps and ps.get("size") == ps.get("size_vram")),
        "evidences": runs,
    }

    blob = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(blob)
    else:
        print(blob)


if __name__ == "__main__":
    main()