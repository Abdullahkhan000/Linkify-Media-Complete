import Link from "next/link";
import { Logo } from "./logo";

export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <Logo />
        <span>© 2026 Linkify Media. Built for serious products.</span>
        <div className="footer-links"><Link href="/docs">Docs</Link><Link href="/pricing">Pricing</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link></div>
      </div>
    </footer>
  );
}
