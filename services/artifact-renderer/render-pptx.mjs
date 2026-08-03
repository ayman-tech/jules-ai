import fs from "node:fs"
import path from "node:path"
import pptxgen from "pptxgenjs"

const [specPath, themePath, citationsPath, destination] = process.argv.slice(2)
if (!specPath || !themePath || !citationsPath || !destination) {
  throw new Error("Usage: render-pptx.mjs <spec.json> <theme.json> <citations.json> <output.pptx>")
}

const spec = JSON.parse(fs.readFileSync(specPath, "utf8"))
const theme = JSON.parse(fs.readFileSync(themePath, "utf8"))
const citations = JSON.parse(fs.readFileSync(citationsPath, "utf8"))
const cleanHex = (value, fallback) => /^#[0-9a-f]{6}$/i.test(value ?? "") ? value.slice(1).toUpperCase() : fallback
const primary = cleanHex(theme.primary_color, "312E81")
const accent = cleanHex(theme.accent_color, "6D28D9")
const ink = "17151C"
const muted = "66616F"
const pale = "F3F0F8"
const headingFont = theme.heading_font || "Aptos Display"
const bodyFont = theme.body_font || "Aptos"

const pptx = new pptxgen()
pptx.layout = "LAYOUT_WIDE"
pptx.author = "Jules AI"
pptx.subject = spec.subtitle || spec.title
pptx.title = spec.title
pptx.company = ""
pptx.lang = "en-US"
pptx.theme = {
  headFontFace: headingFont,
  bodyFontFace: bodyFont,
  lang: "en-US",
}
pptx.defineSlideMaster({
  title: "JULES_BASE",
  background: { color: "FCFBFD" },
  objects: [
    { line: { x: 0.55, y: 7.12, w: 12.23, h: 0, line: { color: "DDD7E8", width: 1 } } },
    { text: { text: "Jules AI", options: { x: 0.62, y: 7.18, w: 5.5, h: 0.16, fontFace: bodyFont, fontSize: 8, color: muted, margin: 0 } } },
    { text: { text: "{{slideNum}}", options: { x: 12.1, y: 7.18, w: 0.6, h: 0.16, align: "right", fontFace: bodyFont, fontSize: 8, color: muted, margin: 0 } } },
  ],
  slideNumber: { x: 12.1, y: 7.16, color: muted, fontFace: bodyFont, fontSize: 8 },
})

function addTitle(slide, title, subtitle = "") {
  slide.addText(title, { x: 0.72, y: 0.55, w: 10.15, h: 0.55, fontFace: headingFont, fontSize: 35, bold: true, color: ink, margin: 0, breakLine: false, fit: "shrink" })
  slide.addShape(pptx.ShapeType.line, { x: 0.72, y: 1.23, w: 1.15, h: 0, line: { color: accent, width: 4 } })
  if (subtitle) slide.addText(subtitle, { x: 2.05, y: 1.08, w: 8.8, h: 0.28, fontFace: bodyFont, fontSize: 14, color: muted, margin: 0, fit: "shrink" })
}

