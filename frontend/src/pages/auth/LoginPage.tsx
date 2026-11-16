import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, BookOpenCheck, CheckCircle2, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataState, Logo } from "@/components/campus/core";
import { useAuth } from "@/context/auth-context";
import { getApiErrorMessage } from "@/lib/api-error";
import type { AuthRole } from "@/services/authApi";
export function LoginPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<AuthRole>("student");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { user, isLoading, login } = useAuth();
  const nav = useNavigate();
  useEffect(() => {
    if (!isLoading && user)
      nav({
        to: user.role === "student" ? "/student/dashboard" : "/faculty/dashboard",
        replace: true,
      });
  }, [isLoading, user, nav]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const authenticatedUser = await login(identifier, password);
      nav({
        to: authenticatedUser.role === "student" ? "/student/dashboard" : "/faculty/dashboard",
        replace: true,
      });
    } catch (loginError) {
      setError(getApiErrorMessage(loginError));
    } finally {
      setBusy(false);
    }
  }
  if (isLoading)
    return (
      <div className="center-state">
        <DataState type="loading" title="Restoring your session…" />
      </div>
    );
  return (
    <div className="login-page">
      <section className="login-context">
        <div>
          <Logo />
          <div className="login-message">
            <span className="eyebrow">Academic early-warning system</span>
            <h1>
              See performance early.
              <br />
              Act before it’s too late.
            </h1>
            <p>
              A focused academic workspace for understanding semester progress, supporting students,
              and acting on evidence.
            </p>
          </div>
          <div className="login-proof">
            <BookOpenCheck />
            <div>
              <strong>Semester workflow, clearly connected</strong>
              <span>
                Internal assessments, predictions, targets, benchmarks, and faculty monitoring in
                one dependable record.
              </span>
            </div>
          </div>
        </div>
        <footer>CampusConnect · Academic performance monitoring</footer>
      </section>
      <section className="login-form-area">
        <form onSubmit={submit} className="login-form">
          <div className="mobile-logo">
            <Logo />
          </div>
          <span className="eyebrow">Welcome back</span>
          <h2>Sign in to CampusConnect</h2>
          <p>Use your institutional account to continue.</p>
          <label>
            Institutional ID or email
            <Input
              type="text"
              autoComplete="username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <div className="password-field">
              <Input
                type={show ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setShow(!show)}
                aria-label={show ? "Hide password" : "Show password"}
              >
                {show ? <EyeOff /> : <Eye />}
              </Button>
            </div>
          </label>
          <div className="forgot">
            <button type="button">Forgot password?</button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <fieldset>
            <legend>Quick account</legend>
            <div className="role-options">
              {(["student", "faculty"] as Role[]).map((r) => (
                <button
                  type="button"
                  key={r}
                  className={role === r ? "selected" : ""}
                  onClick={() => {
                    setRole(r);
                    setIdentifier(r === "student" ? "CS21041" : "FAC1024");
                  }}
                >
                  <span>
                    <b>{r === "student" ? "Student" : "Faculty"}</b>
                    <small>
                      {r === "student" ? "View personal performance" : "Monitor a semester cohort"}
                    </small>
                  </span>
                  {role === r && <CheckCircle2 />}
                </button>
              ))}
            </div>
            <small>The server verifies your account and determines your workspace.</small>
          </fieldset>
          <Button type="submit" size="lg" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
            <ArrowRight />
          </Button>
        </form>
      </section>
    </div>
  );
}
