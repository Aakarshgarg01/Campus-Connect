import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, BookOpenCheck, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataState, Logo } from "@/components/campus/core";
import { useAuth } from "@/context/auth-context";
import { getApiErrorMessage } from "@/lib/api-error";
import { workspaceOf } from "@/services/authApi";
import { Link } from "@tanstack/react-router";
export function LoginPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { user, isLoading, login } = useAuth();
  const nav = useNavigate();
  useEffect(() => {
    if (!isLoading && user)
      nav({
        to: workspaceOf(user) === "student" ? "/student/dashboard" : "/faculty/dashboard",
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
        to:
          workspaceOf(authenticatedUser) === "student"
            ? "/student/dashboard"
            : "/faculty/dashboard",
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
          <p>Sign in with your email, roll number or staff ID.</p>
          <label>
            Email, roll number or staff ID
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
                autoComplete="current-password"
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
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
            <ArrowRight />
          </Button>
          <p className="auth-switch">
            New student? <Link to="/register">Create an account</Link>
          </p>
          <p className="auth-switch">Faculty accounts are created by an administrator.</p>
        </form>
      </section>
    </div>
  );
}