function addBlock(slide, block, y, height) {
  let cursor = y
  if (block.heading) {
    slide.addText(block.heading, { x: 0.8, y: cursor, w: 11.65, h: 0.35, fontFace: headingFont, fontSize: 22, bold: true, color: primary, margin: 0, fit: "shrink" })
    cursor += 0.46
  }
  const available = Math.max(0.55, height - (cursor - y))
  if (block.kind === "table" && block.headers?.length) {
    const rows = [block.headers, ...(block.rows || [])]
    slide.addTable(rows, {
      x: 0.82, y: cursor, w: 11.55, h: available,
      border: { color: "D7D0E2", pt: 1 },
      fill: "FFFFFF", color: ink, fontFace: bodyFont, fontSize: 14,
      margin: 0.09, valign: "mid", rowH: 0.42,
      bold: false, autoFit: false,
    })
    return
  }
  if (block.kind === "callout") {
    slide.addShape(pptx.ShapeType.rect, { x: 0.82, y: cursor, w: 11.55, h: Math.min(available, 1.35), rectRadius: 0.06, fill: { color: pale }, line: { color: "D7D0E2", width: 1 } })
    slide.addText(block.text || "", { x: 1.1, y: cursor + 0.2, w: 11.0, h: Math.min(available - 0.3, 0.95), fontFace: bodyFont, fontSize: 18, bold: true, color: primary, margin: 0, fit: "shrink", valign: "mid" })
    return
  }
  if ((block.kind === "bullets" || block.kind === "numbered") && block.items?.length) {
    const lines = block.items.slice(0, 7).map((text, index) => ({
      text,
      options: block.kind === "bullets" ? { bullet: { indent: 18 }, hanging: 4, breakLine: true } : { bullet: { type: "number", startAt: index + 1, indent: 18 }, hanging: 4, breakLine: true },
    }))
    slide.addText(lines, { x: 0.9, y: cursor, w: 11.35, h: available, fontFace: bodyFont, fontSize: 20, color: ink, margin: 0.05, paraSpaceAfterPt: 12, breakLine: true, valign: "top", fit: "shrink" })
    return
  }
  slide.addText(block.text || "", { x: 0.82, y: cursor, w: 11.45, h: available, fontFace: bodyFont, fontSize: 20, color: ink, margin: 0, breakLine: false, valign: "top", fit: "shrink", paraSpaceAfterPt: 10 })
}

const titleSlide = pptx.addSlide()
titleSlide.background = { color: primary }
titleSlide.addShape(pptx.ShapeType.line, { x: 0.82, y: 1.15, w: 1.25, h: 0, line: { color: accent, width: 5 } })
titleSlide.addText(spec.title, { x: 0.82, y: 1.5, w: 10.6, h: 1.55, fontFace: headingFont, fontSize: 50, bold: true, color: "FFFFFF", margin: 0, fit: "shrink", valign: "mid" })
if (spec.subtitle) titleSlide.addText(spec.subtitle, { x: 0.84, y: 3.25, w: 9.8, h: 0.75, fontFace: bodyFont, fontSize: 24, color: "E9E1F5", margin: 0, fit: "shrink" })
titleSlide.addText(spec.audience || "", { x: 0.84, y: 6.45, w: 7.5, h: 0.28, fontFace: bodyFont, fontSize: 12, color: "D9CFEB", margin: 0 })

for (const page of spec.pages) {
  const slide = pptx.addSlide("JULES_BASE")
  addTitle(slide, page.title, page.subtitle)
  const blocks = (page.blocks || []).slice(0, 5)
  const startY = 1.65
  const totalHeight = 5.15
  const gap = 0.18
  const blockHeight = blocks.length ? (totalHeight - gap * (blocks.length - 1)) / blocks.length : totalHeight
  blocks.forEach((block, index) => addBlock(slide, block, startY + index * (blockHeight + gap), blockHeight))
  const notes = [page.speaker_notes || "", citations.length ? `[Sources]\n${citations.map((item) => `[${item.ordinal}] ${item.title}${item.location || item.url ? ` - ${item.location || item.url}` : ""}`).join("\n")}` : ""].filter(Boolean).join("\n\n")
  if (notes && typeof slide.addNotes === "function") slide.addNotes(notes)
}

if (citations.length) {
  const slide = pptx.addSlide("JULES_BASE")
  addTitle(slide, "Sources")
  const sourceText = citations.slice(0, 18).map((item) => ({ text: `[${item.ordinal}] ${item.title}${item.publisher ? ` — ${item.publisher}` : ""}\n${item.location || item.url || ""}`, options: { breakLine: true } }))
  slide.addText(sourceText, { x: 0.82, y: 1.62, w: 11.45, h: 5.25, fontFace: bodyFont, fontSize: 13, color: ink, margin: 0, paraSpaceAfterPt: 7, fit: "shrink", valign: "top" })
  if (typeof slide.addNotes === "function") slide.addNotes(`[Sources]\n${citations.map((item) => `[${item.ordinal}] ${item.title} - ${item.location || item.url || ""}`).join("\n")}`)
}

fs.mkdirSync(path.dirname(destination), { recursive: true })
await pptx.writeFile({ fileName: destination })
