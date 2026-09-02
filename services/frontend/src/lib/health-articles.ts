import type { CitedPassage, TriageSessionDetail } from "@/lib/api/types";
import { conditionLabel } from "@/lib/condition-labels";

export type HealthArticle = {
  id: string;
  title: string;
  excerpt: string;
  url: string;
  source_id: string;
  /** Condition ids this article relates to — used for personalization. */
  topic_ids: string[];
  /** Tailwind gradient classes for the card header when no cover image is set. */
  gradient: string;
  /** Hero image from the source article page (womenshealth heading-images, etc.). */
  cover_image_url?: string;
  cover_image_alt?: string;
  /** Where this card came from. */
  origin: "curated" | "chat";
  /** Short reason shown on personalized cards. */
  reason?: string;
};

/**
 * Curated articles from reviewed sources (ingest.lock.jsonl / ingest_targets.yaml).
 * URLs are real pages we have fetched and verified — not invented.
 */
export const CURATED_ARTICLES: HealthArticle[] = [
  {
    id: "menstruation",
    title: "Your menstrual cycle",
    excerpt:
      "What a normal cycle looks like, common changes, and when to see a doctor.",
    url: "https://womenshealth.gov/a-z-topics/menstruation-and-menstrual-cycle",
    source_id: "womenshealth",
    topic_ids: ["normal_variation", "perimenopause", "pcos"],
    gradient: "from-rose-400/30 via-primary/15 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/styles/large/public/bucket-images/Yourmenstrualcycle.jpg",
    cover_image_alt: "Illustration related to the menstrual cycle",
    origin: "curated",
  },
  {
    id: "endometriosis",
    title: "Endometriosis",
    excerpt:
      "Symptoms, causes, and when pelvic pain during your period needs a closer look.",
    url: "https://womenshealth.gov/a-z-topics/endometriosis",
    source_id: "womenshealth",
    topic_ids: ["endometriosis", "adenomyosis"],
    gradient: "from-fuchsia-400/25 via-primary/10 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/heading-images/Endometriosis.jpg",
    cover_image_alt:
      "A person resting on a sofa, curled up with knees drawn in",
    origin: "curated",
  },
  {
    id: "pcos",
    title: "Polycystic ovary syndrome",
    excerpt:
      "Irregular periods, hormone changes, and what sources say about PCOS.",
    url: "https://womenshealth.gov/a-z-topics/polycystic-ovary-syndrome",
    source_id: "womenshealth",
    topic_ids: ["pcos"],
    gradient: "from-violet-400/25 via-primary/10 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/heading-images/Polycysticovarysyndrome.jpg",
    cover_image_alt: "Healthcare provider speaking with a patient",
    origin: "curated",
  },
  {
    id: "fibroids",
    title: "Uterine fibroids",
    excerpt:
      "Heavy bleeding, pelvic pressure, and when fibroids may be worth discussing.",
    url: "https://womenshealth.gov/a-z-topics/uterine-fibroids",
    source_id: "womenshealth",
    topic_ids: ["uterine_fibroids"],
    gradient: "from-orange-300/25 via-primary/10 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/heading-images/Uterinefibroids.jpg",
    cover_image_alt: "Person in a consultation with a clinician",
    origin: "curated",
  },
  {
    id: "uti",
    title: "Urinary tract infections",
    excerpt:
      "Burning, urgency, and when urinary symptoms need treatment.",
    url: "https://womenshealth.gov/a-z-topics/urinary-tract-infections",
    source_id: "womenshealth",
    topic_ids: ["urinary_tract_infection", "bladder_pain"],
    gradient: "from-sky-400/25 via-primary/10 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/heading-images/Urinarytractinfections.jpg",
    cover_image_alt: "Person drinking water at home",
    origin: "curated",
  },
  {
    id: "infertility",
    title: "Infertility",
    excerpt:
      "Trying to conceive, common causes, and when to talk to a clinician.",
    url: "https://womenshealth.gov/a-z-topics/infertility",
    source_id: "womenshealth",
    topic_ids: ["infertility", "pcos", "endometriosis"],
    gradient: "from-emerald-400/20 via-primary/10 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/heading-images/Infertility.jpg",
    cover_image_alt: "Couple sitting together on a sofa",
    origin: "curated",
  },
  {
    id: "thyroid",
    title: "Thyroid disease",
    excerpt:
      "How thyroid problems can affect periods, energy, and weight.",
    url: "https://womenshealth.gov/a-z-topics/thyroid-disease",
    source_id: "womenshealth",
    topic_ids: ["hypothyroidism"],
    gradient: "from-amber-300/25 via-primary/10 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/heading-images/Thyroiddisease.jpg",
    cover_image_alt: "Clinician examining a patient's neck",
    origin: "curated",
  },
  {
    id: "sti",
    title: "Sexually transmitted infections",
    excerpt:
      "Symptoms, testing, and why discharge or pelvic pain may need a check.",
    url: "https://womenshealth.gov/a-z-topics/sexually-transmitted-infections",
    source_id: "womenshealth",
    topic_ids: ["sexually_transmitted_infection", "pelvic_inflammatory_disease"],
    gradient: "from-pink-400/25 via-primary/10 to-background",
    cover_image_url:
      "https://womenshealth.gov/sites/default/files/heading-images/Sexuallytransmittedinfections.jpg",
    cover_image_alt: "Healthcare provider in a clinical setting",
    origin: "curated",
  },
];

