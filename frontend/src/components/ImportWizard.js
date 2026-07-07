import React, { useEffect, useState } from "react";
import api, { formatError } from "@/api/client";
import { X, Upload, ArrowRight, CheckCircle2, AlertTriangle } from "lucide-react";

const STEPS = ["Upload", "Map Columns", "Preview", "Commit"];

export default function ImportWizard({ projectId, datasetType, onClose }) {
  const [step, setStep] = useState(0);
  const [schema, setSchema] = useState(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null); // { columns, rows, total_rows, suggested_map, file_token, filename }
  const [columnMap, setColumnMap] = useState({}); // source -> target
  const [committing, setCommitting] = useState(false);
  const [result, setResult] = useState(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get(`/api/projects/${projectId}/import/schema`).then(({ data }) => {
      const ds = data.datasets.find((d) => d.dataset_type === datasetType);
      setSchema(ds);
    });
  }, [projectId, datasetType]);

  const doUpload = async () => {
    if (!file) return;
    setUploading(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("dataset_type", datasetType);
      fd.append("file", file);
      const { data } = await api.post(`/api/projects/${projectId}/import/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setPreview(data);
      setColumnMap(data.suggested_map || {});
      setStep(1);
    } catch (e) { setErr(formatError(e)); }
    finally { setUploading(false); }
  };

  const doCommit = async () => {
    setCommitting(true);
    setErr("");
    try {
      const { data } = await api.post(`/api/projects/${projectId}/import/commit`, {
        dataset_type: datasetType,
        file_token: preview.file_token,
        column_map: columnMap,
        filename: preview.filename,
        replace_existing: replaceExisting,
        save_as_template: templateName || null,
      });
      setResult(data);
      setStep(3);
    } catch (e) { setErr(formatError(e)); }
    finally { setCommitting(false); }
  };

  const missingRequired = schema && preview
    ? schema.required.filter((r) => !Object.values(columnMap).includes(r))
    : [];

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => onClose(!!result)}>
      <div className="panel w-[900px] max-w-full max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()} data-testid="import-wizard">
        <div className="panel-header">
          <div className="flex items-center gap-3">
            <span className="uppercase tracking-wider">Import Wizard · {schema?.label || datasetType}</span>
            <div className="flex items-center gap-1 text-[11px] font-mono text-neutral-500">
              {STEPS.map((s, i) => (
                <span key={s} className={`px-1.5 py-0.5 border ${i === step ? "bg-black text-white border-black" : "border-neutral-300"}`}>
                  {i + 1}. {s}
                </span>
              ))}
            </div>
          </div>
          <button onClick={() => onClose(!!result)} className="text-neutral-500 hover:text-black" data-testid="wizard-close"><X className="w-4 h-4" /></button>
        </div>

        <div className="panel-body overflow-auto flex-1">
          {err && <div className="chip chip-err normal-case tracking-normal py-2 mb-3">{err}</div>}

          {step === 0 && (
            <div className="space-y-4">
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Choose a file</div>
                <label className="border-2 border-dashed border-neutral-300 hover:border-black p-8 block cursor-pointer text-center">
                  <Upload className="w-6 h-6 mx-auto mb-2 text-neutral-500" />
                  <div className="text-sm">{file ? file.name : "Click to select .xlsx, .xls or .csv"}</div>
                  <input
                    data-testid="wizard-file-input"
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
              </div>
              {schema && (
                <div className="text-xs text-neutral-500">
                  <div className="font-semibold mb-1">Expected fields:</div>
                  <div className="flex flex-wrap gap-1">
                    {schema.fields.map((f) => (
                      <span key={f} className={`chip ${schema.required.includes(f) ? "chip-warn" : "chip-muted"} normal-case tracking-normal`}>
                        {f}{schema.required.includes(f) && " *"}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex justify-end pt-4 border-t border-neutral-200">
                <button data-testid="wizard-next-0" disabled={!file || uploading} onClick={doUpload} className="ribbon-button primary">
                  {uploading ? "Uploading…" : <>Next <ArrowRight className="w-3.5 h-3.5" /></>}
                </button>
              </div>
            </div>
          )}

          {step === 1 && preview && schema && (
            <div className="space-y-4">
              <div className="text-xs text-neutral-500">Map each column from your file to a target field. Auto-mapped where possible.</div>
              <div className="border border-neutral-300">
                <table className="tt-grid">
                  <thead>
                    <tr>
                      <th style={{ width: "50%" }}>Source column (from file)</th>
                      <th>Maps to</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.columns.map((col) => (
                      <tr key={col}>
                        <td className="font-mono">{col}</td>
                        <td>
                          <select
                            data-testid={`map-${col}`}
                            value={columnMap[col] || ""}
                            onChange={(e) => setColumnMap({ ...columnMap, [col]: e.target.value })}
                            className="w-full border border-neutral-300 h-7 px-1 text-xs"
                          >
                            <option value="">— skip —</option>
                            {schema.fields.map((f) => (
                              <option key={f} value={f}>{f}{schema.required.includes(f) && " *"}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {missingRequired.length > 0 && (
                <div className="chip chip-warn normal-case tracking-normal py-2">
                  Missing required fields: {missingRequired.join(", ")}
                </div>
              )}

              <div className="flex items-center justify-between pt-4 border-t border-neutral-200">
                <button className="ribbon-button" onClick={() => setStep(0)}>← Back</button>
                <button data-testid="wizard-next-1" disabled={missingRequired.length > 0} onClick={() => setStep(2)} className="ribbon-button primary">
                  Next <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {step === 2 && preview && (
            <div className="space-y-4">
              <div className="text-xs text-neutral-500">Preview of the first {preview.rows.length} rows (total {preview.total_rows}). Review before committing.</div>
              <div className="border border-neutral-300 overflow-auto max-h-[300px]">
                <table className="tt-grid">
                  <thead>
                    <tr>
                      {preview.columns.map((c) => (
                        <th key={c}>
                          <div className="font-semibold">{columnMap[c] || <em className="text-neutral-400">skip</em>}</div>
                          <div className="text-[10px] text-neutral-500 font-mono">{c}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, i) => (
                      <tr key={`preview-${i}-${row[preview.columns[0]] ?? ""}`}>
                        {preview.columns.map((c) => (
                          <td key={c} className="font-mono text-xs">{String(row[c] ?? "")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex items-center gap-2 text-xs">
                  <input data-testid="wizard-replace" type="checkbox" checked={replaceExisting} onChange={(e) => setReplaceExisting(e.target.checked)} />
                  <span>Replace existing records for this dataset</span>
                </label>
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 block mb-1">
                    Save mapping as template (optional)
                  </label>
                  <input
                    data-testid="wizard-template-name"
                    value={templateName}
                    onChange={(e) => setTemplateName(e.target.value)}
                    placeholder="e.g., Delhi Public School - Teachers"
                    className="w-full h-7 px-2 border border-neutral-300 text-xs"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-neutral-200">
                <button className="ribbon-button" onClick={() => setStep(1)}>← Back</button>
                <button data-testid="wizard-commit" disabled={committing} onClick={doCommit} className="ribbon-button primary">
                  {committing ? "Importing…" : "Commit Import →"}
                </button>
              </div>
            </div>
          )}

          {step === 3 && result && (
            <div className="text-center py-8">
              {result.imported_rows > 0 ? (
                <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-600 mb-3" />
              ) : (
                <AlertTriangle className="w-10 h-10 mx-auto text-amber-600 mb-3" />
              )}
              <h3 className="text-xl font-bold">Import Complete</h3>
              <div className="mt-3 flex justify-center gap-6 font-mono text-sm">
                <span><b>{result.total_rows}</b> total</span>
                <span className="text-emerald-700"><b>{result.imported_rows}</b> imported</span>
                <span className="text-red-700"><b>{result.error_rows}</b> errors</span>
              </div>
              {result.errors && result.errors.length > 0 && (
                <div className="mt-4 max-h-40 overflow-auto text-left border border-neutral-300 p-2 text-xs font-mono">
                  {result.errors.slice(0, 50).map((e, i) => (
                    <div key={`err-${e.row}-${i}`}>Row {e.row}: {e.error}</div>
                  ))}
                </div>
              )}
              <button className="ribbon-button primary mt-6" onClick={() => onClose(true)} data-testid="wizard-done">Done</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
