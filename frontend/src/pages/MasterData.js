import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import api, { formatError } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, Trash2, Save, RefreshCw, Undo2, Redo2, Search, ClipboardPaste } from "lucide-react";

/* Field definitions per dataset. Keep in sync with backend importer.py. */
const DATASET_META = {
  teachers: { label: "Teachers", cols: [
    { key: "code", label: "Code" }, { key: "name", label: "Name" },
    { key: "email", label: "Email" }, { key: "phone", label: "Phone" },
    { key: "department_id", label: "Department", type: "ref", ref: "departments" },
    { key: "max_periods_per_day", label: "Max/Day", type: "number" },
    { key: "max_periods_per_week", label: "Max/Week", type: "number" },
    { key: "is_active", label: "Active", type: "boolean" },
  ]},
  subjects: { label: "Subjects", cols: [
    { key: "code", label: "Code" }, { key: "name", label: "Name" },
    { key: "weekly_periods", label: "Weekly Periods", type: "number" },
    { key: "is_lab", label: "Is Lab", type: "boolean" },
    { key: "department_id", label: "Department", type: "ref", ref: "departments" },
  ]},
  classes: { label: "Classes", cols: [
    { key: "code", label: "Code" }, { key: "name", label: "Name" },
    { key: "grade_level", label: "Grade Level", type: "number" },
  ]},
  sections: { label: "Sections", cols: [
    { key: "class_id", label: "Class", type: "ref", ref: "classes" },
    { key: "code", label: "Code" }, { key: "name", label: "Name" },
    { key: "strength", label: "Strength", type: "number" },
  ]},
  rooms: { label: "Rooms", cols: [
    { key: "code", label: "Code" }, { key: "name", label: "Name" },
    { key: "capacity", label: "Capacity", type: "number" },
    { key: "room_type", label: "Type" },
  ]},
  departments: { label: "Departments", cols: [
    { key: "code", label: "Code" }, { key: "name", label: "Name" },
  ]},
  teacher_mapping: { label: "Teacher Mapping", cols: [
    { key: "teacher_id", label: "Teacher", type: "ref", ref: "teachers" },
    { key: "subject_id", label: "Subject", type: "ref", ref: "subjects" },
    { key: "class_id", label: "Class", type: "ref", ref: "classes" },
    { key: "section_id", label: "Section", type: "ref", ref: "sections" },
    { key: "periods_per_week", label: "Periods/Week", type: "number" },
  ]},
  weekly_priority: { label: "Weekly Priority", cols: [
    { key: "subject_id", label: "Subject", type: "ref", ref: "subjects" },
    { key: "class_id", label: "Class", type: "ref", ref: "classes" },
    { key: "priority", label: "Priority", type: "number" },
    { key: "min_periods", label: "Min", type: "number" },
    { key: "max_periods", label: "Max", type: "number" },
  ]},
  school_timing: { label: "School Timing", cols: [
    { key: "day_of_week", label: "Day (0=Mon)", type: "number" },
    { key: "period_number", label: "Period", type: "number" },
    { key: "start_time", label: "Start" },
    { key: "end_time", label: "End" },
    { key: "is_break", label: "Break", type: "boolean" },
    { key: "label", label: "Label" },
  ]},
  constraints: { label: "Constraints", cols: [
    { key: "type", label: "Type" }, { key: "name", label: "Name" },
    { key: "entity_type", label: "Entity" }, { key: "entity_id", label: "Entity ID" },
    { key: "is_active", label: "Active", type: "boolean" },
  ]},
};

