"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { backend, errorMessage } from "@/lib/api";

export default function VerifyEmailPage(){const{key}=useParams<{key:string}>();const router=useRouter();const[error,setError]=useState("");useEffect(()=>{backend("_allauth/browser/v1/auth/email/verify",{method:"POST",body:JSON.stringify({key})}).then(()=>setTimeout(()=>router.replace("/dashboard"),900)).catch(reason=>setError(errorMessage(reason)))},[key,router]);return <AuthShell title="Trust begins with a verified identity."><div className="auth-card"><h1 className="display">Verifying your email…</h1>{error?<div className="form-alert error">{error}</div>:<div className="form-alert success">Securely confirming this address. You’ll be redirected automatically.</div>}</div></AuthShell>}
