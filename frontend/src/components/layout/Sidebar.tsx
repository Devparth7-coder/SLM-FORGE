"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard,
  Database,
  ShieldCheck,
  Cpu,
  FlaskConical,
  Activity,
  BarChart3,
  ShieldAlert,
  Bug,
  GitCompare,
  FileText,
  Settings,
  Beaker,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/datasets", label: "Datasets", icon: Database },
  { href: "/data-quality", label: "Data Quality", icon: ShieldCheck },
  { href: "/models", label: "Models", icon: Cpu },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/training", label: "Training", icon: Activity },
  { href: "/evaluation", label: "Evaluation", icon: BarChart3 },
  { href: "/robustness", label: "Robustness", icon: ShieldAlert },
  { href: "/failures", label: "Failures", icon: Bug },
  { href: "/comparison", label: "Comparison", icon: GitCompare },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-border bg-bg-elevated flex flex-col">
      <div className="px-4 py-4 border-b border-border-subtle">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-accent/15 border border-accent/30 flex items-center justify-center">
            <Beaker className="w-4 h-4 text-accent" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">SLM-FORGE</div>
            <div className="text-[10px] text-fg-subtle uppercase tracking-widest">
              Research Lab
            </div>
          </div>
        </Link>
      </div>
      <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx("nav-item", active && "nav-item-active")}
            >
              <Icon className="w-4 h-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border-subtle">
        <div className="text-[10px] text-fg-subtle leading-relaxed">
          <div className="font-semibold text-fg-muted mb-1">
            Train less. Measure more.
          </div>
          <div>© 2025 Dev Parth</div>
        </div>
      </div>
    </aside>
  );
}
