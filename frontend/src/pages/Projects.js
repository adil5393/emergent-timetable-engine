import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { formatError } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import { Grid3x3, Plus, LogOut, ArrowRight, Folder, X } from "lucide-react";

export default function ProjectsPage() {
  const { user, logout, isEditor } = useAuth();
  const nav = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", academic_year: "", working_days: 5, periods_per_day: 8 });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/api/projects");
      setProjects(data);
    } catch (e) { setErr(formatError(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      const { data } = await api.post("/api/projects", form);
      setShowCreate(false);
      setForm({ name: "", description: "", academic_year: "", working_days: 5, periods_per_day: 8 });
      nav(`/projects/${data.id}/import`);
    } catch (e) { setErr(formatError(e)); }
    finally { setSaving(false); }
  };

  return (
    <div className="min-h-screen bg-white" data-testid="projects-page">
      <header className="h-11 border-b border-neutral-300 flex items-center px-3 gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-black flex items-center justify-center">
            <Grid3x3 className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Timetable OS</span>
        </div>
        <div className="flex-1" />
        <div className="text-xs text-neutral-500 font-mono">{user?.email} · <span className="uppercase font-semibold">{user?.role}</span></div>
        <button data-testid="logout-btn" className="ribbon-button" onClick={logout}><LogOut className="w-3.5 h-3.5" /> Logout</button>
      </header>

      <div className="max-w-5xl mx-auto px-8 py-10">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">Workspace</div>
            <h1 className="text-3xl font-black tracking-tight">Projects</h1>
            <p className="text-sm text-neutral-500 mt-1">Every school-year timetable is its own project. Master data lives inside.</p>
          </div>
          {isEditor && (
            <button data-testid="new-project-btn" className="ribbon-button primary h-9" onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4" /> New Project
            </button>
          )}
        </div>

        {loading ? (
          <div className="text-sm text-neutral-500">Loading…</div>
        ) : projects.length === 0 ? (
          <div className="panel">
            <div className="panel-body text-center py-16">
              <Folder className="w-8 h-8 mx-auto mb-3 text-neutral-400" />
              <div className="font-semibold mb-1">No projects yet</div>
              <div className="text-sm text-neutral-500 mb-6">Create a project to start importing master data.</div>
              {isEditor && (
                <button data-testid="new-project-btn-empty" className="ribbon-button primary" onClick={() => setShowCreate(true)}>
                  <Plus className="w-4 h-4" /> Create Project
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {projects.map((p) => (
              <Link
                to={`/projects/${p.id}/import`}
                key={p.id}
                data-testid={`project-card-${p.id}`}
                className="panel hover:border-black transition-colors group"
              >
                <div className="panel-body">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500 mb-2">
                    {p.academic_year || "Untitled year"}
                  </div>
                  <div className="font-semibold text-base leading-snug group-hover:text-black">{p.name}</div>
                  <div className="text-xs text-neutral-500 mt-2 line-clamp-2 min-h-[32px]">
                    {p.description || "No description"}
                  </div>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-neutral-200 text-[11px] font-mono text-neutral-500">
                    <span>{p.working_days} days · {p.periods_per_day} periods</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={create} className="panel w-[440px]" data-testid="new-project-modal">
            <div className="panel-header">
              <span>New Project</span>
              <button type="button" onClick={() => setShowCreate(false)} className="text-neutral-500 hover:text-black"><X className="w-4 h-4" /></button>
            </div>
            <div className="panel-body space-y-3">
              <Field label="Name" required>
                <input data-testid="proj-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" />
              </Field>
              <Field label="Academic Year">
                <input data-testid="proj-year" value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input" placeholder="e.g., 2026-2027" />
              </Field>
              <Field label="Description">
                <textarea data-testid="proj-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input min-h-[70px]" />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Working Days / Week">
                  <input data-testid="proj-days" type="number" min={1} max={7} value={form.working_days} onChange={(e) => setForm({ ...form, working_days: parseInt(e.target.value) || 5 })} className="input" />
                </Field>
                <Field label="Periods / Day">
                  <input data-testid="proj-periods" type="number" min={1} max={16} value={form.periods_per_day} onChange={(e) => setForm({ ...form, periods_per_day: parseInt(e.target.value) || 8 })} className="input" />
                </Field>
              </div>
              {err && <div className="chip chip-err normal-case tracking-normal py-2 w-full justify-start">{err}</div>}
            </div>
            <div className="p-3 border-t border-neutral-200 flex justify-end gap-2">
              <button type="button" className="ribbon-button" onClick={() => setShowCreate(false)}>Cancel</button>
              <button data-testid="proj-submit" type="submit" disabled={saving} className="ribbon-button primary">{saving ? "Creating…" : "Create Project"}</button>
            </div>
          </form>
        </div>
      )}

      <style>{`
        .input { width: 100%; height: 32px; padding: 0 8px; border: 1px solid #d4d4d4; font-size: 13px; }
        .input:focus { outline: none; border-color: #000; }
        textarea.input { padding: 6px 8px; height: auto; }
      `}</style>
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-wider text-neutral-500 block mb-1">
        {label}{required && <span className="text-red-600"> *</span>}
      </label>
      {children}
    </div>
  );
}
