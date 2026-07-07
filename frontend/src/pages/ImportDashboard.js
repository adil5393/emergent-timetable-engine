import React, { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { formatError } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import ImportWizard from "@/components/ImportWizard";
import { CheckCircle2, AlertTriangle, Circle, Upload, RefreshCw, Table2, Trash2 } from "lucide-react";

export default function ImportDashboard() {
  const { projectId } = useParams();
  const { isEditor } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [wizardDataset, setWizardDataset] = useState(null);
  const [project, setProject] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [{ data: sum }, { data: proj }] = await Promise.all([
        api.get(`/api/projects/${projectId}/import/summary`),
        api.get(`/api/projects/${projectId}`),
      ]);
      setItems(sum);
      setProject(proj);
    } catch (e) { setErr(formatError(e)); }
    finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const handleImportAgain = (ds) => setWizardDataset(ds);
  const handleWizardClose = (refresh) => {
    setWizardDataset(null);
    if (refresh) load();
  };

  return (
    <div className="p-6" data-testid="import-dashboard">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">
            {project?.academic_year || "Project"}
          </div>
          <h1 className="text-2xl font-bold tracking-tight">{project?.name || "Import Dashboard"}</h1>
          <p className="text-sm text-neutral-500 mt-1">Upload master data once. Edit everything in the app after.</p>
        </div>
        <button onClick={load} className="ribbon-button"><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>
      </div>

      {err && <div className="chip chip-err normal-case tracking-normal py-2 mb-4">{err}</div>}

      {loading ? (
        <div className="text-sm text-neutral-500">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {items.map((it) => (
            <DatasetCard
              key={it.dataset_type}
              projectId={projectId}
              item={it}
              onImport={() => isEditor && handleImportAgain(it.dataset_type)}
              isEditor={isEditor}
            />
          ))}
        </div>
      )}

      {wizardDataset && (
        <ImportWizard
          projectId={projectId}
          datasetType={wizardDataset}
          onClose={handleWizardClose}
        />
      )}
    </div>
  );
}

function DatasetCard({ projectId, item, onImport, isEditor }) {
  const statusIcon = item.record_count > 0
    ? <CheckCircle2 className="w-4 h-4 text-emerald-600" />
    : item.validation_status === "warning"
      ? <AlertTriangle className="w-4 h-4 text-amber-600" />
      : <Circle className="w-4 h-4 text-neutral-400" />;

  const statusLabel = item.record_count > 0 ? "Imported" : (item.validation_status === "warning" ? "Required" : "Optional");
  const statusClass = item.record_count > 0 ? "chip-ok" : (item.validation_status === "warning" ? "chip-warn" : "chip-muted");

  return (
    <div className="panel" data-testid={`dataset-card-${item.dataset_type}`}>
      <div className="panel-body">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">
              {item.dataset_type.replace(/_/g, " ")}
            </div>
            <div className="font-semibold text-base leading-tight mt-1">{item.label}</div>
          </div>
          {statusIcon}
        </div>
        <div className="mt-4 flex items-baseline gap-2">
          <span className="font-mono text-3xl font-black">{item.record_count}</span>
          <span className="text-xs text-neutral-500 font-mono">records</span>
        </div>
        <div className="mt-3 text-[11px] text-neutral-500 min-h-[32px]">
          {item.last_imported ? (
            <>
              <div className="font-mono">Last: {new Date(item.last_imported).toLocaleString()}</div>
              {item.issue_count > 0 && <div className="text-amber-700 font-medium">{item.issue_count} row error(s)</div>}
            </>
          ) : (
            <div>Never imported</div>
          )}
        </div>
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <span className={`chip ${statusClass}`}>{statusLabel}</span>
        </div>
        <div className="mt-4 pt-3 border-t border-neutral-200 flex items-center gap-1.5">
          {isEditor && (
            <button
              data-testid={`import-btn-${item.dataset_type}`}
              onClick={onImport}
              className="ribbon-button flex-1 justify-center h-8"
            >
              <Upload className="w-3.5 h-3.5" /> {item.record_count > 0 ? "Import Again" : "Upload"}
            </button>
          )}
          <Link
            to={`/projects/${projectId}/data/${item.dataset_type}`}
            className="ribbon-button flex-1 justify-center h-8"
            data-testid={`edit-btn-${item.dataset_type}`}
          >
            <Table2 className="w-3.5 h-3.5" /> Edit
          </Link>
        </div>
      </div>
    </div>
  );
}
