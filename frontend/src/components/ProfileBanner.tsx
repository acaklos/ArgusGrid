import { useSession } from "../state/session";

/** Classification marking of the deployment profile (ARG-021): on every screen, including the login page. */
export function ProfileBanner({ position }: { position: "top" | "bottom" }) {
  const { session } = useSession();
  const marking = session?.profile?.marking ?? "";
  if (!marking) return null;
  return (
    <div className={`marking marking--${position}`} role="note" data-testid={`marking-${position}`}>
      {marking}
    </div>
  );
}
