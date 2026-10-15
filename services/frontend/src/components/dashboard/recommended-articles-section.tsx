"use client";

import { BookOpen } from "lucide-react";

import { ArticleCard } from "@/components/dashboard/article-card";
import { Skeleton } from "@/components/ui/skeleton";
import type { HealthArticle } from "@/lib/health-articles";
import { useI18n } from "@/i18n/locale-provider";

type RecommendedArticlesSectionProps = {
  articles: HealthArticle[];
  loading?: boolean;
  personalized?: boolean;
};

export function RecommendedArticlesSection({
  articles,
  loading,
  personalized,
}: RecommendedArticlesSectionProps) {
  const { m, locale } = useI18n();
  const d = m.dashboard;
  return (
    <section>
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="size-5 text-primary" />
            <h2 className="text-lg font-semibold tracking-tight">
              {personalized ? d.recommended : d.explore}
            </h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {personalized ? d.recommendedLead : d.exploreLead}
            {locale !== "en" ? ` ${d.articlesInEnglish}` : null}
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex gap-4 overflow-hidden pb-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-[260px] shrink-0 rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="-mx-4 flex gap-4 overflow-x-auto px-4 pb-2 scrollbar-thin sm:-mx-6 sm:px-6">
          {articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      )}

      <p className="mt-3 text-xs text-muted-foreground">
        {d.articlesDisclaimer}
      </p>
    </section>
  );
}
