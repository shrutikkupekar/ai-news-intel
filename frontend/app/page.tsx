import Link from "next/link";

// Server components run inside the web container, where localhost is the
// container itself; the API is reachable by its compose service name
const API_URL = process.env.INTERNAL_API_URL || "http://api:8000";
const PAGE_SIZE = 20;

interface StorySummary {
  id: number;
  title: string;
  article_count: number;
  source_count: number;
  source_names: string[];
  first_article_at: string;
  latest_article_at: string;
  topic: string;
}

interface StoryList {
  total: number;
  limit: number;
  offset: number;
  items: StorySummary[];
}

async function getStories(
  minArticles: number,
  page: number
): Promise<StoryList | null> {
  const params = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String((page - 1) * PAGE_SIZE),
    min_articles: String(minArticles),
  });
  try {
    const res = await fetch(`${API_URL}/api/stories?${params}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
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

function timeAgo(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 60) return `${Math.max(minutes, 0)}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function pageHref(page: number, includeSingles: boolean): string {
  const params = new URLSearchParams();
  if (includeSingles) params.set("min", "1");
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/?${query}` : "/";
}

const styles = {
  main: { maxWidth: 820, margin: "0 auto", padding: "32px 16px 64px" },
  muted: { color: "#8b8f98" },
  card: {
    display: "block",
    background: "#13151a",
    border: "1px solid #23262d",
    borderRadius: 10,
    padding: "16px 18px",
    marginBottom: 12,
    color: "inherit",
    textDecoration: "none",
  },
  pill: {
    display: "inline-block",
    fontSize: 12,
    padding: "2px 8px",
    borderRadius: 999,
    background: "#1d2733",
    color: "#9cc3ff",
    whiteSpace: "nowrap" as const,
  },
  navLink: {
    color: "#9cc3ff",
    textDecoration: "none",
    padding: "8px 14px",
    border: "1px solid #2a2f38",
    borderRadius: 8,
    fontSize: 14,
  },
};

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; min?: string }>;
}) {
  const { page: pageParam, min } = await searchParams;
  const includeSingles = min === "1";
  const page = Math.max(1, Number.parseInt(pageParam ?? "1", 10) || 1);
  const data = await getStories(includeSingles ? 1 : 2, page);
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <main style={styles.main}>
      <h1 style={{ fontSize: 26, margin: "0 0 4px" }}>AI News Intelligence</h1>
      <p style={{ ...styles.muted, margin: "0 0 20px" }}>
        Stories clustered from articles across sources.
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 20,
          fontSize: 14,
        }}
      >
        <span style={styles.muted}>
          {includeSingles
            ? "Showing all stories, including single-article ones"
            : "Showing stories covered by 2 or more articles"}
          {data && ` · ${data.total} total`}
        </span>
        <Link href={pageHref(1, !includeSingles)} style={{ color: "#9cc3ff" }}>
          {includeSingles
            ? "Show only multi-article stories"
            : "Include single-article stories"}
        </Link>
      </div>

      {data === null && (
        <div
          style={{
            ...styles.card,
            borderColor: "#5a2a2a",
            background: "#1a1214",
          }}
        >
          <strong>Couldn&apos;t reach the news API.</strong>
          <p style={{ ...styles.muted, margin: "6px 0 0" }}>
            The stories service at {API_URL} isn&apos;t responding. Check that
            the api container is running, then refresh.
          </p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <p style={styles.muted}>
          {page > 1 ? "No stories on this page." : "No stories yet."}
        </p>
      )}

      {data?.items.map((story) => (
        <Link key={story.id} href={`/stories/${story.id}`} style={styles.card}>
          <div
            style={{
              display: "flex",
              gap: 12,
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <h2
              style={{
                fontSize: 17,
                lineHeight: 1.35,
                margin: 0,
                fontWeight: 600,
              }}
            >
              {story.title}
            </h2>
            <span style={styles.pill}>{story.topic}</span>
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "4px 14px",
              marginTop: 10,
              fontSize: 13,
            }}
          >
            <span style={{ color: "#e6e6e6", fontWeight: 500 }}>
              {story.article_count}{" "}
              {story.article_count === 1 ? "article" : "articles"} ·{" "}
              {story.source_count}{" "}
              {story.source_count === 1 ? "source" : "sources"}
            </span>
            <span style={{ color: "#c9cdd4" }}>
              {story.source_names.join(", ")}
            </span>
          </div>
          <div style={{ ...styles.muted, fontSize: 13, marginTop: 6 }}>
            Latest {formatTime(story.latest_article_at)} (
            {timeAgo(story.latest_article_at)})
          </div>
        </Link>
      ))}

      {data && data.total > PAGE_SIZE && (
        <nav
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginTop: 24,
          }}
        >
          {page > 1 ? (
            <Link href={pageHref(page - 1, includeSingles)} style={styles.navLink}>
              ← Newer
            </Link>
          ) : (
            <span />
          )}
          <span style={{ ...styles.muted, fontSize: 14 }}>
            Page {page} of {totalPages}
          </span>
          {page < totalPages ? (
            <Link href={pageHref(page + 1, includeSingles)} style={styles.navLink}>
              Older →
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </main>
  );
}
