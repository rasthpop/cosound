// One interpreted-query chip (ui.md §4.1). Three kinds look different:
// - soft: a preference; a menu offers "More of this" / "Less of this" (D1, no ✕);
// - hard: an explicit requirement; solid outline + lock, read-only;
// - negative: something to avoid; "not" prefix + strikethrough, read-only.
import { Lock } from "lucide-react";
import { useId } from "react";

import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";
import { cn } from "../ui/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

export type ChipKind = "soft" | "hard" | "negative";

interface BaseProps {
  label: string;
}

export type QueryChipProps =
  | (BaseProps & { kind: "soft"; onMore: () => void; onLess: () => void; moreLabel?: string; lessLabel?: string })
  | (BaseProps & { kind: "hard" })
  | (BaseProps & { kind: "negative" });

const CHIP = "inline-flex h-3 items-center gap-0.5 rounded-pill border px-1 text-meta";

export function QueryChip(props: QueryChipProps) {
  const menuId = useId();
  if (props.kind === "hard") {
    return (
      <span className={cn(CHIP, "border-border-strong font-medium text-fg")}>
        <Lock aria-hidden="true" {...ICON} />
        <span>{props.label}</span>
        <span className="sr-only">(requirement)</span>
      </span>
    );
  }
  if (props.kind === "negative") {
    return (
      <span className={cn(CHIP, "border-dashed border-hairline text-muted")}>
        <span>not</span>
        <span className="line-through">{props.label}</span>
      </span>
    );
  }
  const { label, onMore, onLess, moreLabel = "More of this", lessLabel = "Less of this" } = props;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`${label}: adjust`}
          className={cn(CHIP, "cursor-pointer border-hairline bg-surface-raised text-fg hover:border-border-strong")}
        >
          {label}
        </button>
      </PopoverTrigger>
      <PopoverContent aria-labelledby={menuId} align="start" className="w-24">
        <p id={menuId} className="px-0.5 text-meta text-muted">
          {label}
        </p>
        <Button size="sm" variant="ghost" className="justify-start" onClick={onMore}>
          {moreLabel}
        </Button>
        <Button size="sm" variant="ghost" className="justify-start" onClick={onLess}>
          {lessLabel}
        </Button>
      </PopoverContent>
    </Popover>
  );
}
