"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";

type Metric = {
  name: string;
  score: number | null;
  weight: number;
  detail: string;
  minimum: number | null;
  below_minimum: boolean;
  extra: { answer_tokens?: string[]; matched?: number[]; found?: string[]; missing?: string[] };
};
type CaseRow = {
  id: string; question: string; reference: string; answer: string | null;
  score: number; passed: boolean; metrics: Metric[]; reasons: string[]; tags: string[];
};
type Summary = {
  total: number; passed: number; pass_rate: number; mean_score: number;
  metric_means: Record<string, number>; by_tag: Record<string, { total: number; passed: number }>;
};
type Run = {
  id: number; name: string; created_at: string; answers: string; warnings: string[];
  rubric: { name: string; pass_threshold: number; metrics: Record<string, { weight: number; min: number | null }> };
  summary: Summary; cases: CaseRow[];
};
type RunListItem = { id: number; name: string; created_at: string; passed: number; total: number; mean_score: number };

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data as T;
}

const LABELS: Record<string, string> = {
  exact_match: "Exact match", keyword_recall: "Keywords", rouge_l: "ROUGE-L",
  length_ratio: "Length", numbers_match: "Numbers", no_forbidden: "No banned phrases",
};
const label = (name: string) => LABELS[name] || name.replaceAll("_", " ");

const fmt = (n: number | null | undefined) => (n === null || n === undefined ? "–" : n.toFixed(2));

// Cell tint: pale for low scores, deeper honey for high ones.
function tint(score: number | null) {
  if (score === null) return "transparent";
  return `rgba(214, 164, 58, ${0.08 + score * 0.42})`;
}

function Highlighted({ metric }: { metric?: Metric }) {
  const tokens = metric?.extra.answer_tokens;
  if (!tokens) return null;
  const matched = new Set(metric.extra.matched || []);
  return (
    <p className="tokens">
      {tokens.map((t, i) => (
        <span key={i}><span className={matched.has(i) ? "hit" : undefined}>{t}</span> </span>
      ))}
    </p>
  );
}

