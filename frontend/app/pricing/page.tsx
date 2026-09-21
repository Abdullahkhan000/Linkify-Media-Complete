import Link from "next/link";
import { Check } from "lucide-react";
import { MarketingNav } from "@/components/marketing-nav";
import { SiteFooter } from "@/components/site-footer";

const plans = [
  { name: "Free", price: "$0", color: "#dff9fc", features: ["1 API key", "1,000 requests/day", "Search & usage endpoints"] },
  { name: "Pro", price: "$29", color: "#ede9ff", featured: true, features: ["5 scoped API keys", "25,000 requests/day", "Batch, analytics & exports"] },
  { name: "Business", price: "$99", color: "#fff3cd", features: ["100 API keys", "Unlimited daily usage", "Priority support"] },
];

export default function PricingPage() {
  return <><MarketingNav/><main className="section"><div className="container"><div className="section-heading" style={{marginInline:"auto",textAlign:"center"}}><span className="eyebrow">Simple pricing</span><h1 className="display" style={{fontSize:"clamp(48px,6vw,76px)",margin:"20px 0"}}>Start small. Scale without surprises.</h1><p>Every plan includes secure credentials, versioned endpoints and the complete media schema.</p></div><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))",gap:18}}>{plans.map(plan=><article key={plan.name} className="feature-card" style={{background:plan.color,minHeight:430,border:plan.featured?"2px solid var(--purple)":undefined}}>{plan.featured&&<span className="eyebrow">Most popular</span>}<h2 className="display" style={{fontSize:30,marginTop:24}}>{plan.name}</h2><div className="display" style={{fontSize:52,fontWeight:800,margin:"15px 0"}}>{plan.price}<small style={{fontSize:14,color:"var(--muted)"}}>/month</small></div><div style={{display:"grid",gap:13,margin:"28px 0"}}>{plan.features.map(item=><span key={item} style={{display:"flex",gap:9,alignItems:"center"}}><Check size={17} color="var(--purple)"/>{item}</span>)}</div><Link className={`btn ${plan.featured?"btn-primary":"btn-secondary"} btn-full`} href="/signup">Choose {plan.name}</Link></article>)}</div></div></main><SiteFooter/></>;
}
