import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Logo } from "./logo";

export function MarketingNav() {
  return (
    <nav className="site-nav">
      <div className="container nav-inner">
        <Logo />
        <div className="nav-links">
          <Link href="/#features">Product</Link>
          <Link href="/docs">Developers</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/#security">Security</Link>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-secondary" href="/login">Sign in</Link>
          <Link className="btn btn-primary" href="/signup">Start building <ArrowUpRight size={16} /></Link>
        </div>
      </div>
    </nav>
  );
}
