"use client";

import { useEffect, useState } from "react";
import { backend, csrfToken, errorMessage } from "@/lib/api";

type Config = { data?: { socialaccount?: { providers?: Array<{ id: string; name: string }> } } };

export function SocialButtons({ onError }: { onError: (message: string) => void }) {
  const [providers, setProviders] = useState<Array<{ id: string; name: string }>>([]);
  const [busy, setBusy] = useState<string>();

  useEffect(() => {
    backend<Config>("_allauth/browser/v1/config")
      .then((value) => setProviders(value.data?.socialaccount?.providers ?? []))
      .catch(() => setProviders([]));
  }, []);

  if (!providers.length) return null;

  async function connect(provider: string) {
    setBusy(provider);
    onError("");
    try {
      const body = new URLSearchParams({
        provider,
        process: "login",
        callback_url: `${window.location.origin}/dashboard`,
      });
      const response = await fetch("/api/backend/_allauth/browser/v1/auth/provider/redirect?_redirect=manual", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrfToken() },
        body,
      });
      const payload = await response.json();
      if (!response.ok || !payload.redirect) throw new Error("Social sign-in could not be started.");
      window.location.assign(payload.redirect);
    } catch (error) {
      onError(errorMessage(error));
      setBusy(undefined);
    }
  }

  return (
    <>
      <div className="divider">or continue with</div>
      <div className="social-grid">
        {providers.map((provider) => (
          <button className="social-btn" type="button" disabled={Boolean(busy)} onClick={() => connect(provider.id)} key={provider.id}>
            {busy === provider.id ? "Connecting…" : provider.name}
          </button>
        ))}
      </div>
    </>
  );
}
