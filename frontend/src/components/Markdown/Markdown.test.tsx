import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders GFM content and does not render raw HTML", () => {
    const { container } = render(
      <Markdown>{"## Temuan\n\n- **Penting**\n\n| Risiko | Nilai |\n| --- | --- |\n| Narasi | Tinggi |\n\n<script>alert('x')</script>"}</Markdown>,
    );

    expect(screen.getByRole("heading", { name: "Temuan" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("Narasi");
    expect(container.querySelector("script")).toBeNull();
    expect(container).not.toHaveTextContent("alert('x')");
  });
});
