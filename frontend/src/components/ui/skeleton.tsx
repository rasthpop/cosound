// shadcn Skeleton: a loading placeholder that keeps the layout from jumping. Its pulse is a
// motion token, so it stops under prefers-reduced-motion.
import type { ComponentProps } from "react";

import { cn } from "./cn";

function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="skeleton" aria-hidden="true" className={cn("animate-skeleton rounded-md bg-surface-raised", className)} {...props} />;
}

export { Skeleton };
