export const metadata = {
  title: "基金涨幅估算",
  description: "根据十大重仓股实时涨跌幅估算基金当日涨幅",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
