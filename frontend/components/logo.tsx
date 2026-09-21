import Link from "next/link";
import { Layers3 } from "lucide-react";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="brand" aria-label="Linkify Media home">
      <span className="brand-mark"><Layers3 size={20} strokeWidth={2.5} /></span>
      {!compact && <span>Linkify Media</span>}
    </Link>
  );
}
