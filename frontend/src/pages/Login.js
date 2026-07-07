import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatError } from "@/api/client";
import { Grid3x3, Calendar, Users, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@timetable.app");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email.trim(), password);
      nav("/", { replace: true });
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-shell" data-testid="login-page">
      <div className="login-hero">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-white flex items-center justify-center">
              <Grid3x3 className="w-4 h-4 text-black" />
            </div>
            <div className="font-mono text-xs uppercase tracking-[0.25em] text-neutral-400">
              Timetable OS
            </div>
          </div>
          <h1 className="text-5xl font-black tracking-tight leading-[1.05]">
            The workstation for<br />school scheduling.
          </h1>
          <p className="mt-6 text-neutral-400 max-w-md text-sm leading-relaxed">
            Import once. Edit forever. Generate timetables, review conflicts,
            and export reports — all inside a spreadsheet-fast interface.
          </p>
        </div>
        <div className="relative z-10 grid grid-cols-3 gap-4 text-xs text-neutral-400">
          <div className="border-t border-neutral-800 pt-3">
            <Users className="w-4 h-4 mb-2" />
            <div className="text-white font-semibold">Multi-role</div>
            <div>Admin · Planner · Viewer</div>
          </div>
          <div className="border-t border-neutral-800 pt-3">
            <Calendar className="w-4 h-4 mb-2" />
            <div className="text-white font-semibold">Versioned</div>
            <div>Every generation preserved</div>
          </div>
          <div className="border-t border-neutral-800 pt-3">
            <ShieldCheck className="w-4 h-4 mb-2" />
            <div className="text-white font-semibold">Validated</div>
            <div>Live conflict detection</div>
          </div>
        </div>
      </div>

      <div className="flex flex-col justify-center px-12 py-10">
        <div className="max-w-sm w-full mx-auto">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-neutral-500 mb-2">
            Sign in
          </div>
          <h2 className="text-2xl font-bold mb-8">Welcome back</h2>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-neutral-500 block mb-1">
                Email
              </label>
              <input
                data-testid="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full h-9 px-3 border border-neutral-300 focus:border-black focus:outline-none text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-neutral-500 block mb-1">
                Password
              </label>
              <input
                data-testid="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full h-9 px-3 border border-neutral-300 focus:border-black focus:outline-none text-sm"
              />
            </div>

            {error && (
              <div data-testid="login-error" className="chip chip-err w-full justify-start px-3 py-2 normal-case tracking-normal font-medium">
                {error}
              </div>
            )}

            <button
              data-testid="login-submit"
              type="submit"
              disabled={loading}
              className="ribbon-button primary w-full justify-center h-10"
            >
              {loading ? "Signing in…" : "Sign in →"}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-neutral-200 text-xs text-neutral-500 space-y-1">
            <div className="font-semibold text-neutral-700 uppercase tracking-wider">Demo accounts</div>
            <div>admin@timetable.app · admin123</div>
            <div>planner@timetable.app · planner123</div>
            <div>viewer@timetable.app · viewer123</div>
          </div>
        </div>
      </div>
    </div>
  );
}
