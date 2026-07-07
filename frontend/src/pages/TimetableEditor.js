import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import api, { formatError } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import { Lock, LockOpen, Trash, RefreshCw, ArrowLeftRight, AlertTriangle } from "lucide-react";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function TimetableEditor() {
  const { projectId, timetableId } = useParams();
  const { isEditor } = useAuth();
  const [tt, setTt] = useState(null);
  const [entries, setEntries] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [classes, setClasses] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [selectedClass, setSelectedClass] = useState("");
  const [selected, setSelected] = useState(null); // entry id
  const [dragEntryId, setDragEntryId] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ttR, entR, confR, mds] = await Promise.all([
        api.get(`/api/projects/${projectId}/timetables/${timetableId}`),
        api.get(`/api/projects/${projectId}/timetables/${timetableId}/entries`),
        api.get(`/api/projects/${projectId}/timetables/${timetableId}/conflicts`),
        Promise.all([
          api.get(`/api/projects/${projectId}/data/teachers`),
          api.get(`/api/projects/${projectId}/data/subjects`),
          api.get(`/api/projects/${projectId}/data/classes`),
          api.get(`/api/projects/${projectId}/data/rooms`),
        ]),
      ]);
      setTt(ttR.data);
      setEntries(entR.data);
      setConflicts(confR.data.conflicts || []);
      setTeachers(mds[0].data.rows);
      setSubjects(mds[1].data.rows);
      setClasses(mds[2].data.rows);
      setRooms(mds[3].data.rows);
      const firstClassId = mds[2].data.rows[0]?.id;
      if (firstClassId) setSelectedClass((cur) => cur || firstClassId);
    } catch (e) { setErr(formatError(e)); }
    finally { setLoading(false); }
  }, [projectId, timetableId]);

  useEffect(() => { load(); }, [load]);

  const [projectMeta, setProjectMeta] = useState({ working_days: 5, periods_per_day: 8 });
  useEffect(() => {
    if (projectId) api.get(`/api/projects/${projectId}`).then(({ data }) => setProjectMeta(data));
  }, [projectId]);

  const teacherMap = useMemo(() => Object.fromEntries(teachers.map((t) => [t.id, t])), [teachers]);
  const subjectMap = useMemo(() => Object.fromEntries(subjects.map((s) => [s.id, s])), [subjects]);
  const roomMap = useMemo(() => Object.fromEntries(rooms.map((r) => [r.id, r])), [rooms]);
  const classMap = useMemo(() => Object.fromEntries(classes.map((c) => [c.id, c])), [classes]);

  const conflictEntryIds = useMemo(() => {
    const s = new Set();
    conflicts.forEach((c) => c.entry_ids?.forEach((id) => s.add(id)));
    return s;
  }, [conflicts]);

  const grid = useMemo(() => {
    if (!selectedClass) return {};
    const g = {};
    entries.filter((e) => e.class_id === selectedClass).forEach((e) => {
      g[`${e.day_of_week}-${e.period_number}`] = e;
    });
    return g;
  }, [entries, selectedClass]);

  const days = projectMeta.working_days || 5;
  const periods = projectMeta.periods_per_day || 8;

  const patchEntry = async (id, patch) => {
    try {
      const full = entries.find((e) => e.id === id);
      const merged = { ...full, ...patch };
      const { data } = await api.patch(`/api/projects/${projectId}/timetables/${timetableId}/entries/${id}`, {
        day_of_week: merged.day_of_week,
        period_number: merged.period_number,
        class_id: merged.class_id,
        section_id: merged.section_id,
        subject_id: merged.subject_id,
        teacher_id: merged.teacher_id,
        room_id: merged.room_id,
        is_locked: merged.is_locked,
        note: merged.note,
      });
      setEntries((es) => es.map((e) => (e.id === id ? data : e)));
      // Refresh conflicts
      const { data: c } = await api.get(`/api/projects/${projectId}/timetables/${timetableId}/conflicts`);
      setConflicts(c.conflicts || []);
    } catch (e) { setErr(formatError(e)); }
  };

  const toggleLock = async (id) => {
    try {
      await api.post(`/api/projects/${projectId}/timetables/${timetableId}/entries/${id}/toggle-lock`);
      setEntries((es) => es.map((e) => (e.id === id ? { ...e, is_locked: !e.is_locked } : e)));
    } catch (e) { setErr(formatError(e)); }
  };

  const swap = async (aId, bId) => {
    try {
      await api.post(`/api/projects/${projectId}/timetables/${timetableId}/entries/swap`, { a_id: aId, b_id: bId });
      await load();
    } catch (e) { setErr(formatError(e)); }
  };

  const onDrop = (e, cellKey) => {
    e.preventDefault();
    if (!dragEntryId) return;
    const target = grid[cellKey];
    if (target && target.id !== dragEntryId) {
      swap(dragEntryId, target.id);
    }
    setDragEntryId(null);
  };

  const selectedEntry = selected ? entries.find((e) => e.id === selected) : null;

  return (
    <div className="flex flex-col h-full" data-testid="timetable-editor">
      <div className="bg-white border-b border-neutral-300 flex items-center gap-2 px-3 py-2">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mr-2">Timetable</div>
        <select
          data-testid="class-select"
          value={selectedClass}
          onChange={(e) => setSelectedClass(e.target.value)}
          className="h-8 px-2 border border-neutral-300 text-sm"
        >
          {classes.map((c) => (
            <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
          ))}
        </select>
        <div className="w-px h-6 bg-neutral-300 mx-1" />
        <button className="ribbon-button" onClick={load}><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>
        <div className="flex-1" />
        <div className="text-[11px] font-mono text-neutral-500">{tt?.name || ""} · v{tt?.version || "—"}</div>
        {conflicts.length > 0 && (
          <span className="chip chip-err"><AlertTriangle className="w-3 h-3" /> {conflicts.length} conflict(s)</span>
        )}
      </div>

      {err && <div className="chip chip-err normal-case tracking-normal py-2 m-3">{err}</div>}

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="text-sm text-neutral-500">Loading…</div>
          ) : (
            <div
              className="tt-editor"
              style={{ gridTemplateColumns: `70px repeat(${days}, minmax(140px, 1fr))` }}
              data-testid="tt-grid"
            >
              <div className="tt-cell header">Period</div>
              {Array.from({ length: days }).map((_, d) => (
                <div key={`day-${d}`} className="tt-cell header">{DAY_NAMES[d]}</div>
              ))}
              {Array.from({ length: periods }).map((_, p) => (
                <React.Fragment key={`period-${p}`}>
                  <div className="tt-cell header">P{p + 1}</div>
                  {Array.from({ length: days }).map((_, d) => {
                    const key = `${d}-${p + 1}`;
                    const e = grid[key];
                    const isConflict = e && conflictEntryIds.has(e.id);
                    const isSelected = e && selected === e.id;
                    return (
                      <div
                        key={key}
                        className={`tt-cell ${e?.is_locked ? "locked" : ""} ${isConflict ? "conflict" : ""} ${isSelected ? "selected" : ""}`}
                        onClick={() => e && setSelected(e.id)}
                        onDragOver={(ev) => { ev.preventDefault(); ev.currentTarget.classList.add("drop-target"); }}
                        onDragLeave={(ev) => ev.currentTarget.classList.remove("drop-target")}
                        onDrop={(ev) => { ev.currentTarget.classList.remove("drop-target"); onDrop(ev, key); }}
                        draggable={!!e && isEditor && !e.is_locked}
                        onDragStart={() => e && setDragEntryId(e.id)}
                        data-testid={`cell-${d}-${p + 1}`}
                      >
                        {e ? (
                          <>
                            <div className="text-[12px] font-semibold leading-tight">
                              {subjectMap[e.subject_id]?.code || "—"}
                            </div>
                            <div className="text-[11px] text-neutral-500 truncate">
                              {teacherMap[e.teacher_id]?.code || ""}
                            </div>
                            {e.room_id && (
                              <div className="text-[10px] text-neutral-500 font-mono mt-1">
                                {roomMap[e.room_id]?.code}
                              </div>
                            )}
                          </>
                        ) : (
                          <span className="text-neutral-300 text-xs">—</span>
                        )}
                      </div>
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
          )}
        </div>

        {/* Side inspector */}
        <div className="w-72 border-l border-neutral-300 bg-white overflow-y-auto" data-testid="tt-inspector">
          <div className="panel-header">Inspector</div>
          <div className="p-3 text-sm">
            {!selectedEntry ? (
              <div className="text-neutral-500 text-xs">Click a cell to inspect / edit it.</div>
            ) : (
              <div className="space-y-3">
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">
                  {DAY_NAMES[selectedEntry.day_of_week]} · P{selectedEntry.period_number}
                </div>

                <SelectField label="Subject" value={selectedEntry.subject_id} onChange={(v) => patchEntry(selectedEntry.id, { subject_id: v })} options={subjects} disabled={!isEditor} testid="sel-subject" />
                <SelectField label="Teacher" value={selectedEntry.teacher_id} onChange={(v) => patchEntry(selectedEntry.id, { teacher_id: v })} options={teachers} disabled={!isEditor} testid="sel-teacher" />
                <SelectField label="Room" value={selectedEntry.room_id} onChange={(v) => patchEntry(selectedEntry.id, { room_id: v })} options={rooms} disabled={!isEditor} testid="sel-room" />

                <div className="flex gap-1 pt-2 border-t border-neutral-200">
                  <button className="ribbon-button flex-1" onClick={() => toggleLock(selectedEntry.id)} disabled={!isEditor} data-testid="btn-lock">
                    {selectedEntry.is_locked ? <><LockOpen className="w-3.5 h-3.5" /> Unlock</> : <><Lock className="w-3.5 h-3.5" /> Lock</>}
                  </button>
                  <button className="ribbon-button danger" disabled={!isEditor} onClick={() => patchEntry(selectedEntry.id, { subject_id: null, teacher_id: null, room_id: null })} data-testid="btn-clear">
                    <Trash className="w-3.5 h-3.5" /> Clear
                  </button>
                </div>

                {conflictEntryIds.has(selectedEntry.id) && (
                  <div className="chip chip-err normal-case tracking-normal py-2 w-full justify-start">
                    <AlertTriangle className="w-3 h-3" /> This cell participates in a conflict
                  </div>
                )}
              </div>
            )}

            {conflicts.length > 0 && (
              <div className="mt-6 pt-4 border-t border-neutral-200">
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500 mb-2">Conflicts ({conflicts.length})</div>
                <div className="space-y-1 max-h-64 overflow-auto">
                  {conflicts.map((c, i) => (
                    <div key={`${c.type}-${c.day}-${c.period}-${i}`} className="text-xs bg-red-50 border border-red-200 p-2">
                      <div className="font-semibold text-red-800">{c.type.replace(/_/g, " ")}</div>
                      <div className="font-mono text-neutral-600">{DAY_NAMES[c.day]} · P{c.period}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="status-bar">
        <span>{entries.length} entries · {conflicts.length} conflicts</span>
        <div className="flex-1" />
        <span className="font-mono">Drag a cell onto another to swap · Click to inspect</span>
      </div>
    </div>
  );
}

function SelectField({ label, value, onChange, options, disabled, testid }) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">{label}</div>
      <select
        data-testid={testid}
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={disabled}
        className="w-full h-8 px-2 border border-neutral-300 text-sm"
      >
        <option value="">—</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.name} ({o.code})</option>
        ))}
      </select>
    </div>
  );
}
