"use client";

import Link from "next/link";
import { Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";

type ChatHeaderProps = {
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
};

export function ChatHeader({ onToggleSidebar, sidebarOpen }: ChatHeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border/60 bg-background/95 px-3 backdrop-blur sm:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 lg:hidden"
        onClick={onToggleSidebar}
        aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
      >
        {sidebarOpen ? <X className="size-5" /> : <Menu className="size-5" />}
      </Button>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">Health chat</p>
        <p className="truncate text-xs text-muted-foreground">
          Guidance only — not a diagnosis
        </p>
      </div>

      <Button variant="ghost" size="sm" className="hidden shrink-0 sm:inline-flex" asChild>
        <Link href={routes.dashboard}>Dashboard</Link>
      </Button>
    </header>
  );
}
