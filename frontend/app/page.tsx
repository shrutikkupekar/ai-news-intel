const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Article {
  id: number;
  title: string;
  url: string;
  published_at: string | null;
  source: { name: string };
}

async function getArticles(): Promise<Article[]> {
  try {
    const res = await fetch(`${API_URL}/api/articles?limit=50`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function Home() {
  const articles = await getArticles();

  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "32px 16px" }}>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>AI News Intelligence</h1>
      <p style={{ color: "#888", marginBottom: 24 }}>
        Phase 1 — raw ingested articles, no clustering yet.
      </p>

      {articles.length === 0 && (
        <p style={{ color: "#888" }}>
          No articles yet. Trigger ingestion via{" "}
          <code>POST /api/ingest/run</code> or wait for the scheduled job.
        </p>
      )}

      <ul style={{ listStyle: "none", padding: 0 }}>
        {articles.map((a) => (
          <li
            key={a.id}
            style={{
              borderBottom: "1px solid #222",
              padding: "12px 0",
            }}
          >
            <a
              href={a.url}
              target="_blank"
              rel="noreferrer"
              style={{ color: "#e6e6e6", textDecoration: "none", fontWeight: 500 }}
            >
              {a.title}
            </a>
            <div style={{ fontSize: 13, color: "#888", marginTop: 4 }}>
              {a.source?.name}
              {a.published_at &&
                ` · ${new Date(a.published_at).toLocaleString()}`}
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
