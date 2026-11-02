import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!localStorage.getItem("lono_token")) { setUser(null); setLoading(false); return; }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      localStorage.removeItem("lono_token");
      setUser(null);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const accept = (data) => {
    localStorage.setItem("lono_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const login = async (email, password) => accept((await api.post("/auth/login", { email, password })).data);
  const register = async (email, password, name) =>
    accept((await api.post("/auth/register", { email, password, name })).data);
  const googleLogin = async (credential) => accept((await api.post("/auth/google", { credential })).data);

  const logout = () => {
    localStorage.removeItem("lono_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, googleLogin, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
