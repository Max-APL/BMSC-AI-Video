import React from "react";

export function parseMarkdown(content) {
  const blocks = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "p", text: paragraph.join(" ").trim() });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push(list);
      list = null;
    }
  };

  const lines = content.split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const line = rawLine.trim();
    const nextLine = (lines[index + 1] || "").trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    if (/^(={3,}|-{3,})$/.test(nextLine)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h2", text: line.replace(/^#+\s*/, "").trim() });
      index += 1;
      continue;
    }
    const imageMatch = line.match(/^!\[(.*?)\]\((.*?)\)$/);
    if (imageMatch) {
      flushParagraph();
      flushList();
      blocks.push({ type: "image", alt: imageMatch[1].trim(), src: imageMatch[2].trim() });
      continue;
    }
    if (line.startsWith("# ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h1", text: line.slice(2).trim() });
      continue;
    }
    if (line.startsWith("## ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h2", text: line.slice(3).trim() });
      continue;
    }
    if (line.startsWith("### ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h3", text: line.slice(4).trim() });
      continue;
    }
    if (line.startsWith("#### ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h4", text: line.slice(5).trim() });
      continue;
    }
    if (line.startsWith("- ") || line.startsWith("* ") || line.startsWith("+ ")) {
      flushParagraph();
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(line.slice(2).trim());
      continue;
    }
    const numberMatch = line.match(/^(\d+)\.\s+/);
    if (numberMatch) {
      flushParagraph();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", start: Number(numberMatch[1]) || 1, items: [] };
      }
      list.items.push(line.replace(/^\d+\.\s+/, "").trim());
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return blocks;
}

export function resolveManualImageUrl(assetBaseUrl, src) {
  if (!assetBaseUrl || !src) return "";
  if (/^https?:\/\//i.test(src)) return src;
  const cleaned = String(src)
    .replace(/^\/+/, "")
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  return `${assetBaseUrl.replace(/\/$/, "")}/${cleaned}`;
}

export function renderInlineMarkdown(text) {
  const parts = String(text).split(/(\*\*.+?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}