export default function Home() {
  const [files, setFiles] = useState<string[]>([]);
  const [chosenFile, setChosenFile] = useState("");
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadRuns = () => api<{ runs: RunListItem[] }>("/api/runs").then((d) => d.runs);

  async function openRun(id: number) {
    const data = await api<Run>(`/api/runs/${id}`);
    setRun(data);
    setCaseId((data.cases.find((c) => !c.passed) || data.cases[0])?.id ?? null);
  }

  useEffect(() => {
    (async () => {
      try {
        const f = await api<{ answers: string[] }>("/api/files");
        setFiles(f.answers);
        setChosenFile(f.answers[0] || "");
        const list = await loadRuns();
        setRuns(list);
        if (list.length) await openRun(list[0].id);
      } catch {
        setError("Can't reach the API. Start it with: python server.py");
      }
    })();
  }, []);

  async function runEvaluation() {
    setBusy(true);
    setError("");
    try {
      const created = await api<Run>("/api/runs", { method: "POST", body: JSON.stringify({ answers_file: chosenFile }) });
      setRuns(await loadRuns());
      await openRun(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadScorecard() {
    if (!run) return;
    const { markdown } = await api<{ markdown: string }>(`/api/runs/${run.id}/scorecard`);
    const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `scorecard-run-${run.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const metricNames = run ? Object.keys(run.rubric.metrics) : [];
  const selected = run?.cases.find((c) => c.id === caseId);
  const byName = (c: CaseRow | undefined, name: string) => c?.metrics.find((m) => m.name === name);

  return (
    <main className="page">
      <header className="top">
        <div>
          <h1>RubricSmith</h1>
          <p>Grade LLM answers against known-good answers.</p>
        </div>
        <div className="controls">
          <select value={chosenFile} onChange={(e) => setChosenFile(e.target.value)} aria-label="Answers file">
            {files.map((f) => <option key={f}>{f}</option>)}
          </select>
          <button className="primary" onClick={runEvaluation} disabled={busy || !chosenFile}>
            {busy ? "Grading..." : "Run evaluation"}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <div className="layout">
        <aside className="cell runs">
          <h2>Runs</h2>
          {runs.length === 0 && <p className="muted">No runs yet. Pick an answers file and run it.</p>}
          <ul>
            {runs.map((r) => (
              <li key={r.id}>
                <button className={run?.id === r.id ? "run active" : "run"} onClick={() => openRun(r.id)}>
                  <span className="run-name">{r.name}</span>
                  <span className="muted">#{r.id} · {r.passed}/{r.total} passed · {fmt(r.mean_score)}</span>
                </button>
              </li>
            ))}
          </ul>
          {run && (
            <div className="tags">
              <h2>By topic</h2>
              {Object.entries(run.summary.by_tag).map(([tag, t]) => (
                <div key={tag} className="tag-row">
                  <span>{tag}</span>
                  <span className="bar"><span style={{ width: `${(t.passed / t.total) * 100}%` }} /></span>
                  <span className="num">{t.passed}/{t.total}</span>
                </div>
              ))}
              <h2 className="gap">Average per metric</h2>
              {Object.entries(run.summary.metric_means).map(([name, mean]) => (
                <div key={name} className="tag-row">
                  <span>{label(name)}</span>
                  <span className="bar"><span style={{ width: `${mean * 100}%` }} /></span>
                  <span className="num">{fmt(mean)}</span>
                </div>
              ))}
            </div>
          )}
        </aside>

        {run && (
          <section className="main">
            <div className="stats">
              <div className="cell"><span className="label">Passed</span><strong>{run.summary.passed}/{run.summary.total}</strong></div>
              <div className="cell"><span className="label">Mean score</span><strong>{fmt(run.summary.mean_score)}</strong></div>
              <div className="cell"><span className="label">Pass mark</span><strong>{fmt(run.rubric.pass_threshold)}</strong></div>
              <div className="cell rubric">
                <span className="label">Rubric</span>
                <span>{run.rubric.name}</span>
                <button onClick={downloadScorecard}>Download scorecard</button>
              </div>
            </div>

            {run.warnings.map((w) => <p key={w} className="warning">{w}</p>)}

            <div className="cell table-wrap">
              <table className="grade">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Score</th>
                    {metricNames.map((m) => (
                      <th key={m}>
                        {label(m)}
                        <small>x{run.rubric.metrics[m].weight}{run.rubric.metrics[m].min !== null ? ` · min ${run.rubric.metrics[m].min}` : ""}</small>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {run.cases.map((c) => (
                    <tr key={c.id} className={c.id === caseId ? "picked" : ""} onClick={() => setCaseId(c.id)}>
                      <td>
                        <button className="case-btn" onClick={() => setCaseId(c.id)}>
                          <span className={c.passed ? "dot pass" : "dot fail"} aria-label={c.passed ? "passed" : "failed"} />
                          {c.id}
                        </button>
                      </td>
                      <td className="num strong">{fmt(c.score)}</td>
                      {metricNames.map((m) => {
                        const metric = byName(c, m);
                        const score = metric?.score ?? null;
                        return (
                          <td key={m} className="num" style={{ background: tint(score) }} title={metric?.detail}>
                            {fmt(score)}{metric?.below_minimum && <span className="flag"> !</span>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="legend">Darker cells mean higher scores. <span className="flag">!</span> means the metric is below its minimum, which fails the case on its own. Click a row to see why.</p>
            </div>

            {selected && (
              <div className="detail">
                <div className="cell">
                  <h2>
                    <span className={selected.passed ? "verdict pass" : "verdict fail"}>{selected.passed ? "Pass" : "Fail"}</span>
                    {selected.id}
                  </h2>
                  <p className="q">{selected.question}</p>
                  <h3>Expected</h3>
                  <p>{selected.reference}</p>
                  <h3>Model answer <small>(words shared with the expected answer are marked)</small></h3>
                  {selected.answer === null ? <p className="muted">No answer for this case.</p> : <Highlighted metric={byName(selected, "rouge_l")} />}
                  {selected.reasons.length > 0 && (
                    <ul className="reasons">{selected.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  )}
                </div>
                <div className="cell">
                  <h2>Metric breakdown</h2>
                  <ul className="breakdown">
                    {selected.metrics.map((m) => (
                      <li key={m.name}>
                        <div className="row">
                          <span>{label(m.name)}</span>
                          <span className={m.below_minimum ? "num bad" : "num"}>{fmt(m.score)}</span>
                        </div>
                        <span className="muted">{m.detail}</span>
                        {m.extra.found && (
                          <div className="chips">
                            {m.extra.found.map((k) => <span key={k} className="chip ok">{k}</span>)}
                            {(m.extra.missing || []).map((k) => <span key={k} className="chip miss">{k}</span>)}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
