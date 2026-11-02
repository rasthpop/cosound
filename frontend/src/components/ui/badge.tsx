// shadcn Badge on tokens. Badges carry text; colour is never the only signal (ui.md §7).
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "./cn";

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-0.5 rounded-pill border px-1 text-meta whitespace-nowrap [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        muted: "border-hairline text-muted",
        outline: "border-border-strong text-fg",
        accent: "border-accent text-fg",
      },
    },
    defaultVariants: { variant: "muted" },
  },
);

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span";
  return <Comp data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
