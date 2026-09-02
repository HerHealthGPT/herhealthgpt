"use client";

import { useCallback, useEffect, useState } from "react";

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
};

const EMPTY: DashboardData = {
  sessions: [],
  sessionDetails: [],
  articles: buildArticleRecommendations([]),
  exploredTopics: [],
  hasChats: false,
  concludedCount: 0,
};

async function fetchDashboardData(): Promise<DashboardData> {
  const sessions = await listTriageSessions();
  const sorted = [...sessions].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  const detailTargets = sorted
    .filter((s) => s.status === "concluded")
    .slice(0, 5);

  const sessionDetails = await Promise.all(
    detailTargets.map((s) => getTriageSession(s.id)),
  );

  const exploredTopics = collectExploredTopics(sessionDetails);
  const articles = buildArticleRecommendations(sessionDetails);

  return {
    sessions: sorted,
    sessionDetails,
    articles,
    exploredTopics,
    hasChats: sorted.length > 0,
    concludedCount: sorted.filter((s) => s.status === "concluded").length,
  };
}

export function useDashboardData() {
  const [data, setData] = useState<DashboardData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => {
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
      .catch(() => {
        if (!cancelled) {
          setError("Could not load your dashboard data.");
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
