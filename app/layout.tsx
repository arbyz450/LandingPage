
export const metadata = {
  title: "Appraisal Quest Co | Ventura County Appraiser",
  description:
    "Certified Ventura County home appraiser providing estate, divorce and date of death valuations."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
