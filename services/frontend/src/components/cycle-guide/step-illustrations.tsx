/**
 * The four step cards of the cycle-data guide, drawn rather than
 * screenshotted: no app's logo or screens, so nothing to license, nothing
 * that goes out of date when an app is redesigned, and nothing in English
 * that an Arabic or French reader has to decode.
 *
 * Every stroke is `currentColor` or a theme token, so the cards follow light
 * and dark mode. The spreadsheet's column names are the file's real column
 * names and stay left-to-right in every language, because that is how she
 * will see them in her spreadsheet app.
 */

type IllustrationProps = { className?: string };

const frame = "fill-background stroke-border";

export function DownloadTemplateIllustration({ className }: IllustrationProps) {
  return (
    <svg viewBox="0 0 160 120" className={className} role="img" aria-hidden>
      <rect x="44" y="10" width="72" height="92" rx="8" className={frame} strokeWidth="2" />
      <path d="M96 10v18h20" className="fill-none stroke-border" strokeWidth="2" />
      {[34, 46, 58].map((y) => (
        <rect key={y} x="56" y={y} width="48" height="6" rx="3" className="fill-muted" />
      ))}
      <rect x="56" y="72" width="22" height="12" rx="3" className="fill-primary/15" />
      <text x="67" y="81" textAnchor="middle" className="fill-primary" fontSize="8" fontWeight="700">
        CSV
      </text>
      <circle cx="112" cy="94" r="16" className="fill-primary" />
      <path
        d="M112 86v14m-6-6 6 6 6-6"
        className="fill-none stroke-primary-foreground"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function FillRowsIllustration({ className }: IllustrationProps) {
  const columns = ["date", "flow", "symptoms"];
  const rows = [
    ["2026-10-01", "heavy", "cramps"],
    ["2026-10-02", "medium", ""],
    ["2026-10-03", "light", ""],
  ];
  return (
    <svg viewBox="0 0 160 120" className={className} role="img" aria-hidden direction="ltr">
      <rect x="8" y="14" width="144" height="92" rx="8" className={frame} strokeWidth="2" />
      <rect x="8" y="14" width="144" height="20" rx="8" className="fill-muted" />
      {columns.map((name, index) => (
        <text
          key={name}
          x={16 + index * 48}
          y={28}
          className="fill-foreground"
          fontSize="8"
          fontWeight="700"
          fontFamily="ui-monospace, monospace"
        >
          {name}
        </text>
      ))}
      {[56, 104].map((x) => (
        <line key={x} x1={x} y1="14" x2={x} y2="106" className="stroke-border" strokeWidth="1" />
      ))}
      {rows.map((row, r) => (
        <g key={r}>
          <line
            x1="8"
            y1={34 + r * 22}
            x2="152"
            y2={34 + r * 22}
            className="stroke-border"
            strokeWidth="1"
          />
          {row.map((cell, c) =>
            cell ? (
              <text
                key={c}
                x={16 + c * 48}
                y={48 + r * 22}
                className={c === 0 ? "fill-muted-foreground" : "fill-primary"}
                fontSize="7"
                fontFamily="ui-monospace, monospace"
              >
                {cell}
              </text>
            ) : null,
          )}
        </g>
      ))}
    </svg>
  );
}

export function SaveAsCsvIllustration({ className }: IllustrationProps) {
  return (
    <svg viewBox="0 0 160 120" className={className} role="img" aria-hidden direction="ltr">
      <rect x="20" y="12" width="120" height="96" rx="8" className={frame} strokeWidth="2" />
      <rect x="20" y="12" width="120" height="16" rx="8" className="fill-muted" />
      <rect
        x="36"
        y="38"
        width="88"
        height="56"
        rx="6"
        className="fill-background stroke-border"
        strokeWidth="1.5"
      />
      <rect x="44" y="48" width="72" height="10" rx="3" className="fill-muted" />
      <rect
        x="44"
        y="64"
        width="72"
        height="14"
        rx="4"
        className="fill-primary/15 stroke-primary"
        strokeWidth="1.5"
      />
      <text x="80" y="74" textAnchor="middle" className="fill-primary" fontSize="8" fontWeight="700">
        CSV (UTF-8)
      </text>
      <circle cx="122" cy="88" r="11" className="fill-primary" />
      <path
        d="M117 88l4 4 6-8"
        className="fill-none stroke-primary-foreground"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function UploadReviewIllustration({ className }: IllustrationProps) {
  return (
    <svg viewBox="0 0 160 120" className={className} role="img" aria-hidden>
      <rect x="48" y="6" width="64" height="108" rx="12" className={frame} strokeWidth="2" />
      <rect x="70" y="12" width="20" height="4" rx="2" className="fill-muted" />
      <rect x="56" y="24" width="48" height="44" rx="6" className="fill-primary/10" />
      {[32, 42, 52].map((y) => (
        <g key={y}>
          <circle cx="63" cy={y + 2} r="3" className="fill-primary" />
          <rect x="70" y={y} width="28" height="4" rx="2" className="fill-primary/40" />
        </g>
      ))}
      <rect x="56" y="76" width="48" height="12" rx="6" className="fill-primary" />
      <rect x="66" y="80.5" width="28" height="3" rx="1.5" className="fill-primary-foreground" />
      <circle cx="40" cy="92" r="14" className="fill-background stroke-primary" strokeWidth="2" />
      <path
        d="M44 87l-7 7a3 3 0 0 1-4-4l8-8a2 2 0 0 1 3 3l-7 7"
        className="fill-none stroke-primary"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export const STEP_ILLUSTRATIONS = [
  DownloadTemplateIllustration,
  FillRowsIllustration,
  SaveAsCsvIllustration,
  UploadReviewIllustration,
] as const;
