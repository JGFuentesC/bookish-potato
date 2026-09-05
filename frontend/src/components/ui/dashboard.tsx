"use client";

import { useState } from "react";

import { PromptInput, type PromptInputProps } from "@/components/ui/ai-chat-input";
import { runNl2Sql, clearToken, type QueryResponse } from "@/lib/api";
import { SCENARIOS, type Scenario } from "@/lib/scenarios";

interface Answer {
  role: "user" | "assistant"
  text: string
  sql?: string
  result?: QueryResponse
  error?: string
}

interface DashboardProps {
  userEmail?: string
  onLogout: () => void
}

const BACKGROUND = {
  backgroundImage:
    "radial-gradient(125% 125% at 50% 101%, rgba(245,87,2,1) 10.5%, rgba(245,120,2,1) 16%, rgba(245,140,2,1) 17.5%, rgba(245,170,100,1) 25%, rgba(238,174,202,1) 40%, rgba(202,179,214,1) 65%, rgba(148,201,233,1) 100%)",
}

export function Dashboard({ userEmail, onLogout }: DashboardProps) {
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [pending, setPending] = useState(false)
  const [showReport, setShowReport] = useState(false)

  // NL2SQL real: cada pregunta se traduce a SQL con el modelo local y se
  // responde sobre la capa gold. No se acumula historial: solo la última QA.
  const ask = async (question: string) => {
    setPending(true)
    setAnswer({ role: "assistant", text: "Consultando…" })
    try {
      const data = await runNl2Sql(question)
      setAnswer({
        role: "assistant",
        text: data.answer,
        sql: data.sql,
        result: {
          columns: data.columns,
          rows: data.rows,
          row_count: data.row_count,
          duration_ms: data.duration_ms,
        },
      })
    } catch (err) {
      setAnswer({
        role: "assistant",
        text: "No se pudo responder.",
        error: err instanceof Error ? err.message : "error",
      })
    } finally {
      setPending(false)
    }
  }

  const handleSend: NonNullable<PromptInputProps["onSubmit"]> = (message) => {
    ask(message)
  }

  const runScenario = async (scenario: Scenario) => {
    ask(scenario.question)
  }

  const handleLogout = () => {
    clearToken()
    onLogout()
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <span className="text-sm font-bold">GB</span>
            </div>
            <div className="leading-tight">
              <span className="font-semibold">GenBI Fútbol</span>
              <span className="ml-2 text-xs text-muted-foreground">talk-to-your-data</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowReport((v) => !v)}
              className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
            >
              {showReport ? "Cerrar reporte" : "Reporte"}
            </button>
            <span className="text-sm text-muted-foreground">{userEmail ?? "usuario"}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* Hero / Prompt */}
      <section
        className="relative flex min-h-[50vh] w-full items-start justify-center overflow-hidden pt-16"
        style={BACKGROUND}
      >
        <div className="flex w-full max-w-lg flex-col items-center p-4">
          <h1 className="mb-6 text-center text-2xl font-bold text-foreground drop-shadow-sm">
            Pregunta sobre fútbol en lenguaje natural
          </h1>
          <PromptInput onSubmit={handleSend} placeholder="Pregunta, p. ej. cuántos goles metió Thomas Müller…" />

          <div className="mt-8 flex max-w-xl flex-wrap items-center justify-center gap-2">
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                type="button"
                disabled={pending}
                onClick={() => runScenario(s)}
                className="rounded-full border border-border bg-card/80 px-3 py-1.5 text-xs font-medium shadow-sm backdrop-blur transition-colors hover:bg-card disabled:opacity-50"
              >
                {s.title}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Resultado (solo la última pregunta) */}
      <main className="mx-auto w-full max-w-3xl px-6 py-8">
        {!answer && !showReport && (
          <p className="text-center text-muted-foreground">
            Escribe una pregunta o pulsa una tarjeta para consultar la capa gold.
          </p>
        )}

        {pending && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="inline-block size-3 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
            Traduciendo pregunta y consultando gold…
          </div>
        )}

        {answer && (
          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              GenBI
            </div>
            <div className="text-sm leading-relaxed">{answer.text}</div>
            {answer.sql && (
              <details className="mt-1">
                <summary className="cursor-pointer text-xs text-muted-foreground">
                  SQL generado
                </summary>
                <pre className="mt-1 overflow-auto rounded-md border border-border bg-muted p-2 text-xs">
                  {answer.sql}
                </pre>
              </details>
            )}
            {answer.result && <ResultTable result={answer.result} />}
            {answer.error && (
              <div className="mt-1 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {answer.error}
              </div>
            )}
          </div>
        )}

        {/* Report panel */}
        {showReport && (
          <section className="mt-8 rounded-2xl border border-border bg-card p-6 shadow-sm">
            <h2 className="mb-1 text-lg font-semibold">Reporte — talk-to-your-data</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              8 preguntas verificadas contra la capa gold. Pulsa "Ejecutar" para
              responderlas en vivo con NL2SQL.
            </p>
            <div className="space-y-3">
              {SCENARIOS.map((s, i) => (
                <article
                  key={s.id}
                  className="rounded-xl border border-border p-4 transition-colors hover:border-ring/40"
                >
                  <div className="flex items-baseline gap-3">
                    <span className="font-semibold tabular-nums text-primary">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="font-medium">{s.title}</h3>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    <strong>Pregunta:</strong> {s.question}
                  </p>
                  <details className="mt-1">
                    <summary className="cursor-pointer text-xs text-muted-foreground">
                      SQL esperado
                    </summary>
                    <pre className="mt-1 overflow-auto rounded-md border border-border bg-muted p-2 text-xs">
                      {s.sql}
                    </pre>
                  </details>
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => runScenario(s)}
                    className="mt-2 rounded-lg border border-border px-3 py-1 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-50"
                  >
                    Ejecutar
                  </button>
                </article>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

function ResultTable({ result }: { result: QueryResponse }) {
  return (
    <div className="mt-2 overflow-auto rounded-md border border-border">
      <table className="w-full text-left text-xs">
        <thead className="bg-muted">
          <tr>
            {result.columns.map((c) => (
              <th key={c} className="px-3 py-1.5 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, ri) => (
            <tr key={ri} className="border-t border-border">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-1.5 tabular-nums">
                  {String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}