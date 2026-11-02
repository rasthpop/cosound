// Shared layout for the state views: an icon, a heading, body text and actions.
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { ICON } from "@/theme/tokens/semantic";

export function StateMessage({
  icon: Icon,
  title,
  children,
  actions,
  tone = "muted",
  role,
}: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  tone?: "muted" | "error" | "warning";
  role?: "alert" | "status";
}) {
  const iconTone = { muted: "text-state-empty", error: "text-state-error", warning: "text-state-warning" }[tone];
  return (
    <section role={role} aria-label={title} className="flex flex-col items-start gap-1 p-2">
      <Icon aria-hidden="true" className={iconTone} {...ICON} />
      <h2 className="text-body font-medium">{title}</h2>
      {children && <div className="flex flex-col gap-0.5 text-meta text-muted">{children}</div>}
      {actions && <div className="mt-0.5 flex flex-wrap gap-1">{actions}</div>}
    </section>
  );
}
