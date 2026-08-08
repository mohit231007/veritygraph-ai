import type { SourceBundle, SourceSpan } from "../types";

function spanLocation(span: SourceSpan) {
  const parts: string[] = [];
  if (span.page_number) parts.push(`Page ${span.page_number}`);
  if (span.section) parts.push(span.section);
  if (span.paragraph_number) parts.push(`Paragraph ${span.paragraph_number}`);
  return parts.length > 0 ? parts.join(" · ") : "Evidence span";
}

type Props = {
  bundle: SourceBundle;
};

export default function SourcePreview({ bundle }: Props) {
  const sourceLabel = bundle.document.filename ?? bundle.document.title;

  return (
    <section className="source-preview" data-testid="source-preview" aria-labelledby="preview-heading">
      <div className="preview-header">
        <div>
          <p className="section-label">CANONICAL SOURCE PROVENANCE</p>
          <h2 id="preview-heading">{sourceLabel}</h2>
          {bundle.document.url && (
            <a className="source-link" href={bundle.document.url} target="_blank" rel="noreferrer">
              Open original public source ↗
            </a>
          )}
        </div>
        <div className="source-badges">
          <span>{bundle.document.source_type.replaceAll("_", " ")}</span>
          <span>{bundle.document.source_format.toUpperCase()}</span>
          <span>{bundle.spans.length} spans</span>
        </div>
      </div>

      <div className="source-meta">
        <div>
          <span>Source ID</span>
          <code>{bundle.document.source_id}</code>
        </div>
        <div>
          <span>SHA-256</span>
          <code>{bundle.document.content_hash.slice(0, 20)}…</code>
        </div>
      </div>

      <div className="span-list">
        {bundle.spans.slice(0, 16).map((span) => (
          <article className="span-row" key={span.span_id}>
            <div>
              <span className="span-location">{spanLocation(span)}</span>
              <span className="span-offset">chars {span.char_start}–{span.char_end}</span>
            </div>
            <p>{span.text}</p>
          </article>
        ))}
      </div>

      {bundle.spans.length > 16 && (
        <p className="preview-note">Showing the first 16 of {bundle.spans.length} spans.</p>
      )}
    </section>
  );
}
