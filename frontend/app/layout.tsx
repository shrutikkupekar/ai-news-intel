export const metadata = {
  title: "AI News Intelligence",
  description: "Real-time news ingestion and story intelligence",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          background: "#0b0c0f",
          color: "#e6e6e6",
        }}
      >
        {children}
      </body>
    </html>
  );
}
