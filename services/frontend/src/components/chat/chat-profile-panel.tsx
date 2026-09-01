"use client";

import Link from "next/link";
import { LayoutDashboard, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/contexts/auth-context";
import { routes } from "@/lib/routes";

type ChatProfilePanelProps = {
  open: boolean;
  onClose: () => void;
};

export function ChatProfilePanel({ open, onClose }: ChatProfilePanelProps) {
  const { user, signOut } = useAuth();

  if (!open) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-black/30 lg:hidden"
        onClick={onClose}
        aria-label="Close profile"
      />
      <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col border-l border-border/60 bg-background shadow-xl">
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-4">
          <h2 className="text-lg font-semibold">Your account</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        <div className="flex flex-1 flex-col gap-4 p-4">
          <div className="rounded-2xl border border-border/60 bg-muted/30 p-4">
            <p className="text-sm text-muted-foreground">Signed in as</p>
            <p className="mt-1 break-all font-medium">{user?.email}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              {user?.email_verified ? "Email verified" : "Email not verified yet"}
            </p>
          </div>

          <Separator />

          <Button variant="outline" className="justify-start" asChild>
            <Link href={routes.dashboard} onClick={onClose}>
              <LayoutDashboard className="size-4" />
              Dashboard
            </Link>
          </Button>

          <Button
            variant="outline"
            className="justify-start"
            onClick={() => void signOut()}
          >
            <LogOut className="size-4" />
            Sign out
          </Button>
        </div>
      </aside>
    </>
  );
}
