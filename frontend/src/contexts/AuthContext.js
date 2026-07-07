import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import api, { formatError } from "@/api/client";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("checking"); // checking | ready

  const bootstrap = useCallback(async () => {
    const token = localStorage.getItem("tt_token");
    if (!token) {
      setStatus("ready");
      return;
    }
    try {
      const { data } = await api.get("/api/auth/me");
      setUser(data);
    } catch (e) {
      localStorage.removeItem("tt_token");
    } finally {
      setStatus("ready");
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = async (email, password) => {
    const { data } = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("tt_token", data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("tt_token");
    setUser(null);
    window.location.href = "/login";
  };

  const isEditor = user?.role === "admin" || user?.role === "planner";
  const isAdmin = user?.role === "admin";

  return (
    <AuthContext.Provider value={{ user, status, login, logout, isEditor, isAdmin, formatError }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
