import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api, { formatError } from "@/api/client";
import { FileDown, FileSpreadsheet, FileText, Info } from "lucide-react";

export default function ExportsPage() {
  const { projectId } = useParams();
  const [versions, setVersions] = useState([]);
  const [reports, setReports] = useState([]);
  const [version, setVersion] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const [v, r] = await Promise.all([
        api.get(`/api/projects/${projectId}/timetables`),
        api.get(`/api/projects/${projectId}/timetables/reports/list`),
      ]);
      setVersions(v.data);
      setReports(r.data);
      if (v.data.length && !version) setVersion(v.data[0].id);
    } catch (e) { setErr(formatError(e)); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const download = async (reportKey, fmt) => {
    if (!version) return;
    try {
      const res = await api.get(`/api/projects/${projectId}/timetables/${version}/export`, {
        params: { report: reportKey, fmt },
        responseType: "blob",
      });
      const filename = `${reportKey}.${fmt}`;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) { setErr(formatError(e)); }
  };

  return (
    <div className="p-6" data-testid="exports-page">
      <div className="mb-6">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">Output</div>
        <h1 className="text-2xl font-bold tracking-tight">Exports</h1>
        <p className="text-sm text-neutral-500 mt-1">Generate xlsx or csv for every report. PDF will be added without changing the URLs.</p>
      </div>

      {err && <div className="chip chip-err normal-case tracking-normal py-2 mb-4">{err}</div>}

      <div className="panel mb-6">
        <div className="panel-body flex items-center gap-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">Version</div>
          <select
            data-testid="version-select"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            className="h-8 px-2 border border-neutral-300 text-sm min-w-[220px]"
          >
            {versions.length === 0 && <option value="">— No timetables generated yet —</option>}
            {versions.map((v) => (
              <option key={v.id} value={v.id}>v{v.version} · {v.name || "Untitled"}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {reports.map((r) => (
          <div key={r.key} className="panel" data-testid={`report-${r.key}`}>
            <div className="panel-body">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">Report</div>
                  <div className="font-semibold text-base mt-1 leading-tight">{r.label}</div>
                </div>
                <FileDown className="w-4 h-4 text-neutral-400" />
              </div>
              <div className="mt-4 flex gap-1">
                <button className="ribbon-button flex-1 justify-center" disabled={!version} onClick={() => download(r.key, "xlsx")} data-testid={`dl-xlsx-${r.key}`}>
                  <FileSpreadsheet className="w-3.5 h-3.5" /> Excel
                </button>
                <button className="ribbon-button flex-1 justify-center" disabled={!version} onClick={() => download(r.key, "csv")} data-testid={`dl-csv-${r.key}`}>
                  <FileText className="w-3.5 h-3.5" /> CSV
                </button>
                <button className="ribbon-button flex-1 justify-center" disabled title="PDF export coming soon">
                  PDF
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 text-xs text-neutral-500 flex items-center gap-2">
        <Info className="w-3.5 h-3.5" /> PDF export uses the same DataFrame contract as Excel; wiring a PDF renderer will not change these URLs.
      </div>
    </div>
  );
}
