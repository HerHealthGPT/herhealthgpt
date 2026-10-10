"use client";

import { useCallback, useEffect, useState } from "react";

import { friendlyApiError } from "@/lib/api/errors";
import { getTriageSession, listTriageSessions } from "@/lib/api/triage";
import type { TriageSessionDetail, TriageSessionSummary } from "@/lib/api/types";
import {
  buildArticleRecommendations,
  collectExploredTopics,
} from "@/lib/health-articles";
import type { HealthArticle } from "@/lib/health-articles";

export type DashboardData = {
  sessions: TriageSessionSummary[];
  sessionDetails: TriageSessionDetail[];
  articles: HealthArticle[];
  exploredTopics: string[];
  hasChats: boolean;
  concludedCount: number;
  /** Most recent session still in progress, if any. */
  activeSession: TriageSessionSummary | null;
};

const EMPTY: DashboardData = {
  sessions: [],
  sessionDetails: [],
  articles: buildArticleRecommendations([]),
  exploredTopics: [],
  hasChats: false,
  concludedCount: 0,
  activeSession: null,
};

async function fetchDashboardData(): Promise<DashboardData> {
  const sessions = await listTriageSessions();
  const sorted = [...sessions].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(b.created_at).getTime(),
  );

  const detailTargets = sorted
    .filter((s) => s.status === "concluded")
    .slice(0, 5);

  const detailResults = await Promise.allSettled(
    detailTargets.map((s) => getTriageSession(s.id)),
  );
  const sessionDetails = detailResults
    .filter(
      (result): result is PromiseFulfilledResult<TriageSessionDetail> =>
        result.status === "fulfilled",
    )
    .map((result) => result.value);

  const exploredTopics = collectExploredTopics(sessionDetails);
  const articles = buildArticleRecommendations(sessionDetails);
  const activeSession =
    sorted.find((session) => session.status === "active") ?? null;

  return {
    sessions: sorted,
    sessionDetails,
    articles,
    exploredTopics,
    hasChats: sorted.length > 0,
    concludedCount: sorted.filter((s) => s.status === "concluded").length,
    activeSession,
  };
}

export function useDashboardData() {
  const [data, setData] = useState<DashboardData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => {
    setLoading(true);
    setReloadToken((t) => t + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetchDashboardData()
      .then((next) => {
        if (!cancelled) {
          setData(next);
          setError(null);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(friendlyApiError(caught));
          setData({ ...EMPTY, articles: buildArticleRecommendations([]) });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  return { data, loading, error, reload };
}
