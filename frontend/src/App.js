import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "@/App.css";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import LoginPage from "@/pages/Login";
import ProjectsPage from "@/pages/Projects";
import AppShell from "@/layouts/AppShell";
import ImportDashboard from "@/pages/ImportDashboard";
import MasterData from "@/pages/MasterData";
import ValidationCenter from "@/pages/ValidationCenter";
import GeneratePage from "@/pages/GeneratePage";
import TimetableEditor from "@/pages/TimetableEditor";
import ExportsPage from "@/pages/ExportsPage";
import { Toaster } from "sonner";

function RequireAuth({ children }) {
  const { user, status } = useAuth();
  const loc = useLocation();
  if (status === "checking") {
    return <div className="min-h-screen flex items-center justify-center text-sm text-neutral-500">Loading…</div>;
  }
  if (!user) return <Navigate to="/login" replace state={{ from: loc }} />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <ProjectsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/projects/:projectId"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="import" replace />} />
            <Route path="import" element={<ImportDashboard />} />
            <Route path="data/:dataset" element={<MasterData />} />
            <Route path="validation" element={<ValidationCenter />} />
            <Route path="generate" element={<GeneratePage />} />
            <Route path="timetables/:timetableId" element={<TimetableEditor />} />
            <Route path="exports" element={<ExportsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" richColors closeButton />
    </AuthProvider>
  );
}

export default App;