/** Cover art keyed by canonical article URL — reused for chat citations. */
const COVER_BY_URL = new Map(
  CURATED_ARTICLES.filter((article) => article.cover_image_url).map((article) => [
    article.url,
    {
      cover_image_url: article.cover_image_url!,
      cover_image_alt: article.cover_image_alt,
    },
  ]),
);

function passageToArticle(
  passage: CitedPassage,
  reason: string,
): HealthArticle | null {
  if (!passage.url) return null;

  const excerpt =
    passage.text.length > 140
      ? `${passage.text.slice(0, 137).trim()}…`
      : passage.text;

  return {
    id: `chat-${passage.id}`,
    title: passage.citation || "From your recent chat",
    excerpt,
    url: passage.url,
    source_id: passage.source_id,
    topic_ids: [],
    gradient: "from-primary/20 via-accent/30 to-background",
    ...COVER_BY_URL.get(passage.url),
    origin: "chat",
    reason,
  };
}

/** Collect condition ids mentioned across concluded sessions. */
export function collectExploredTopics(
  sessions: TriageSessionDetail[],
): string[] {
  const topics = new Set<string>();
  for (const session of sessions) {
    for (const message of session.messages) {
      if (message.role !== "assistant" || !message.decision) continue;
      for (const id of message.decision.matching_conditions) {
        topics.add(id);
      }
    }
  }
  return [...topics];
}

/**
 * Build a deduplicated article list: chat citations first, then curated
 * articles matched to explored topics, then general starters.
 */
export function buildArticleRecommendations(
  sessionDetails: TriageSessionDetail[],
  limit = 8,
): HealthArticle[] {
  const seen = new Set<string>();
  const articles: HealthArticle[] = [];

  const topics = collectExploredTopics(sessionDetails);

  // 1. Passages cited in the user's chats (most personal)
  for (const session of sessionDetails) {
    for (const message of session.messages) {
      if (message.role !== "assistant" || !message.decision?.cited_passages) {
        continue;
      }
      const conditions = message.decision.matching_conditions;
      const reason =
        conditions.length > 0
          ? `Related to ${conditionLabel(conditions[0])} from your chat`
          : "Cited in your recent chat";

      for (const passage of message.decision.cited_passages) {
        if (!passage.url || seen.has(passage.url)) continue;
        const article = passageToArticle(passage, reason);
        if (!article) continue;
        seen.add(passage.url);
        articles.push(article);
      }
    }
  }

  // 2. Curated articles matching explored topics
  const curatedMatches = CURATED_ARTICLES.filter((article) =>
    article.topic_ids.some((id) => topics.includes(id)),
  );
  const curatedRest = CURATED_ARTICLES.filter(
    (article) => !curatedMatches.includes(article),
  );

  for (const article of [...curatedMatches, ...curatedRest]) {
    if (seen.has(article.url)) continue;
    seen.add(article.url);
    const personalized =
      topics.length > 0 &&
      article.topic_ids.some((id) => topics.includes(id));
    articles.push({
      ...article,
      reason: personalized
        ? `Based on topics from your chats`
        : undefined,
    });
    if (articles.length >= limit) break;
  }

  return articles.slice(0, limit);
}
