import React from "react";
import { NavLink, Outlet, useParams, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutGrid, Upload, Table2, ShieldAlert, CalendarClock, FileDown, Users2, ChevronLeft, LogOut, Grid3x3, CircleDot,
} from "lucide-react";

const NAV = [
  { to: "import", label: "Import Dashboard", icon: Upload },
  { to: "data/teachers", label: "Teachers", icon: Users2 },
  { to: "data/subjects", label: "Subjects", icon: Table2 },
  { to: "data/classes", label: "Classes", icon: Table2 },
  { to: "data/sections", label: "Sections", icon: Table2 },
  { to: "data/rooms", label: "Rooms", icon: Table2 },
  { to: "data/departments", label: "Departments", icon: Table2 },
  { to: "data/teacher_mapping", label: "Teacher Mapping", icon: Table2 },
  { to: "data/weekly_priority", label: "Weekly Priorities", icon: Table2 },
  { to: "data/school_timing", label: "School Timing", icon: Table2 },
  { to: "data/constraints", label: "Constraints", icon: Table2 },
  { to: "validation", label: "Validation Center", icon: ShieldAlert },
  { to: "generate", label: "Generate & Versions", icon: CalendarClock },
  { to: "exports", label: "Exports", icon: FileDown },
];

export default function AppShell() {
  const { projectId } = useParams();
  const { user, logout } = useAuth();
  const loc = useLocation();

  const base = `/projects/${projectId}`;

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <header className="h-11 border-b border-neutral-300 bg-white flex items-center px-3 gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-black flex items-center justify-center">
            <Grid3x3 className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-mono text-[11px] uppercase tracking-[0.2em]">Timetable OS</span>
        </div>
        <NavLink to="/" className="ribbon-button" data-testid="back-projects">
          <ChevronLeft className="w-3.5 h-3.5" /> Projects
        </NavLink>
        <div className="flex-1" />
        <div className="text-xs text-neutral-500 font-mono">
          {user?.email} · <span className="uppercase font-semibold">{user?.role}</span>
        </div>
        <button data-testid="logout-btn" className="ribbon-button" onClick={logout}>
          <LogOut className="w-3.5 h-3.5" /> Logout
        </button>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-56 bg-neutral-50 border-r border-neutral-300 shrink-0 overflow-y-auto">
          <div className="p-2 text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mt-2 mb-1 px-3">
            Project
          </div>
          <nav className="px-2 flex flex-col gap-0.5">
            {NAV.map((item) => {
              const Icon = item.icon;
              const to = `${base}/${item.to}`;
              const active = loc.pathname.startsWith(to);
              return (
                <NavLink
                  key={item.to}
                  to={to}
                  className={`sidebar-link ${active ? "active" : ""}`}
                  data-testid={`nav-${item.to.replace(/\//g, "-")}`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto bg-neutral-100">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
