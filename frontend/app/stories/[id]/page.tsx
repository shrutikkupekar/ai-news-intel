import Link from "next/link";
import { notFound } from "next/navigation";

// Server components run inside the web container, where localhost is the
// container itself; the API is reachable by its compose service name
const API_URL = process.env.INTERNAL_API_URL || "http://api:8000";

interface StoryArticle {
  id: number;
  title: string;
  url: string;
  source_name: string;
  published_at: string | null;
  created_at: string;
  similarity: number | null;
}

interface StoryDetail {
  id: number;
  title: string;
  article_count: number;
  source_count: number;
  source_names: string[];
  first_article_at: string;
  latest_article_at: string;
  topic: string;
  articles: StoryArticle[];
}

type StoryResult =
  | { status: "ok"; story: StoryDetail }
  | { status: "missing" }
  | { status: "error" };

async function getStory(id: string): Promise<StoryResult> {
  try {
    const res = await fetch(`${API_URL}/api/stories/${id}`, {
      cache: "no-store",
    });
    if (res.status === 404) return { status: "missing" };
    if (!res.ok) return { status: "error" };
    return { status: "ok", story: await res.json() };
  } catch {
    return { status: "error" };
  }
}

function formatTime(iso: string): string {
  const formatted = new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
  return `${formatted} UTC`;
}

const muted = { color: "#8b8f98" };

export default async function StoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();

  const result = await getStory(id);
  if (result.status === "missing") notFound();

  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: "32px 16px 64px" }}>
      <Link href="/" style={{ color: "#9cc3ff", textDecoration: "none", fontSize: 14 }}>
        ← All stories
      </Link>

      {result.status === "error" && (
        <div
          style={{
            marginTop: 20,
            background: "#1a1214",
            border: "1px solid #5a2a2a",
            borderRadius: 10,
            padding: "16px 18px",
          }}
        >
          <strong>Couldn&apos;t reach the news API.</strong>
          <p style={{ ...muted, margin: "6px 0 0" }}>
            The stories service at {API_URL} isn&apos;t responding. Check that
            the api container is running, then refresh.
          </p>
        </div>
      )}

      {result.status === "ok" && <StoryView story={result.story} />}
    </main>
  );
}

function StoryView({ story }: { story: StoryDetail }) {
  return (
    <>
      <h1 style={{ fontSize: 26, lineHeight: 1.3, margin: "16px 0 10px" }}>
        {story.title}
      </h1>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "4px 14px",
          fontSize: 14,
          ...muted,
        }}
      >
        <span style={{ color: "#e6e6e6", fontWeight: 500 }}>
          {story.article_count} {story.article_count === 1 ? "article" : "articles"} ·{" "}
          {story.source_count} {story.source_count === 1 ? "source" : "sources"}
        </span>
        <span>{story.topic}</span>
        <span>First {formatTime(story.first_article_at)}</span>
        <span>Latest {formatTime(story.latest_article_at)}</span>
      </div>

      <ol style={{ listStyle: "none", padding: 0, margin: "28px 0 0" }}>
        {story.articles.map((article) => {
          // Some feeds don't give a publish date; fall back to when we ingested it
          const time = article.published_at ?? article.created_at;
          return (
            <li
              key={article.id}
              style={{
                background: "#13151a",
                border: "1px solid #23262d",
                borderRadius: 10,
                padding: "14px 18px",
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "2px 12px",
                  alignItems: "baseline",
                  fontSize: 13,
                  marginBottom: 6,
                }}
              >
                <span style={{ color: "#9cc3ff", fontWeight: 600 }}>
                  {article.source_name}
                </span>
                <time dateTime={time} style={{ color: "#c9cdd4" }}>
                  {formatTime(time)}
                  {article.published_at === null && " (ingested)"}
                </time>
              </div>
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "#e6e6e6",
                  fontSize: 16,
                  lineHeight: 1.4,
                  fontWeight: 500,
                  textDecoration: "none",
                }}
              >
                {article.title} <span style={muted}>↗</span>
              </a>
            </li>
          );
        })}
      </ol>
    </>
  );
}