export default function MasterData() {
  const { projectId, dataset } = useParams();
  const { isEditor } = useAuth();
  const meta = DATASET_META[dataset];
  const [rows, setRows] = useState([]);
  const [dirty, setDirty] = useState({}); // id -> patch
  const [creating, setCreating] = useState([]); // uncommitted new rows
  const [deleted, setDeleted] = useState([]); // deleted ids
  const [selected, setSelected] = useState(new Set());
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editCell, setEditCell] = useState(null); // {rowId, col}
  const [err, setErr] = useState("");
  const [historyIdx, setHistoryIdx] = useState(0);
  const historyRef = useRef([]);
  const [refData, setRefData] = useState({}); // datasetName -> rows, for "ref" columns

  const loadRefData = useCallback(async () => {
    if (!meta) return;
    const refDatasets = Array.from(new Set(meta.cols.filter((c) => c.type === "ref").map((c) => c.ref)));
    if (refDatasets.length === 0) { setRefData({}); return; }
    try {
      const entries = await Promise.all(refDatasets.map(async (ds) => {
        const { data } = await api.get(`/api/projects/${projectId}/data/${ds}`, { params: { limit: 5000 } });
        return [ds, data.rows];
      }));
      setRefData(Object.fromEntries(entries));
    } catch (e) { /* dropdowns will fall back to raw ids */ }
  }, [projectId, meta]);

  useEffect(() => { loadRefData(); }, [loadRefData]);

  const refOptionLabel = (row) => {
    if (!row) return "";
    const code = row.code ?? "";
    const name = row.name ?? "";
    if (code && name) return `${code} — ${name}`;
    return name || code || row.id;
  };

  const refLabel = (refDataset, id) => {
    if (!id) return "";
    const row = (refData[refDataset] || []).find((r) => r.id === id);
    return row ? refOptionLabel(row) : id;
  };

  const load = useCallback(async () => {
    if (!meta) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/api/projects/${projectId}/data/${dataset}`, {
        params: { q: q || undefined, limit: 2000 },
      });
      setRows(data.rows);
      setDirty({});
      setCreating([]);
      setDeleted([]);
      setSelected(new Set());
      historyRef.current = [];
      setHistoryIdx(0);
    } catch (e) { setErr(formatError(e)); }
    finally { setLoading(false); }
  }, [projectId, dataset, q, meta]);

  useEffect(() => { load(); }, [load]);

  const applyEdit = (rowId, col, value) => {
    if (rowId.startsWith("new_")) {
      setCreating((c) => c.map((r) => (r._id === rowId ? { ...r, [col]: value } : r)));
    } else {
      setRows((rs) => rs.map((r) => (r.id === rowId ? { ...r, [col]: value } : r)));
      setDirty((d) => ({ ...d, [rowId]: { ...(d[rowId] || {}), [col]: value } }));
    }
    // append to history
    const snap = { rowId, col, value };
    const arr = historyRef.current.slice(0, historyIdx);
    arr.push(snap);
    historyRef.current = arr;
    setHistoryIdx(arr.length);
  };

  const addRow = () => {
    const _id = `new_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const empty = { _id };
    meta.cols.forEach((c) => { empty[c.key] = c.type === "boolean" ? false : ""; });
    setCreating((c) => [...c, empty]);
  };

  const deleteSelected = () => {
    const ids = Array.from(selected);
    setRows((rs) => rs.filter((r) => !selected.has(r.id)));
    setCreating((c) => c.filter((r) => !selected.has(r._id)));
    setDeleted((d) => [...d, ...ids.filter((id) => !id.startsWith("new_"))]);
    setSelected(new Set());
  };

  const save = async () => {
    setSaving(true);
    setErr("");
    try {
      // deletes
      for (const id of deleted) {
        await api.delete(`/api/projects/${projectId}/data/${dataset}/${id}`);
      }
      // updates
      for (const [id, patch] of Object.entries(dirty)) {
        const cleanPatch = { ...patch };
        // coerce numbers
        meta.cols.forEach((c) => {
          if (c.type === "number" && cleanPatch[c.key] !== undefined && cleanPatch[c.key] !== "") {
            cleanPatch[c.key] = Number(cleanPatch[c.key]);
          }
          if (c.type === "boolean" && cleanPatch[c.key] !== undefined) {
            cleanPatch[c.key] = !!cleanPatch[c.key];
          }
        });
        await api.put(`/api/projects/${projectId}/data/${dataset}/${id}`, cleanPatch);
      }
      // creates
      for (const row of creating) {
        const payload = {};
        meta.cols.forEach((c) => {
          let v = row[c.key];
          if (c.type === "number") v = v === "" || v === null ? null : Number(v);
          if (c.type === "boolean") v = !!v;
          if (v !== "" && v !== null && v !== undefined) payload[c.key] = v;
        });
        await api.post(`/api/projects/${projectId}/data/${dataset}`, payload);
      }
      await load();
    } catch (e) { setErr(formatError(e)); }
    finally { setSaving(false); }
  };

  // Copy selection to clipboard as TSV
  const copySelection = async () => {
    const displayRows = combined;
    const selectedRows = displayRows.filter((r) => selected.has(r.id || r._id));
    if (selectedRows.length === 0) return;
    const tsv = selectedRows.map((r) => meta.cols.map((c) => r[c.key] ?? "").join("\t")).join("\n");
    try {
      await navigator.clipboard.writeText(tsv);
    } catch (e) {
      setErr("Copy to clipboard was blocked by the browser. Grant clipboard permission and try again.");
    }
  };

  // Paste TSV into rows starting at current selection
  const pasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      const lines = text.replace(/\r/g, "").split("\n").filter((l) => l !== "");
      const newRows = lines.map((line) => {
        const cells = line.split("\t");
        const _id = `new_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
        const obj = { _id };
        meta.cols.forEach((c, i) => { obj[c.key] = cells[i] ?? ""; });
        return obj;
      });
      setCreating((c) => [...c, ...newRows]);
    } catch (e) { setErr("Clipboard paste not permitted"); }
  };

  const combined = useMemo(() => {
    if (!meta) return [];
    const filtered = q
      ? rows.filter((r) => meta.cols.some((c) => String(r[c.key] ?? "").toLowerCase().includes(q.toLowerCase())))
      : rows;
    return [...filtered, ...creating.map((c) => ({ ...c, id: c._id }))];
  }, [rows, creating, q, meta]);

  const hasChanges = Object.keys(dirty).length + creating.length + deleted.length > 0;

  if (!meta) {
    return (
      <div className="p-6">
        <div className="chip chip-warn">Unknown dataset “{dataset}”</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" data-testid={`master-data-${dataset}`}>
      {/* Ribbon */}
      <div className="bg-white border-b border-neutral-300 flex items-center gap-2 px-3 py-2 sticky top-0 z-10">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mr-3">{meta.label}</div>
        {isEditor && (
          <>
            <button data-testid="add-row-btn" className="ribbon-button" onClick={addRow}><Plus className="w-3.5 h-3.5" /> Row</button>
            <button data-testid="delete-row-btn" className="ribbon-button danger" disabled={selected.size === 0} onClick={deleteSelected}>
              <Trash2 className="w-3.5 h-3.5" /> Delete ({selected.size})
            </button>
            <button data-testid="paste-btn" className="ribbon-button" onClick={pasteFromClipboard}><ClipboardPaste className="w-3.5 h-3.5" /> Paste</button>
          </>
        )}
        <button data-testid="copy-btn" className="ribbon-button" onClick={copySelection} disabled={selected.size === 0}>Copy</button>
        <div className="w-px h-6 bg-neutral-300 mx-1" />
        <button className="ribbon-button" onClick={() => { load(); loadRefData(); }}><RefreshCw className="w-3.5 h-3.5" /> Reload</button>
        <div className="flex-1" />
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            data-testid="search-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search…"
            className="h-8 pl-7 pr-2 border border-neutral-300 text-xs w-52"
          />
        </div>
        {isEditor && (
          <button data-testid="save-btn" className="ribbon-button primary" disabled={!hasChanges || saving} onClick={save}>
            <Save className="w-3.5 h-3.5" /> {saving ? "Saving…" : `Save${hasChanges ? ` (${Object.keys(dirty).length + creating.length + deleted.length})` : ""}`}
          </button>
        )}
      </div>

      {err && <div className="chip chip-err normal-case tracking-normal py-2 m-3">{err}</div>}

      <div className="flex-1 overflow-auto bg-white">
        {loading ? (
          <div className="p-6 text-sm text-neutral-500">Loading…</div>
        ) : (
          <table className="tt-grid" data-testid="master-grid">
            <thead>
              <tr>
                <th className="row-idx">
                  <input
                    type="checkbox"
                    aria-label="select all"
                    onChange={(e) => setSelected(e.target.checked ? new Set(combined.map((r) => r.id)) : new Set())}
                    checked={combined.length > 0 && selected.size === combined.length}
                  />
                </th>
                <th style={{ width: 44 }}>#</th>
                {meta.cols.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {combined.map((row, i) => {
                const rowId = row.id || row._id;
                const isSelected = selected.has(rowId);
                const isNew = String(rowId).startsWith("new_");
                const isDirty = !!dirty[rowId];
                return (
                  <tr key={rowId} className={isSelected ? "selected" : ""}>
                    <td className="row-idx">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          const next = new Set(selected);
                          if (e.target.checked) next.add(rowId); else next.delete(rowId);
                          setSelected(next);
                        }}
                      />
                    </td>
                    <td className="row-idx">
                      {i + 1}
                      {isNew && <span className="ml-1 text-emerald-700">+</span>}
                      {isDirty && !isNew && <span className="ml-1 text-amber-600">•</span>}
                    </td>
                    {meta.cols.map((c) => {
                      const editing = editCell && editCell.rowId === rowId && editCell.col === c.key;
                      const val = row[c.key];
                      return (
                        <td
                          key={c.key}
                          className={editing ? "editing" : ""}
                          onDoubleClick={() => isEditor && setEditCell({ rowId, col: c.key })}
                          data-testid={`cell-${rowId}-${c.key}`}
                        >
                          {editing ? (
                            c.type === "boolean" ? (
                              <select
                                autoFocus
                                defaultValue={val ? "true" : "false"}
                                onBlur={(e) => { applyEdit(rowId, c.key, e.target.value === "true"); setEditCell(null); }}
                              >
                                <option value="true">true</option>
                                <option value="false">false</option>
                              </select>
                            ) : c.type === "ref" ? (
                              <select
                                autoFocus
                                defaultValue={val ?? ""}
                                onChange={(e) => { applyEdit(rowId, c.key, e.target.value || null); setEditCell(null); }}
                                onBlur={() => setEditCell(null)}
                              >
                                <option value="">—</option>
                                {(refData[c.ref] || []).map((r) => (
                                  <option key={r.id} value={r.id}>{refOptionLabel(r)}</option>
                                ))}
                              </select>
                            ) : (
                              <input
                                autoFocus
                                defaultValue={val ?? ""}
                                type={c.type === "number" ? "number" : "text"}
                                onBlur={(e) => { applyEdit(rowId, c.key, c.type === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value); setEditCell(null); }}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") { e.target.blur(); }
                                  if (e.key === "Escape") { setEditCell(null); }
                                }}
                              />
                            )
                          ) : (
                            <span className={c.type === "number" ? "font-mono" : ""}>{
                              c.type === "boolean" ? (val ? "✓" : "") : c.type === "ref" ? refLabel(c.ref, val) : String(val ?? "")
                            }</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              {combined.length === 0 && (
                <tr>
                  <td colSpan={meta.cols.length + 2} className="text-center text-neutral-500 py-8">
                    No records. {isEditor && "Click ‘Add Row’ or use the Import Wizard."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      <div className="status-bar">
        <span>{combined.length} rows</span>
        {selected.size > 0 && <span>{selected.size} selected</span>}
        {hasChanges && <span className="text-amber-700">unsaved: +{creating.length} ~{Object.keys(dirty).length} -{deleted.length}</span>}
        <div className="flex-1" />
        <span className="font-mono">Double-click a cell to edit · Enter to commit · Esc to cancel</span>
      </div>
    </div>
  );
}
