// `outcome: "no_confident_match"`: the system's reasons, as given, and the user's choice to edit
// the search. Relaxing a constraint is never done for the user (D1).
import { CircleHelp } from "lucide-react";

import { Button } from "../ui/button";
import { StateMessage } from "./StateMessage";

export interface NoConfidentMatchProps {
  /** `SearchResponse.no_match_reasons`, shown as provided. */
  reasons: readonly string[];
  onEditQuery?: () => void;
}

export function NoConfidentMatch({ reasons, onEditQuery }: NoConfidentMatchProps) {
  return (
    <StateMessage
      icon={CircleHelp}
      tone="warning"
      role="status"
      title="No confident match"
      actions={
        onEditQuery && (
          <Button size="sm" onClick={onEditQuery}>
            Edit your search
          </Button>
        )
      }
    >
      <p>No track meets everything you asked for with enough evidence.</p>
      {reasons.length > 0 && (
        <ul className="list-disc pl-2">
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      <p>You can change or drop a requirement and search again.</p>
    </StateMessage>
  );
}
