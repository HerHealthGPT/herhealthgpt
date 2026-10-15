"use client";

import Image from "next/image";
import { ExternalLink } from "lucide-react";

import type { HealthArticle } from "@/lib/health-articles";
import { sourceLabel } from "@/lib/source-labels";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/locale-provider";

type ArticleCardProps = {
  article: HealthArticle;
  className?: string;
};

/**
 * Apple Health–inspired article tile: cover image (when available), title,
 * trusted source, short excerpt. Opens the original page in a new tab.
 */
export function ArticleCard({ article, className }: ArticleCardProps) {
  const hasCover = Boolean(article.cover_image_url);
  const { m } = useI18n();

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "group flex w-[260px] shrink-0 flex-col overflow-hidden rounded-2xl border border-border/70 bg-card shadow-sm transition-all hover:border-primary/30 hover:shadow-md sm:w-[280px]",
        className,
      )}
    >
      <div
        className={cn(
          "relative h-36 overflow-hidden",
          !hasCover && "bg-gradient-to-br px-4 py-3",
          !hasCover && article.gradient,
        )}
      >
        {hasCover ? (
          <>
            <Image
              src={article.cover_image_url!}
              alt={article.cover_image_alt ?? article.title}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
              sizes="(max-width: 640px) 260px, 280px"
            />
            <div
              className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/10 to-transparent"
              aria-hidden
            />
          </>
        ) : null}

        <span
          className={cn(
            "absolute start-3 top-3 z-10 inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium backdrop-blur-sm",
            hasCover
              ? "bg-background/90 text-foreground"
              : "bg-background/80 text-muted-foreground",
          )}
        >
          {sourceLabel(article.source_id, m)}
        </span>
        {article.origin === "chat" ? (
          <span className="absolute end-3 top-3 z-10 rounded-full bg-primary/90 px-2 py-0.5 text-[10px] font-medium text-primary-foreground">
            {m.dashboard.fromYourChat}
          </span>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="line-clamp-2 text-sm font-semibold leading-snug tracking-tight group-hover:text-primary">
          {m.articles.items[article.id]?.title ?? article.title}
        </h3>
        <p className="line-clamp-3 flex-1 text-xs leading-relaxed text-muted-foreground">
          {m.articles.items[article.id]?.excerpt ?? article.excerpt}
        </p>
        {article.reason ? (
          <p className="text-[10px] text-primary/80">{article.reason}</p>
        ) : null}
        <span className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary">
          {m.dashboard.readOn(sourceLabel(article.source_id, m))}
          <ExternalLink className="size-3 transition-transform group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
        </span>
      </div>
    </a>
  );
}
