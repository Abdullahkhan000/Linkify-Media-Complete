"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { BookOpen, CreditCard, KeyRound, LayoutDashboard, LogOut, Menu, Settings, Sparkles, X } from "lucide-react";
import { Logo } from "./logo";
import { AuthUser, backend } from "@/lib/api";

const items = [
  { href: "/dashboard", label: "Overview", Icon: LayoutDashboard },
  { href: "/dashboard#keys", label: "API keys", Icon: KeyRound },
  { href: "/docs", label: "Documentation", Icon: BookOpen },
  { href: "/pricing", label: "Plans", Icon: CreditCard },
  { href: "/account", label: "Account", Icon: Settings },
];

export function DashboardShell({ user, title, children }: { user: AuthUser; title: string; children: React.ReactNode }) {
  const pathname=usePathname(); const router=useRouter(); const[mobileNav,setMobileNav]=useState(false);
  async function logout(){await backend("_allauth/browser/v1/auth/session",{method:"DELETE"}).catch(()=>undefined);router.replace("/login");router.refresh()}
  const links=items.map(({href,label,Icon})=><Link href={href} onClick={()=>setMobileNav(false)} key={label} className={`sidebar-link ${pathname===href?"active":""}`}><Icon size={18}/><span>{label}</span></Link>);
  return <main className="app-layout"><aside className="sidebar"><Logo/><nav className="sidebar-nav">{links}</nav><div className="sidebar-plan"><Sparkles size={20}/><small>Current plan</small><b>Free developer</b><Link href="/pricing" className="btn" style={{minHeight:35,padding:"0 11px",fontSize:12,background:"var(--sun)",color:"var(--ink)"}}>View upgrades</Link></div></aside>{mobileNav&&<div className="mobile-drawer-backdrop"><aside className="mobile-drawer"><div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}><Logo/><button className="btn icon-btn" style={{color:"white",background:"rgba(255,255,255,.12)"}} aria-label="Close navigation" onClick={()=>setMobileNav(false)}><X size={18}/></button></div><nav className="sidebar-nav">{links}</nav></aside></div>}<section className="app-main"><header className="topbar"><div style={{display:"flex",alignItems:"center",gap:12}}><button className="btn btn-secondary icon-btn mobile-menu" aria-label="Open navigation" aria-expanded={mobileNav} onClick={()=>setMobileNav(true)}><Menu size={19}/></button><h1 className="display">{title}</h1></div><div className="user-chip"><div className="user-avatar">{user.username.slice(0,2).toUpperCase()}</div><div><b style={{fontSize:13}}>{user.username}</b><small style={{display:"block",color:"var(--muted)"}}>{user.email}</small></div><button className="btn btn-secondary icon-btn" onClick={logout} title="Sign out"><LogOut size={17}/></button></div></header><div className="app-content">{children}</div></section></main>
}
