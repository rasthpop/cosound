// shadcn Input on tokens: raised surface, hairline border, accent border on focus.
import type { ComponentProps } from "react";

import { cn } from "./cn";

function Input({ className, type, ...props }: ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-5 w-full min-w-0 rounded-md border border-hairline bg-surface-raised px-1.5 text-body text-fg transition-colors duration-(--token-motion-duration-fast) outline-none placeholder:text-muted focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-state-error",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
