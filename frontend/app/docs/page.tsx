import { Braces, KeyRound, Search, ShieldCheck } from "lucide-react";
import { MarketingNav } from "@/components/marketing-nav";
import { SiteFooter } from "@/components/site-footer";

const requestExample = [
  'curl "https://api.example.com/api/v1/search/results/?q=Inception&type=movie" \\',
  '  -H "X-API-Key: lm_live_your_secret"',
].join("\n");

const responseExample = JSON.stringify({ page: 1, results: [{ title: "Inception", year: 2010, rating: 8.4 }] }, null, 2);

const concepts = [
  { Icon: KeyRound, title: "Authenticate", copy: "Send X-API-Key on every request." },
  { Icon: Search, title: "Discover", copy: "Search titles, people and trending media." },
  { Icon: Braces, title: "Integrate", copy: "Use Python, JavaScript or Postman starters." },
  { Icon: ShieldCheck, title: "Protect", copy: "Rotate, scope and expire keys from your console." },
];

export default function DocsPage() {
  return <><MarketingNav/><main className="section"><div className="container"><div className="section-heading"><span className="eyebrow">Developer quickstart</span><h1 className="display" style={{fontSize:"clamp(48px,6vw,76px)"}}>Your first result in under a minute.</h1><p>Use the versioned REST API from any server-side runtime. Never expose your secret in browser code.</p></div><div className="dashboard-grid"><div className="panel" style={{padding:30}}><div className="panel-head"><h2 className="display">Search media</h2><span className="scope">GET</span></div><pre style={{overflow:"auto",padding:22,borderRadius:16,background:"#292653",color:"#f3f1ff",lineHeight:1.8}}>{requestExample}</pre><h3>Response</h3><pre style={{overflow:"auto",padding:22,borderRadius:16,background:"#f4f2ff",color:"var(--ink)",lineHeight:1.7}}>{responseExample}</pre></div><aside style={{display:"grid",gap:14}}>{concepts.map(({Icon,title,copy})=><div className="panel" key={title}><span className="feature-icon"><Icon/></span><h3>{title}</h3><p style={{color:"var(--muted)",lineHeight:1.6}}>{copy}</p></div>)}</aside></div><p style={{marginTop:25,color:"var(--muted)"}}>Full OpenAPI and Swagger remain available from the Django backend at <code>/api/docs/</code>.</p></div></main><SiteFooter/></>;
}
