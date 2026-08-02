import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "@/components/common/PageHeader";

describe("PageHeader", () => {
  it("renders the title", () => {
    render(<PageHeader title="Employees" />);
    expect(screen.getByRole("heading", { name: "Employees" })).toBeInTheDocument();
  });

  it("renders the description when provided", () => {
    render(<PageHeader title="Employees" description="Manage your workforce" />);
    expect(screen.getByText("Manage your workforce")).toBeInTheDocument();
  });

  it("omits the description when not provided", () => {
    render(<PageHeader title="Employees" />);
    expect(screen.queryByText("Manage your workforce")).not.toBeInTheDocument();
  });

  it("renders provided actions", () => {
    render(<PageHeader title="Employees" actions={<button type="button">Add employee</button>} />);
    expect(screen.getByRole("button", { name: "Add employee" })).toBeInTheDocument();
  });
});
