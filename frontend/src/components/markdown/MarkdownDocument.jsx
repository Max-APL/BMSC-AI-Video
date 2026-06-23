import React from "react";
import { parseMarkdown, renderInlineMarkdown, resolveManualImageUrl } from "@/utils/markdown.jsx";

export function MarkdownDocument({ content, assetBaseUrl = "" }) {
  const blocks = React.useMemo(() => parseMarkdown(content || ""), [content]);

  if (!content) {
    return (
      <div className="manual-document empty-document">
        <p>El contenido aparecerá aquí mientras se genera el manual.</p>
      </div>
    );
  }

  return (
    <div className="manual-document">
      {blocks.map((block, index) => {
        if (block.type === "h1")
          return <h1 key={index}>{renderInlineMarkdown(block.text)}</h1>;
        if (block.type === "h2")
          return <h2 key={index}>{renderInlineMarkdown(block.text)}</h2>;
        if (block.type === "h3")
          return <h3 key={index}>{renderInlineMarkdown(block.text)}</h3>;
        if (block.type === "h4")
          return <h4 key={index}>{renderInlineMarkdown(block.text)}</h4>;
        if (block.type === "image") {
          const src = resolveManualImageUrl(assetBaseUrl, block.src);
          if (!src) return null;
          return (
            <figure className="manual-figure" key={index}>
              <img src={src} alt={block.alt || "Captura del manual"} loading="lazy" />
              {block.alt && <figcaption>{block.alt}</figcaption>}
            </figure>
          );
        }
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, i) => (
                <li key={i}>{renderInlineMarkdown(item)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={index} start={block.start || 1}>
              {block.items.map((item, i) => (
                <li key={i}>{renderInlineMarkdown(item)}</li>
              ))}
            </ol>
          );
        }
        return <p key={index}>{renderInlineMarkdown(block.text)}</p>;
      })}
    </div>
  );
}
