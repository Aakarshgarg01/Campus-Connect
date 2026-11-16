import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { authApi, type AuthUser } from "@/services/authApi";
import { getApiErrorMessage, getApiErrorStatus } from "@/lib/api-error";

type Auth = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (identifier: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<Auth | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    let active = true;

    authApi
      .getCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setUser(null);
        if (getApiErrorStatus(error) !== 401) {
          toast.error(getApiErrorMessage(error));
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const login = async (identifier: string, password: string) => {
    const authenticatedUser = await authApi.login(identifier, password);
    setUser(authenticatedUser);
    return authenticatedUser;
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
    await queryClient.cancelQueries();
    queryClient.clear();
  };

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: Boolean(user), isLoading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider missing");
  return context;
}
