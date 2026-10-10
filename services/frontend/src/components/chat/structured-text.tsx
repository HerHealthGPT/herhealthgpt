/**
 * Renders an assistant answer's own light structure — section headings and
 * bullet lists — as real elements instead of pre-wrapped text.
 *
 * **Why not a markdown library.** An informational answer (ADR 0016) is the
 * longest text this product shows and the one that most needs typography, so
 * the obvious move is react-markdown. It is also a new runtime dependency and
 * a new transitive tree, pulled in to format four kinds of line, a week after
 * a foreign bundle reached this repo through exactly that surface (see
 * docs/security/0001-injected-postcss-payload-and-leaked-env-backup.md). The
 * grammar the model is asked for is small enough to parse here in a few lines,
 * with no dependency and no `dangerouslySetInnerHTML`, so that is what this
 * does.
 *
 * The grammar, which `DEFAULT_SYSTEM_PROMPT` asks the model to produce:
 *
 *   What it is:                 <- a short line ending in ':' is a heading
 *                               <- a blank line separates sections
 *   - Irregular periods         <- a line starting with '- ' is a list item
 *   - Excess hair growth
 *
 * Everything else is a paragraph.
 *
 * **It is deliberately tolerant of markdown it was told not to emit.** Models
 * reach for `###` and `**bold**` regardless of instruction — the first good
 * PCOS answer did — and the failure mode of a strict parser is the literal
 * characters `### What is PCOS?` arriving in front of a worried user. So
 * markdown emphasis and heading markers are stripped rather than displayed,
 * and `*` and `•` are accepted as bullets alongside `-`. Being lenient here
 * costs nothing and removes a whole class of visible defect.
 */

type Block =
  | { kind: "heading"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "paragraph"; lines: string[] };

/** A heading is short and ends in a colon. The length cap matters: without it
 *  an ordinary sentence that happens to end in a colon becomes a heading. */
const HEADING = /^(.{1,60}):$/;
const BULLET = /^\s*[-*•]\s+(.*)$/;

/** Markdown the model was asked not to use. Stripped, never shown. */
function stripMarkdown(line: string): string {
  return line
    .replace(/^#{1,6}\s*/, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .trimEnd();
}

export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  let list: string[] = [];
  let paragraph: string[] = [];

  const flush = () => {
    if (list.length > 0) {
      blocks.push({ kind: "list", items: list });
      list = [];
    }
    if (paragraph.length > 0) {
      blocks.push({ kind: "paragraph", lines: paragraph });
      paragraph = [];
    }
  };

  for (const raw of text.split("\n")) {
    const line = stripMarkdown(raw);
    const trimmed = line.trim();

    if (trimmed === "") {
      flush();
      continue;
    }

    const bullet = BULLET.exec(line);
    if (bullet) {
      // A bullet ends a paragraph but continues a list.
      if (paragraph.length > 0) {
        blocks.push({ kind: "paragraph", lines: paragraph });
        paragraph = [];
      }
      list.push(bullet[1].trim());
      continue;
    }

    const heading = HEADING.exec(trimmed);
    if (heading) {
      flush();
      blocks.push({ kind: "heading", text: heading[1].trim() });
      continue;
    }

    if (list.length > 0) {
      blocks.push({ kind: "list", items: list });
      list = [];
    }
    paragraph.push(trimmed);
  }

  flush();
  return blocks;
}

export function StructuredText({ text }: { text: string }) {
  const blocks = parseBlocks(text);

  return (
    <div className="space-y-2.5">
      {blocks.map((block, index) => {
        if (block.kind === "heading") {
          return (
            <p
              key={index}
              // `mt-4 first:mt-0` rather than relying on the wrapper's
              // space-y: a heading needs more air above it than a paragraph
              // does, which is most of what makes a long answer skimmable.
              className="mt-4 font-semibold text-foreground first:mt-0"
            >
              {block.text}
            </p>
          );
        }

        if (block.kind === "list") {
          return (
            <ul key={index} className="list-disc space-y-1 pl-5">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="pl-0.5">
                  {item}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={index} className="whitespace-pre-line">
            {block.lines.join("\n")}
          </p>
        );
      })}
    </div>
  );
}
