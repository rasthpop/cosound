import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { NoConfidentMatch } from "./NoConfidentMatch";
import { OfflineState } from "./OfflineState";
import { StatusPill } from "./StatusPill";

afterEach(cleanup);

describe("StatusPill", () => {
  it("renders nothing when nothing is degraded", () => {
    const { container } = render(<StatusPill capabilities={{ semantic: "available", map: "available" }} />);
    expect(container).toBeEmptyDOMElement();
    expect(render(<StatusPill capabilities={null} />).container).toBeEmptyDOMElement();
  });

  it("names each degraded capability in text", () => {
    render(<StatusPill capabilities={{ semantic: "unavailable", map: "unavailable" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Sound-based matching is off — catalog data only");
    expect(screen.getByRole("status")).toHaveTextContent("Map unavailable");
  });

  it("offers retry when offline", async () => {
    const onRetry = vi.fn();
    render(<StatusPill capabilities={null} offline onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("state views", () => {
  it("no confident match lists the reasons as given and offers an edit, never a silent relax", async () => {
    const onEditQuery = vi.fn();
    render(<NoConfidentMatch reasons={["no track has reliable evidence for: vocals excluded"]} onEditQuery={onEditQuery} />);
    expect(screen.getByText("no track has reliable evidence for: vocals excluded")).toBeInTheDocument();
    expect(screen.queryByText(/relax/i)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Edit your search" }));
    expect(onEditQuery).toHaveBeenCalledOnce();
  });

  it("error copy comes from the code, never the raw code or a stack", () => {
    render(<ErrorState error={{ code: "internal_error" }} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong on the server. Retry.");
    expect(alert).not.toHaveTextContent("internal_error");
  });

  it("offline keeps the typed query, empty suggests broadening", () => {
    render(<OfflineState query="chill flute" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Your search “chill flute” is kept.");
    render(<EmptyState query="zzz" />);
    expect(screen.getByRole("status")).toHaveTextContent("Try fewer or broader words");
  });
});
