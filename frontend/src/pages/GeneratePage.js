import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { formatError } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import { Play, ShieldAlert, CheckCircle2, Clock, Table2, Trash2, RefreshCw } from "lucide-react";

export default function GeneratePage() {
  const { projectId } = useParams();
  const { isEditor } = useAuth();
  const nav = useNavigate();
  const [validation, setValidation] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState("");
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [v, tt] = await Promise.all([
        api.get(`/api/projects/${projectId}/validation`),
        api.get(`/api/projects/${projectId}/timetables`),
      ]);
      setValidation(v.data);
      setVersions(tt.data);
    } catch (e) { setErr(formatError(e)); }
    finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    setRunning(true);
    setErr("");
    try {
      const { data } = await api.post(`/api/projects/${projectId}/timetables/generate`, { name: name || null, config: {} });
      setName("");
      nav(`/projects/${projectId}/timetables/${data.id}`);
    } catch (e) { setErr(formatError(e)); }
    finally { setRunning(false); }
  };

  const deleteVersion = async (id) => {
    if (!window.confirm("Delete this version permanently?")) return;
    try {
      await api.delete(`/api/projects/${projectId}/timetables/${id}`);
      load();
    } catch (e) { setErr(formatError(e)); }
  };

  const canGen = validation?.can_generate;

  return (
    <div className="p-6" data-testid="generate-page">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">Engine</div>
          <h1 className="text-2xl font-bold tracking-tight">Generate Timetable</h1>
          <p className="text-sm text-neutral-500 mt-1">Every generation is stored as a new version. Nothing is overwritten.</p>
        </div>
        <button onClick={load} className="ribbon-button"><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>
      </div>

      {err && <div className="chip chip-err normal-case tracking-normal py-2 mb-4">{err}</div>}

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="panel col-span-2">
          <div className="panel-header">Pre-flight</div>
          <div className="panel-body">
            {loading || !validation ? "Loading…" : (
              <div className="grid grid-cols-3 gap-3 text-center">
                <StatMini label="Errors" value={validation.errors} tone={validation.errors ? "text-red-700" : "text-neutral-500"} />
                <StatMini label="Warnings" value={validation.warnings} tone={validation.warnings ? "text-amber-700" : "text-neutral-500"} />
                <StatMini label="Ready" value={canGen ? "Yes" : "No"} tone={canGen ? "text-emerald-700" : "text-red-700"} />
              </div>
            )}
            <div className="mt-4 flex items-center gap-2">
              <input
                data-testid="generate-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Version name (optional)"
                className="flex-1 h-8 px-2 border border-neutral-300 text-sm"
              />
              <button
                data-testid="generate-btn"
                disabled={!isEditor || !canGen || running}
                onClick={generate}
                className="ribbon-button primary"
              >
                <Play className="w-3.5 h-3.5" /> {running ? "Generating…" : "Generate Timetable"}
              </button>
            </div>
            {!canGen && validation && (
              <div className="mt-3 chip chip-err normal-case tracking-normal py-2 w-full justify-start">
                <ShieldAlert className="w-3.5 h-3.5" />
                {validation.errors > 0 ? `${validation.errors} critical error(s) must be resolved first.` : "Import teachers, subjects and classes before generating."}
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">Engine</div>
          <div className="panel-body text-xs text-neutral-600 space-y-2">
            <div><span className="font-mono uppercase tracking-wider text-neutral-500">Current:</span> Stub Engine</div>
            <div>A genetic-algorithm engine will be plugged into <code>EngineService</code> without changing any API.</div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">Versions ({versions.length})</div>
        <div className="divide-y divide-neutral-200">
          {versions.length === 0 ? (
            <div className="text-center text-neutral-500 py-8 text-sm">No timetables generated yet.</div>
          ) : versions.map((v) => (
            <div key={v.id} className="px-4 py-3 flex items-center gap-3" data-testid={`version-${v.version}`}>
              <div className="font-mono text-neutral-500 w-14">v{v.version}</div>
              <div className="flex-1">
                <div className="font-semibold text-sm">{v.name || `Version ${v.version}`}</div>
                <div className="text-xs text-neutral-500 font-mono">
                  {new Date(v.created_at).toLocaleString()} · {v.summary?.total_entries || 0} entries · {v.summary?.unassigned_slots || 0} unassigned
                </div>
              </div>
              <StatusChip status={v.status} />
              <button className="ribbon-button" onClick={() => nav(`/projects/${projectId}/timetables/${v.id}`)} data-testid={`open-v${v.version}`}>
                <Table2 className="w-3.5 h-3.5" /> Open
              </button>
              {isEditor && (
                <button className="ribbon-button danger" onClick={() => deleteVersion(v.id)} data-testid={`del-v${v.version}`}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatMini({ label, value, tone }) {
  return (
    <div className="border border-neutral-200 p-3">
      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">{label}</div>
      <div className={`text-2xl font-black font-mono ${tone}`}>{value}</div>
    </div>
  );
}

function StatusChip({ status }) {
  const map = {
    completed: { c: "chip-ok", i: CheckCircle2 },
    running: { c: "chip-info", i: Clock },
    failed: { c: "chip-err", i: ShieldAlert },
    queued: { c: "chip-muted", i: Clock },
  };
  const { c, i: Icon } = map[status] || map.queued;
  return <span className={`chip ${c}`}><Icon className="w-3 h-3" /> {status}</span>;
}
