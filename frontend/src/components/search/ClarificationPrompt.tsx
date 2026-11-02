// `outcome: "needs_clarification"`: the system's question, inline under the bar, and a reply field.
import { MessageCircleQuestion } from "lucide-react";
import { useId, useState } from "react";

import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";
import { Input } from "../ui/input";

export interface ClarificationPromptProps {
  /** `SearchResponse.clarification_question`, as given. */
  question: string;
  onReply: (text: string) => void;
}

export function ClarificationPrompt({ question, onReply }: ClarificationPromptProps) {
  const [reply, setReply] = useState("");
  const id = useId();
  return (
    <form
      aria-labelledby={id}
      onSubmit={(e) => {
        e.preventDefault();
        const text = reply.trim();
        if (text) onReply(text);
      }}
      className="flex flex-col gap-1 rounded-lg border border-hairline bg-surface-panel p-1.5 backdrop-blur-panel"
    >
      <p id={id} className="flex items-center gap-1 text-body">
        <MessageCircleQuestion aria-hidden="true" className="shrink-0 text-accent" {...ICON} />
        {question}
      </p>
      <div className="flex gap-1">
        <Input aria-labelledby={id} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Your answer" />
        <Button type="submit" variant="primary" disabled={!reply.trim()}>
          Reply
        </Button>
      </div>
    </form>
  );
}
