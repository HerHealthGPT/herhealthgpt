"use client";

import Link from "next/link";
import { ArrowLeft, Menu, UserCircle2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";

type ChatHeaderProps = {
  onToggleSidebar: () => void;
  onOpenProfile: () => void;
  sidebarOpen: boolean;
};

export function ChatHeader({
  onToggleSidebar,
  onOpenProfile,
  sidebarOpen,
}: ChatHeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border/60 bg-background/95 px-3 backdrop-blur sm:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 lg:hidden"
        onClick={onToggleSidebar}
        aria-label={sidebarOpen ? "Close conversations" : "Open conversations"}
      >
        {sidebarOpen ? <X className="size-5" /> : <Menu className="size-5" />}
      </Button>

      <Button variant="ghost" size="icon" className="shrink-0" asChild>
        <Link href={routes.dashboard} aria-label="Back to dashboard">
          <ArrowLeft className="size-5" />
        </Link>
      </Button>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">Health chat</p>
        <p className="truncate text-xs text-muted-foreground">
          Guidance only — not a diagnosis
        </p>
      </div>

      <Button
        variant="outline"
        size="icon"
        className="shrink-0"
        onClick={onOpenProfile}
        aria-label="Open profile"
      >
        <UserCircle2 className="size-5" />
      </Button>
    </header>
  );
}
