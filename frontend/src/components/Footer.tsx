export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="mt-20 border-t border-[var(--line)] px-4 pb-14 pt-10">
      <div className="page-wrap flex flex-col items-center gap-3 text-center">
        <p className="m-0 text-sm text-[var(--ink-soft)]">
          &copy; {year} HomeBidder
        </p>
        <p className="m-0 max-w-md text-xs text-[var(--ink-muted)] leading-relaxed">
          For informational purposes only. Not a substitute for professional real estate advice.
          Always consult a licensed agent before making an offer.
        </p>
      </div>
    </footer>
  )
}
