import Link from "next/link";
import { ArrowRight, BarChart3, Braces, Globe2, Search, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { MarketingNav } from "@/components/marketing-nav";
import { SiteFooter } from "@/components/site-footer";

const brands = ["NORTHSTAR", "MOTION", "KITEWORKS", "PIXELHAUS", "PLATFORM", "NORTHSTAR", "MOTION", "KITEWORKS", "PIXELHAUS", "PLATFORM"];

export default function Home() {
  return (
    <><MarketingNav /><main>
      <section className="hero"><div className="container hero-grid">
        <div className="hero-copy"><span className="eyebrow">The media data layer</span><h1 className="display">Build the next <span>obsession.</span></h1><p>Rich movie and TV metadata, discovery, people and watch availability—delivered through one beautifully predictable API.</p><div className="hero-actions"><Link href="/signup" className="btn btn-primary">Get your API key <ArrowRight size={17} /></Link><Link href="/docs" className="btn btn-secondary"><Braces size={17} /> Explore the docs</Link></div><div className="trust-row"><div className="avatar-stack"><span>AK</span><span>ML</span><span>JS</span></div><span><b>1,200+ builders</b> shipping with Linkify</span></div></div>
        <div className="product-stage" role="img" aria-label="Linkify media search product preview"><div className="glow-orb orb-a" /><div className="glow-orb orb-b" /><div className="console-card"><div className="window-bar"><span className="window-dots"><i /><i /><i /></span><span className="live-pill">● live request</span></div><div className="search-mock"><Search size={17} /> Search “Dune: Part Two”<b>⌘ K</b></div><div className="media-result"><div className="poster-art" /><div className="result-copy"><small>Movie · 2024</small><h3>Dune: Part Two</h3><small>8.5 score · 2h 46m</small><div className="tag-row"><span className="tag">Science Fiction</span><span className="tag">Adventure</span><span className="tag">Drama</span></div></div></div></div><div className="metric-float"><b>99.99%</b><span>API uptime this month</span></div></div>
      </div></section>
      <div className="logo-strip"><div className="logo-track">{brands.map((brand, index) => <span key={`${brand}-${index}`}>{brand}</span>)}</div></div>
      <section className="section" id="features"><div className="container"><div className="section-heading"><span className="eyebrow">Everything connected</span><h2 className="display">One API. Every screen your product needs.</h2><p>Stop stitching together fragile media sources. Start with a clean contract designed for production.</p></div><div className="bento">
        <article className="feature-card large"><span className="feature-icon"><Braces /></span><h3>Predictable by design</h3><p>Versioned endpoints, scoped keys and consistently shaped responses make every integration feel obvious.</p><div className="code-stack"><div className="code-row">GET /api/v1/search/results?q=Dune</div><div className="code-row" style={{ transform: "translateX(18px)" }}>200 · 86ms · cached</div><div className="code-row" style={{ transform: "translateX(7px)" }}>{`{ results: [...], page: 1 }`}</div></div></article>
        <article className="feature-card sun"><span className="feature-icon"><Zap /></span><h3>Fast by default</h3><p>Smart caching and bounded provider timeouts keep your product responsive.</p></article>
        <article className="feature-card cyan"><span className="feature-icon"><Globe2 /></span><h3>Global discovery</h3><p>Movies, series, cast, recommendations and regional watch providers.</p></article>
        <article className="feature-card"><span className="feature-icon"><BarChart3 /></span><h3>Usage you can see</h3><p>Status, latency and daily activity stay visible from the console.</p><div className="chart-art">{[42,75,54,90,64,82,100].map((h,i)=><i key={i} style={{ height: `${h}%` }}/>)}</div></article>
        <article className="feature-card" id="security"><span className="feature-icon"><ShieldCheck /></span><h3>Security built in</h3><p>Hashed secrets, scopes, expiry, rotation and one-time key reveal.</p></article>
      </div></div></section>
      <section className="section" style={{ paddingTop: 10 }}><div className="container cta-panel"><div><h2 className="display">Go from idea to first request.</h2><p>No card required. Create an account and ship your integration today.</p></div><Link href="/signup" className="btn" style={{ background: "var(--sun)", color: "var(--ink)", position: "relative", zIndex: 2 }}>Start building free <Sparkles size={17} /></Link></div></section>
    </main><SiteFooter /></>
  );
}
