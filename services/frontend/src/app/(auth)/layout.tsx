import { GuestGuard } from "@/components/auth/guest-guard";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <GuestGuard>
      <div className="flex min-h-full flex-1 flex-col">{children}</div>
    </GuestGuard>
  );
}
