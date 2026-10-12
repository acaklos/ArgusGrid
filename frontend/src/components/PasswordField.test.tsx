import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionProvider } from "../state/session";
import { PasswordField } from "./PasswordField";

const summary = {
  min_length: 12, max_length: 128, require_upper: true, require_lower: true, require_digit: true,
  require_special: true, reject_username: true, reject_common: true, history_count: 5, min_age_hours: 48,
  reveal_autohide_seconds: 5,
};

let counter = 0;

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    endpoints: {
      ...actual.endpoints,
      session: vi.fn(async () => ({
        authenticated: true, user: { username: "alice", full_name: "", role: "SOC Analyst", email: "" },
        csrf_token: "t", must_change_password: false, capabilities: [], dev_loginless: false, dev_banner: "", profile: { name: "civil", marking: "" }, password_expires_at: null,
      })),
      passwordSummary: vi.fn(async () => summary),
      generatePassword: vi.fn(async () => ({ password: `Gen-Pass-${++counter}!aB9xyz` })),
    },
  };
});

function NewHarness({ defaultMode = "generated" as "generated" | "custom" }) {
  const [value, setValue] = useState("");
  const [valid, setValid] = useState(false);
  return (
    <SessionProvider>
      <PasswordField variant="new" label="Password" value={value} onChange={setValue} defaultMode={defaultMode}
        username="alice" onValidChange={setValid} />
      <output data-testid="valid">{String(valid)}</output>
      <output data-testid="value">{value}</output>
    </SessionProvider>
  );
}

const passwordInputs = () => Array.from(document.querySelectorAll<HTMLInputElement>("input[type='password'], input.input"))
  .filter((el) => el.getAttribute("type") === "password" || el.getAttribute("type") === "text");

beforeEach(() => {
  counter = 0;
});

describe("PasswordField", () => {
  it("generated mode shows exactly one field holding a generated password (PWD-030)", async () => {
    render(<NewHarness />);
    await waitFor(() => expect(screen.getByTestId("value").textContent).toMatch(/^Gen-Pass-1/));
    expect(passwordInputs()).toHaveLength(1);
    expect(screen.getByLabelText("Password")).toHaveAttribute("readonly");
    await waitFor(() => expect(screen.getByTestId("valid").textContent).toBe("true"));
  });

  it("custom mode shows two fields and blocks until they match (PWD-031)", async () => {
    const user = userEvent.setup();
    render(<NewHarness />);
    await waitFor(() => expect(screen.getByTestId("value").textContent).not.toBe(""));
    await user.click(screen.getByLabelText("Custom password"));
    expect(passwordInputs()).toHaveLength(2);
    await user.type(screen.getAllByLabelText(/password/i)[0], "Abcdefgh1!xyz");
    expect(screen.getByTestId("valid").textContent).toBe("false"); // confirm is still empty
    await user.type(screen.getByLabelText("Confirm password"), "Abcdefgh1!xyz");
    await waitFor(() => expect(screen.getByTestId("valid").textContent).toBe("true"));
  });

  it("switching from custom to generated generates immediately (PWD-032)", async () => {
    const user = userEvent.setup();
    render(<NewHarness defaultMode="custom" />);
    await user.click(screen.getByLabelText("Custom password")); // uncheck: back to generated
    await waitFor(() => expect(screen.getByTestId("value").textContent).toMatch(/^Gen-Pass-1/));
    expect(passwordInputs()).toHaveLength(1);
  });

  it("the reveal control has no focus, an accessible name and a state (PWD-034)", async () => {
    const user = userEvent.setup();
    render(<NewHarness />);
    await waitFor(() => expect(screen.getByTestId("value").textContent).not.toBe(""));
    const reveal = screen.getByRole("button", { name: "Show password" });
    expect(reveal).toHaveAttribute("tabindex", "-1");
    expect(reveal).toHaveAttribute("aria-pressed", "false");
    await user.click(reveal);
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
  });

  it("the password hides again after the configured seconds (PWD-035)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<NewHarness />);
      await waitFor(() => expect(screen.getByTestId("value").textContent).not.toBe(""));
      const reveal = screen.getByRole("button", { name: "Show password" });
      await act(async () => reveal.click());
      expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
      await act(async () => {
        vi.advanceTimersByTime(5100);
      });
      expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows the active rules from the policy as a live checklist (PWD-037)", async () => {
    const user = userEvent.setup();
    render(<NewHarness defaultMode="custom" />);
    await waitFor(() => expect(screen.getByText("At least 12 characters")).toBeInTheDocument());
    expect(screen.getByText("An uppercase letter")).toBeInTheDocument();
    await user.type(screen.getAllByLabelText(/password/i)[0], "alice-Aa1!");
    const item = screen.getByText("Does not contain the user name").closest("li");
    expect(item).toHaveAttribute("data-ok", "false");
  });

  it("uses the correct autocomplete values (PWD-036)", async () => {
    render(
      <SessionProvider>
        <PasswordField variant="current" label="Current" value="" onChange={() => undefined} />
      </SessionProvider>,
    );
    expect(screen.getByLabelText("Current")).toHaveAttribute("autocomplete", "current-password");
  });
});
