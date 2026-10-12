import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SessionProvider } from "../state/session";
import { ProfileBanner } from "./ProfileBanner";

const profile = { current: { name: "defense", marking: "RESTRICTED" } };

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    endpoints: {
      ...actual.endpoints,
      session: vi.fn(async () => ({
        authenticated: false, user: null, csrf_token: null, must_change_password: false, capabilities: [],
        dev_loginless: false, dev_banner: "", profile: profile.current, password_expires_at: null,
      })),
    },
  };
});

describe("ProfileBanner (ARG-021)", () => {
  it("shows the marking of the deployment profile, also before sign-in", async () => {
    profile.current = { name: "defense", marking: "RESTRICTED" };
    render(<SessionProvider><ProfileBanner position="top" /></SessionProvider>);
    await waitFor(() => expect(screen.getByTestId("marking-top")).toHaveTextContent("RESTRICTED"));
  });

  it("shows nothing for the civil profile", async () => {
    profile.current = { name: "civil", marking: "" };
    const { container } = render(<SessionProvider><ProfileBanner position="top" /></SessionProvider>);
    await waitFor(() => expect(container.querySelector("[data-testid='marking-top']")).toBeNull());
  });
});
