import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { formatError } from "@/api/client";
import { AlertCircle, AlertTriangle, Info, RefreshCw, CheckCircle2, ArrowRightCircle } from "lucide-react";

const ICONS = { error: AlertCircle, warning: AlertTriangle, info: Info };
const CHIPS = { error: "chip-err", warning: "chip-warn", info: "chip-info" };

export default function ValidationCenter() {
  const { projectId } = useParams();
  const nav = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/api/projects/${projectId}/validation`);
      setReport(data);
    } catch (e) { setErr(formatError(e)); }
    finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const filtered = report
    ? report.issues.filter((i) => filter === "all" || i.severity === filter)
    : [];

  return (
    <div className="p-6" data-testid="validation-center">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">Data health</div>
          <h1 className="text-2xl font-bold tracking-tight">Validation Center</h1>
          <p className="text-sm text-neutral-500 mt-1">Live view of errors, warnings, and suggestions across all master data.</p>
        </div>
        <button onClick={load} className="ribbon-button"><RefreshCw className="w-3.5 h-3.5" /> Re-run</button>
      </div>

      {err && <div className="chip chip-err normal-case tracking-normal py-2 mb-4">{err}</div>}

      {loading || !report ? (
        <div className="text-sm text-neutral-500">Running checks…</div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3 mb-5">
            <StatCard label="Errors" value={report.errors} icon={AlertCircle} tone="chip-err" onClick={() => setFilter("error")} active={filter === "error"} testid="stat-errors" />
            <StatCard label="Warnings" value={report.warnings} icon={AlertTriangle} tone="chip-warn" onClick={() => setFilter("warning")} active={filter === "warning"} testid="stat-warnings" />
            <StatCard label="Suggestions" value={report.infos} icon={Info} tone="chip-info" onClick={() => setFilter("info")} active={filter === "info"} testid="stat-infos" />
            <StatCard label="Can Generate" value={report.can_generate ? "Yes" : "No"} icon={CheckCircle2} tone={report.can_generate ? "chip-ok" : "chip-err"} onClick={() => setFilter("all")} active={filter === "all"} testid="stat-generate" />
          </div>

          <div className="panel">
            <div className="panel-header">
              <span>Issues ({filtered.length})</span>
              <div className="flex gap-1 text-[11px] font-mono">
                {["all", "error", "warning", "info"].map((f) => (
                  <button key={f} onClick={() => setFilter(f)}
                    data-testid={`filter-${f}`}
                    className={`px-2 py-0.5 border ${filter === f ? "bg-black text-white border-black" : "border-neutral-300"}`}>
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <div className="divide-y divide-neutral-200">
              {filtered.length === 0 ? (
                <div className="text-sm text-neutral-500 py-10 text-center">
                  <CheckCircle2 className="w-6 h-6 mx-auto mb-2 text-emerald-600" />
                  No issues found for this filter.
                </div>
              ) : filtered.map((issue) => {
                const Icon = ICONS[issue.severity] || Info;
                return (
                  <div key={issue.id} className="px-4 py-3 flex items-start gap-3 hover:bg-neutral-50" data-testid={`issue-${issue.code}`}>
                    <Icon className={`w-4 h-4 mt-0.5 ${issue.severity === "error" ? "text-red-600" : issue.severity === "warning" ? "text-amber-600" : "text-blue-600"}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`chip ${CHIPS[issue.severity]}`}>{issue.severity}</span>
                        <span className="font-mono text-[11px] text-neutral-500">{issue.code}</span>
                        <span className="chip chip-muted normal-case tracking-normal">{issue.dataset}</span>
                      </div>
                      <div className="text-sm mt-1 leading-snug">{issue.message}</div>
                      {issue.fix_hint && (
                        <div className="text-xs text-neutral-500 mt-1">Hint: {issue.fix_hint}</div>
                      )}
                    </div>
                    <button
                      onClick={() => nav(`/projects/${projectId}/data/${issue.dataset}`)}
                      className="ribbon-button h-7 shrink-0"
                      data-testid={`goto-${issue.code}`}
                    >
                      Go to record <ArrowRightCircle className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tone, onClick, active, testid }) {
  return (
    <button onClick={onClick} className={`panel text-left transition ${active ? "border-black" : "hover:border-neutral-500"}`} data-testid={testid}>
      <div className="panel-body">
        <div className="flex items-center justify-between">
          <span className={`chip ${tone}`}>{label}</span>
          <Icon className="w-4 h-4 text-neutral-400" />
        </div>
        <div className="mt-3 text-3xl font-black font-mono">{value}</div>
      </div>
    </button>
  );
}
