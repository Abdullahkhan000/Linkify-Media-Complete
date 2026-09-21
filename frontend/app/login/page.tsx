"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { LockKeyhole, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth-shell";
import { SocialButtons } from "@/components/social-buttons";
import { AuthResponse, backend, errorMessage, session } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    session().then((value) => { if (value.meta?.is_authenticated) router.replace("/dashboard"); }).catch(() => undefined);
    if (new URLSearchParams(window.location.search).get("social") === "error") {
      const timer = window.setTimeout(() => setError("Social sign-in was cancelled or could not be completed."), 0);
      return () => window.clearTimeout(timer);
    }
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    const login = String(data.get("login") ?? "").trim();
    const payload = { [login.includes("@") ? "email" : "username"]: login, password: data.get("password") };
    try {
      const result = await backend<AuthResponse>("_allauth/browser/v1/auth/login", { method: "POST", body: JSON.stringify(payload) });
      if (!result.meta?.is_authenticated) throw new Error("Sign-in needs another verification step.");
      router.replace("/dashboard"); router.refresh();
    } catch (reason) { setError(errorMessage(reason)); setBusy(false); }
  }

  return <AuthShell><div className="auth-card"><h1 className="display">Welcome back.</h1><p>Enter the console and keep building.</p>{error&&<div className="form-alert error" role="alert">{error}</div>}<form className="form-grid" onSubmit={submit} style={{marginTop:18}}><div className="field"><label htmlFor="login">Email or username</label><div className="input-wrap"><Mail className="field-icon" size={18}/><input className="input has-icon" id="login" name="login" autoComplete="username" required placeholder="you@company.com"/></div></div><div className="field"><div className="form-meta"><label htmlFor="password">Password</label><Link href="/forgot-password">Forgot password?</Link></div><div className="input-wrap"><LockKeyhole className="field-icon" size={18}/><input className="input has-icon" id="password" name="password" type="password" autoComplete="current-password" required placeholder="Your password"/></div></div><button className="btn btn-primary btn-full" disabled={busy}>{busy?"Signing in…":"Sign in to your account"}</button></form><SocialButtons onError={setError}/><p style={{textAlign:"center",marginTop:24,color:"var(--muted)"}}>New to Linkify? <Link className="auth-link" href="/signup">Create an account</Link></p></div></AuthShell>;
}
