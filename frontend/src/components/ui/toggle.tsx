// shadcn Toggle (Radix). The "on" state uses the subtle accent plus `aria-pressed`, never colour alone.
import { cva, type VariantProps } from "class-variance-authority";
import { Toggle as TogglePrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "./cn";

const toggleVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-0.5 rounded-md font-medium whitespace-nowrap text-muted transition-colors duration-(--token-motion-duration-fast) hover:bg-surface-raised hover:text-fg disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-accent-subtle data-[state=on]:text-fg [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        plain: "",
        outline: "border border-hairline data-[state=on]:border-accent",
      },
      size: {
        sm: "h-4 px-1 text-meta",
        md: "h-5 px-1.5 text-body",
      },
    },
    defaultVariants: { variant: "outline", size: "sm" },
  },
);

function Toggle({ className, variant, size, ...props }: ComponentProps<typeof TogglePrimitive.Root> & VariantProps<typeof toggleVariants>) {
  return <TogglePrimitive.Root data-slot="toggle" className={cn(toggleVariants({ variant, size }), className)} {...props} />;
}

export { Toggle, toggleVariants };
