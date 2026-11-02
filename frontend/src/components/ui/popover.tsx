// shadcn Popover (Radix) as a floating glass panel.
import { Popover as PopoverPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "./cn";

function Popover(props: ComponentProps<typeof PopoverPrimitive.Root>) {
  return <PopoverPrimitive.Root data-slot="popover" {...props} />;
}

function PopoverTrigger(props: ComponentProps<typeof PopoverPrimitive.Trigger>) {
  return <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props} />;
}

function PopoverAnchor(props: ComponentProps<typeof PopoverPrimitive.Anchor>) {
  return <PopoverPrimitive.Anchor data-slot="popover-anchor" {...props} />;
}

/** Popover content is a dialog, so it must be named: pass `aria-label` or `aria-labelledby`. */
type Named = { "aria-label": string } | { "aria-labelledby": string };

function PopoverContent({
  className,
  align = "center",
  sideOffset = 6,
  ...props
}: ComponentProps<typeof PopoverPrimitive.Content> & Named) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        data-slot="popover-content"
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 flex w-32 flex-col gap-1 rounded-lg border border-hairline bg-surface-panel p-1.5 text-fg outline-none backdrop-blur-panel",
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}

function PopoverHeader({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="popover-header" className={cn("flex flex-col gap-0.5", className)} {...props} />;
}

function PopoverTitle({ className, ...props }: ComponentProps<"h2">) {
  return <h2 data-slot="popover-title" className={cn("text-body font-medium", className)} {...props} />;
}

function PopoverDescription({ className, ...props }: ComponentProps<"p">) {
  return <p data-slot="popover-description" className={cn("text-meta text-muted", className)} {...props} />;
}

export { Popover, PopoverTrigger, PopoverContent, PopoverAnchor, PopoverHeader, PopoverTitle, PopoverDescription };
