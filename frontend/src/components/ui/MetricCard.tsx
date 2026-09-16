import { ReactNode } from "react";
import clsx from "clsx";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  sublabel?: ReactNode;
  accent?: "default" | "success" | "danger" | "warning" | "info";
  className?: string;
}

const accentColors: Record<string, string> = {
  default: "text-fg",
  success: "text-accent-success",
  danger: "text-accent-danger",
  warning: "text-accent-warning",
  info: "text-accent-info",
};

export function MetricCard({
  label,
  value,
  sublabel,
  accent = "default",
  className,
}: MetricCardProps) {
  return (
    <div className={clsx("card p-4", className)}>
      <div className="metric-label">{label}</div>
      <div className={clsx("metric-value mt-1", accentColors[accent])}>
        {value ?? <span className="text-fg-subtle">—</span>}
      </div>
      {sublabel && <div className="text-xs text-fg-subtle mt-1">{sublabel}</div>}
    </div>
  );
}
