import { ExternalLink } from "lucide-react";

import type { HealthArticle } from "@/lib/health-articles";
import { sourceLabel } from "@/lib/source-labels";
import { cn } from "@/lib/utils";

type ArticleCardProps = {
  article: HealthArticle;
  className?: string;
};

/**
 * Apple Health–inspired article tile: gradient header, title, trusted source,
 * short excerpt. Opens the original page in a new tab.
 */
export function ArticleCard({ article, className }: ArticleCardProps) {
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
          "relative h-24 bg-gradient-to-br px-4 py-3",
          article.gradient,
        )}
      >
        <span className="inline-flex rounded-full bg-background/80 px-2 py-0.5 text-[10px] font-medium text-muted-foreground backdrop-blur-sm">
          {sourceLabel(article.source_id)}
        </span>
        {article.origin === "chat" ? (
          <span className="absolute right-3 top-3 rounded-full bg-primary/90 px-2 py-0.5 text-[10px] font-medium text-primary-foreground">
            From your chat
          </span>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="line-clamp-2 text-sm font-semibold leading-snug tracking-tight group-hover:text-primary">
          {article.title}
        </h3>
        <p className="line-clamp-3 flex-1 text-xs leading-relaxed text-muted-foreground">
          {article.excerpt}
        </p>
        {article.reason ? (
          <p className="text-[10px] text-primary/80">{article.reason}</p>
        ) : null}
        <span className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary">
          Read on {sourceLabel(article.source_id)}
          <ExternalLink className="size-3 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
    </a>
  );
}
