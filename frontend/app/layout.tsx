import "./globals.css";

export const metadata = {
  title: "CoinTwin MVP",
  description: "Personal decision twin MVP skeleton",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
