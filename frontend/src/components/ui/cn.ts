// Class-name helper for shadcn components (components.json "utils" alias). tailwind-merge is
// told about the token scales from theme/generated/tokens.css, so `text-body` (size) and
// `text-muted` (colour) are kept together while two sizes still override each other.
import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

const merge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["meta", "body", "heading", "display"],
      "font-weight": ["regular", "medium"],
      radius: ["sm", "md", "lg", "pill"],
      blur: ["panel"],
      ease: ["out", "linear"],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return merge(clsx(inputs));
}
