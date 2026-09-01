"use client";

import Link from "next/link";
import { Heart } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth-context";
import { routes } from "@/lib/routes";

export function SiteHeader() {
  const { user, isLoading, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Heart className="size-4 fill-current" aria-hidden />
          </span>
          <span className="text-lg font-semibold tracking-tight">
            HerHealth<span className="text-primary">GPT</span>
          </span>
        </Link>

        <nav className="flex items-center gap-2">
          {isLoading ? (
            <div className="h-8 w-24 animate-pulse rounded-lg bg-muted" />
          ) : user ? (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link href={routes.chat}>Health chat</Link>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link href={routes.dashboard}>Dashboard</Link>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void signOut()}
              >
                Sign out
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link href={routes.signIn}>Sign in</Link>
              </Button>
              <Button size="sm" asChild>
                <Link href={routes.signUp}>Sign up</Link>
              </Button>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
