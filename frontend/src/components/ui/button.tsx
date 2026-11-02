// shadcn Button, restyled with semantic token utilities (ADR-0003). Spacing is the 8 px grid:
// h-4 = 32 px, h-5 = 40 px. The accent is reserved for the primary action (ui.md §2).
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "./cn";

const buttonVariants = cva(
  "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1 rounded-md font-medium whitespace-nowrap transition-colors duration-(--token-motion-duration-fast) ease-out disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-accent text-on-accent hover:bg-accent-hover",
        secondary: "border border-hairline bg-surface-raised text-fg hover:border-border-strong",
        ghost: "text-fg hover:bg-surface-raised",
        quiet: "text-muted hover:bg-surface-raised hover:text-fg",
        link: "text-fg underline underline-offset-4 decoration-border-strong hover:decoration-accent",
      },
      size: {
        sm: "h-4 px-1 text-meta",
        md: "h-5 px-2 text-body",
        icon: "size-5",
        "icon-sm": "size-4",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  type,
  ...props
}: ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      data-slot="button"
      // a plain <button> defaults to "button", never an accidental form submit
      type={asChild ? type : (type ?? "button")}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}

export { Button, buttonVariants };
