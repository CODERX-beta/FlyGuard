import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskBadge } from "../src/components/RiskBadge";

describe("FlyGuard AI Frontend Components", () => {
  it("renders accessible RiskBadge with category text and numerical score", () => {
    render(<RiskBadge category="Critical" score={91.4} size="md" />);
    expect(screen.getByText("Critical")).toBeDefined();
    expect(screen.getByText("(91)")).toBeDefined();
  });

  it("renders Low RiskBadge accurately", () => {
    render(<RiskBadge category="Low" score={12.0} />);
    expect(screen.getByText("Low")).toBeDefined();
    expect(screen.getByText("(12)")).toBeDefined();
  });
});

