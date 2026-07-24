import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CitationDrawer } from "./CitationDrawer";

describe("CitationDrawer", () => {
  it("shows citation details and returns focus when closed", async () => {
    const user = userEvent.setup();
    render(<CitationDrawer label="Lihat sumber jawaban" citations={[{
      id: "citation-1",
      sourceType: "document_chunk",
      sourceId: "source-1",
      documentId: "policy.pdf",
      locator: { page: 4 },
      quote: "Kutipan kebijakan yang mendukung jawaban.",
      label: "Dokumen kebijakan",
    }]} />);

    const trigger = screen.getByRole("button", { name: "Lihat sumber jawaban (1)" });
    await user.click(trigger);

    expect(screen.getByRole("dialog", { name: "Sumber kutipan" })).toBeInTheDocument();
    expect(screen.getByText(/Kutipan kebijakan yang mendukung jawaban/)).toBeInTheDocument();
    expect(screen.getByText("page: 4")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("renders nothing without citations", () => {
    const { container } = render(<CitationDrawer citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
