"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Heart, Menu, X } from "lucide-react";

import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth-context";
import { useI18n } from "@/i18n/locale-provider";
import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  const { user, isLoading, signOut } = useAuth();
  const pathname = usePathname();
  const { m } = useI18n();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const isDashboard = pathname === routes.dashboard;
  const isChat = pathname.startsWith(routes.chat);
  const isSettings = pathname === routes.settings;

  function closeMenu() {
    setMenuOpen(false);
  }

  async function handleSignOut() {
    closeMenu();
    await signOut();
  }

  const authLinks = user ? (
    <>
      {!isChat ? (
        <Button variant="ghost" size="sm" asChild onClick={closeMenu}>
          <Link href={routes.chat}>{m.nav.healthChat}</Link>
        </Button>
      ) : null}
      {!isDashboard ? (
        <Button variant="ghost" size="sm" asChild onClick={closeMenu}>
          <Link href={routes.dashboard}>{m.nav.dashboard}</Link>
        </Button>
      ) : null}
      {!isSettings ? (
        <Button variant="ghost" size="sm" asChild onClick={closeMenu}>
          <Link href={routes.settings}>{m.nav.account}</Link>
        </Button>
      ) : null}
      <Button variant="ghost" size="sm" asChild onClick={closeMenu}>
        <Link href={routes.howItWorks}>{m.nav.howItWorks}</Link>
      </Button>
      <Button variant="outline" size="sm" onClick={() => void handleSignOut()}>
        {m.common.signOut}
      </Button>
    </>
  ) : (
    <>
      <Button variant="ghost" size="sm" asChild onClick={closeMenu}>
        <Link href={routes.signIn}>{m.common.signIn}</Link>
      </Button>
      <Button size="sm" asChild onClick={closeMenu}>
        <Link href={routes.signUp}>{m.common.signUp}</Link>
      </Button>
    </>
  );

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 min-w-0 max-w-6xl items-center justify-between gap-3 px-4 sm:h-16 sm:px-6">
        <Link
          href={user ? routes.dashboard : routes.home}
          className="flex min-w-0 shrink items-center gap-2"
          onClick={closeMenu}
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Heart className="size-4 fill-current" aria-hidden />
          </span>
          <span className="truncate text-base font-semibold tracking-tight sm:text-lg">
            HerHealth<span className="text-primary">GPT</span>
          </span>
        </Link>

        {isLoading ? (
          <div className="h-8 w-20 shrink-0 animate-pulse rounded-lg bg-muted sm:w-24" />
        ) : (
          <>
            <nav className="hidden min-w-0 items-center gap-1 sm:flex sm:gap-2">
              <LanguageSwitcher />
              {authLinks}
            </nav>

            <LanguageSwitcher className="ms-auto sm:hidden" />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0 sm:hidden"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-controls="site-header-mobile-menu"
              aria-label={menuOpen ? m.common.closeMenu : m.common.openMenu}
            >
              {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
            </Button>
          </>
        )}
      </div>

      {menuOpen && !isLoading ? (
        <nav
          id="site-header-mobile-menu"
          className={cn(
            "flex flex-col gap-1 border-t border-border/60 px-4 py-3 sm:hidden",
            "animate-in fade-in slide-in-from-top-1 duration-200",
          )}
        >
          {user ? (
            <>
              {!isChat ? (
                <Button variant="ghost" className="justify-start" asChild onClick={closeMenu}>
                  <Link href={routes.chat}>{m.nav.healthChat}</Link>
                </Button>
              ) : null}
              {!isDashboard ? (
                <Button variant="ghost" className="justify-start" asChild onClick={closeMenu}>
                  <Link href={routes.dashboard}>{m.nav.dashboard}</Link>
                </Button>
              ) : null}
              {!isSettings ? (
                <Button variant="ghost" className="justify-start" asChild onClick={closeMenu}>
                  <Link href={routes.settings}>{m.nav.account}</Link>
                </Button>
              ) : null}
              <Button variant="ghost" className="justify-start" asChild onClick={closeMenu}>
                <Link href={routes.howItWorks}>{m.nav.howItWorks}</Link>
              </Button>
              <Button
                variant="outline"
                className="justify-start"
                onClick={() => void handleSignOut()}
              >
                {m.common.signOut}
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" className="justify-start" asChild onClick={closeMenu}>
                <Link href={routes.signIn}>{m.common.signIn}</Link>
              </Button>
              <Button className="justify-start" asChild onClick={closeMenu}>
                <Link href={routes.signUp}>{m.common.signUp}</Link>
              </Button>
            </>
          )}
        </nav>
      ) : null}
    </header>
  );
}
