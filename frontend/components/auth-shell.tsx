import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Logo } from "./logo";

export function AuthShell({ children, title = "Ship media experiences, not data pipelines." }: { children: React.ReactNode; title?: string }) {
  return (
    <main className="auth-page">
      <section className="auth-panel">
        <Logo />
        <div className="auth-main">{children}</div>
        <small style={{ color: "var(--muted)" }}>By continuing, you agree to our <Link className="auth-link" href="/terms">Terms</Link>.</small>
      </section>
      <aside className="auth-art" aria-hidden="true">
        <div className="auth-art-content">
          <span className="eyebrow" style={{ color: "white", borderColor: "rgba(255,255,255,.3)", background: "rgba(255,255,255,.12)" }}><Sparkles size={14} /> Built for product teams</span>
          <h2 className="display">{title}</h2>
          <p>Search, metadata, watch providers and analytics—unified behind one secure, versioned API.</p>
          <div className="quote-card"><b>“The cleanest developer experience in our stack.”</b><p style={{ fontSize: 14, marginBottom: 0 }}>— Product team, Northstar Labs</p></div>
        </div>
      </aside>
    </main>
  );
}
