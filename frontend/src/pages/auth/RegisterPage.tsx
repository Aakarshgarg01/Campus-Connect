import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, BookOpenCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataState, Logo } from "@/components/campus/core";
import { useAuth } from "@/context/auth-context";
import { getApiErrorMessage } from "@/lib/api-error";
import { authApi, workspaceOf } from "@/services/authApi";

const EMPTY = {
  name: "",
  email: "",
  roll_number: "",
  department: "",
  semester: "1",
  password: "",
  confirm: "",
};

export function RegisterPage() {
  const [form, setForm] = useState(EMPTY);
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

  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirm) {
      setError("The two passwords do not match.");
      return;
    }
    if (!/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)) {
      setError("Password must contain at least one letter and one digit.");
      return;
    }
    setBusy(true);
    try {
      await authApi.register({
        name: form.name,
        email: form.email,
        roll_number: form.roll_number,
        department: form.department,
        semester: Number(form.semester),
        password: form.password,
      });
      await login(form.roll_number, form.password);
      nav({ to: "/student/dashboard", replace: true });
    } catch (registerError) {
      setError(getApiErrorMessage(registerError));
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
            <span className="eyebrow">Student registration</span>
            <h1>
              Create your account
              <br />
              to see your progress.
            </h1>
            <p>
              If your faculty has already added you, use the same roll number and email so your
              records are linked to your account.
            </p>
          </div>
          <div className="login-proof">
            <BookOpenCheck />
            <div>
              <strong>Your data, explained</strong>
              <span>
                Predictions come with the factors behind them and suggestions based on your own
                marks.
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
          <span className="eyebrow">New student</span>
          <h2>Create an account</h2>
          <p>Faculty accounts are created by an administrator.</p>
          <label>
            Full name
            <Input
              value={form.name}
              onChange={set("name")}
              autoComplete="name"
              required
              maxLength={120}
            />
          </label>
          <label>
            Email
            <Input
              type="email"
              value={form.email}
              onChange={set("email")}
              autoComplete="email"
              required
            />
          </label>
          <div className="form-pair">
            <label>
              Roll number
              <Input
                value={form.roll_number}
                onChange={set("roll_number")}
                required
                maxLength={32}
              />
            </label>
            <label>
              Semester
              <select className="native-select" value={form.semester} onChange={set("semester")}>
                {Array.from({ length: 12 }, (_, i) => (
                  <option key={i + 1} value={i + 1}>
                    {i + 1}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Department
            <Input value={form.department} onChange={set("department")} required maxLength={120} />
          </label>
          <div className="form-pair">
            <label>
              Password
              <Input
                type="password"
                value={form.password}
                onChange={set("password")}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
              />
            </label>
            <label>
              Confirm password
              <Input
                type="password"
                value={form.confirm}
                onChange={set("confirm")}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
              />
            </label>
          </div>
          <small className="field-hint">
            At least 8 characters, including a letter and a digit.
          </small>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
            <ArrowRight />
          </Button>
          <p className="auth-switch">
            Already registered? <Link to="/login">Sign in</Link>
          </p>
        </form>
      </section>
    </div>
  );
}
