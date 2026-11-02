// shadcn Sheet (Radix Dialog) as a glass side panel. The details drawer (ui.md §4.4) is a
// right-hand 400 px non-modal sheet on desktop (`<Sheet modal={false}>`, `overlay={false}`) and a
// full-height modal sheet below 1024 px. Radix keeps Tab inside and closes on Esc.
import { XIcon } from "lucide-react";
import { Dialog as SheetPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { ICON } from "@/theme/tokens/semantic";

import { cn } from "./cn";

function Sheet(props: ComponentProps<typeof SheetPrimitive.Root>) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />;
}

function SheetTrigger(props: ComponentProps<typeof SheetPrimitive.Trigger>) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />;
}

function SheetClose(props: ComponentProps<typeof SheetPrimitive.Close>) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />;
}

const SIDE = {
  right: "inset-y-0 right-0 h-full w-full border-l lg:w-50",
  left: "inset-y-0 left-0 h-full w-full border-r lg:w-47.5",
  top: "inset-x-0 top-0 h-auto border-b",
  bottom: "inset-x-0 bottom-0 h-auto border-t",
} as const;

function SheetContent({
  className,
  children,
  side = "right",
  overlay = true,
  closeLabel = "Close",
  ...props
}: ComponentProps<typeof SheetPrimitive.Content> & {
  side?: keyof typeof SIDE;
  /** Dim the page behind the sheet; false for the non-modal desktop drawer. */
  overlay?: boolean;
  closeLabel?: string;
}) {
  return (
    <SheetPrimitive.Portal>
      {overlay && <SheetPrimitive.Overlay data-slot="sheet-overlay" className="fixed inset-0 z-40 bg-surface-canvas opacity-60" />}
      <SheetPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          "fixed z-50 flex flex-col gap-2 border-hairline bg-surface-panel p-2 text-fg outline-none backdrop-blur-panel",
          SIDE[side],
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close
          className="absolute top-1.5 right-1.5 inline-flex size-4 cursor-pointer items-center justify-center rounded-sm text-muted hover:bg-surface-raised hover:text-fg"
        >
          <XIcon aria-hidden="true" {...ICON} />
          <span className="sr-only">{closeLabel}</span>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}

function SheetHeader({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="sheet-header" className={cn("flex flex-col gap-0.5 pr-4", className)} {...props} />;
}

function SheetFooter({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="sheet-footer" className={cn("mt-auto flex flex-col gap-1", className)} {...props} />;
}

function SheetTitle({ className, ...props }: ComponentProps<typeof SheetPrimitive.Title>) {
  return <SheetPrimitive.Title data-slot="sheet-title" className={cn("text-heading font-medium", className)} {...props} />;
}

function SheetDescription({ className, ...props }: ComponentProps<typeof SheetPrimitive.Description>) {
  return <SheetPrimitive.Description data-slot="sheet-description" className={cn("text-meta text-muted", className)} {...props} />;
}

export { Sheet, SheetTrigger, SheetClose, SheetContent, SheetHeader, SheetFooter, SheetTitle, SheetDescription };
