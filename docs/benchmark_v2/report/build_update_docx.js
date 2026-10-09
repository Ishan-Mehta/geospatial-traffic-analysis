// Builds the 1–2 page professor update (A4, Google-Docs-friendly .docx).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, ShadingType, LevelFormat, HeadingLevel, VerticalAlign, Footer, TableLayoutType,
} = require("docx");

const OUT = process.argv[2];
const FIG = process.argv[3];
const FONT = "Arial";
const INK = "1F1F1F", MUTED = "5F5E5A", ACCENT = "2A78D6", RULE = "D9D8D3", SOFT = "F3F2EE";
const W = 9638;                       // A4 width 11906 − 2×1134 (2 cm margins), in DXA

const t = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || 20, bold: o.bold, italics: o.italics,
  color: o.color || INK });
const p = (runs, o = {}) => new Paragraph({ children: Array.isArray(runs) ? runs : [runs],
  spacing: { before: o.before ?? 0, after: o.after ?? 80, line: o.line || 264 }, alignment: o.align,
  keepNext: o.keepNext, ...(o.border ? { border: o.border } : {}) });
const h = (text) => p([t(text, { bold: true, size: 24, color: ACCENT })], { before: 160, after: 60, keepNext: true });
const bullet = (runs, level = 0) => new Paragraph({ children: runs, numbering: { reference: "bul", level },
  spacing: { after: 50, line: 259 } });
const num = (runs) => new Paragraph({ children: runs, numbering: { reference: "num", level: 0 },
  spacing: { after: 60, line: 259 } });
const img = (file, wPx, hPx) => new ImageRun({ type: "png", data: fs.readFileSync(path.join(FIG, file)),
  transformation: { width: wPx, height: hPx },
  altText: { title: file, description: file, name: file } });
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };
const tableNoBorders = { ...noBorders, insideHorizontal: noBorder, insideVertical: noBorder };
const thin = { style: BorderStyle.SINGLE, size: 4, color: RULE };

// ---------- page 1: title, question, what we did + map ----------
const title = [
  p([t("Benchmarking LLMs against Navigation Tools", { bold: true, size: 36 })], { after: 40 }),
  p([t("Progress update · October 2026", { size: 22, color: MUTED })], { after: 40 }),
  p([t("Ishan Mehta", { bold: true, size: 20 }), t("   ·   Supervisor: Prof. Vinayak Naik", { size: 20, color: MUTED })],
    { after: 120, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } } }),
];

const question = [
  h("The question"),
  p([t("If you ask an AI model how long a drive across Bangalore will take — without giving it a map — how close does " +
       "it get to Google Maps? This update covers the first full round of that comparison.")]),
];

const LEFT = 5900, RIGHT = W - LEFT;
const whatWeDid = [
  h("What we did"),
  new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: [LEFT, RIGHT], borders: tableNoBorders, layout: TableLayoutType.FIXED,
    rows: [new TableRow({ children: [
      new TableCell({ width: { size: LEFT, type: WidthType.DXA }, borders: noBorders,
        margins: { top: 0, bottom: 0, left: 0, right: 200 }, children: [
          bullet([t("Picked "), t("72 trips", { bold: true }), t(" between 64 well-known Bangalore places (metro stations, " +
            "junctions, hospitals, tech parks…), 1–29 km long and spread across the city (Figure 1).")]),
          bullet([t("Asked "), t("Google Maps", { bold: true }), t(" for the driving time of every trip at 8 am, 2 pm, 6 pm and " +
            "11 pm on each day of one week — "), t("2,016 answers", { bold: true }), t(" (Google’s predicted traffic, 5–11 Oct 2026).")]),
          bullet([t("Asked "), t("Gemini", { bold: true }), t(" (gemini-3.8-flash) the same 2,016 questions using only the place " +
            "names, day and time — no map, no internet. It replied with a route, distance, time and traffic level.")]),
          bullet([t("Compared the two answers trip by trip. Total cost: "), t("under $2", { bold: true }), t(" (≈ ₹160).")]),
          bullet([t("An earlier pilot used tiny road segments with vague names; we redesigned it before this round.",
            { color: MUTED })]),
        ] }),
      new TableCell({ width: { size: RIGHT, type: WidthType.DXA }, borders: noBorders, verticalAlign: VerticalAlign.TOP,
        margins: { top: 0, bottom: 0, left: 0, right: 0 }, children: [
          p([img("fig_A_routes_map.png", 232, 233)], { align: AlignmentType.CENTER, after: 20 }),
          p([t("Figure 1. The 72 test routes (Google’s paths) between the landmarks.", { size: 16, color: MUTED,
            italics: true })], { align: AlignmentType.CENTER }),
        ] }),
    ] })],
  }),
];

// ---------- findings ----------
const findings = [
  h("What we found"),
  num([t("It knows Bangalore’s places and roads. ", { bold: true }), t("All 64 landmarks were placed correctly (typically " +
    "~250 m off), and about 95% of the roads it names are real.")]),
  num([t("Distances are close. ", { bold: true }), t("Gemini’s distances are typically only ~6% longer than Google’s.")]),
  num([t("Travel time is where it goes wrong. ", { bold: true }), t("On weekdays it overestimates rush hour (+49% at 8 am, " +
    "+36% at 6 pm) and underestimates night trips (−12%) — see Figure 2.")]),
  num([t("It knows when traffic is bad, but exaggerates it. ", { bold: true }), t("It roughly doubles every trip at rush " +
    "hour, while Google says about 1.3×. And it applies the same multiplier to every route — a city-wide rule of thumb, " +
    "not knowledge of specific roads.")]),
  num([t("It doesn’t know the exact route. ", { bold: true }), t("Only about 1 in 5 roads on Google’s route appear in " +
    "Gemini’s answer. Short trips (1–5 km) are the hardest.")]),
  num([t("A simple formula does about as well. ", { bold: true }), t("Straight-line distance × typical speed for that time " +
    "of day is about as accurate as Gemini.")]),
  p([img("fig_B_time_by_slot.png", 470, 277)], { align: AlignmentType.CENTER, before: 80, after: 20 }),
  p([t("Figure 2. Typical weekday trip time at each time of day. Gemini is too slow at rush hour and too fast at night.",
    { size: 16, color: MUTED, italics: true })], { align: AlignmentType.CENTER, after: 120 }),
];

// ---------- key numbers table ----------
const rows = [
  ["Trips compared", "2,016  (72 routes × 7 days × 4 times of day)"],
  ["Landmarks placed correctly", "64 of 64"],
  ["Road names that are real roads", "about 95%"],
  ["Distance vs Google", "typically +6%"],
  ["Travel time vs Google", "typically +12% overall; weekdays +49% at 8 am, −12% at 11 pm"],
  ["Rush-hour slowdown (peak ÷ night)", "Gemini 2.2×   ·   Google 1.3×"],
  ["Google’s roads that Gemini names", "about 22%"],
  ["Same question asked 3 times", "answers vary by only 3–4%"],
  ["Cost of the whole round", "$1.83  (≈ ₹160)"],
];
const C1 = 3600, C2 = W - C1;
const cell = (text, w, o = {}) => new TableCell({ width: { size: w, type: WidthType.DXA },
  borders: { top: thin, bottom: thin, left: noBorder, right: noBorder },
  shading: o.fill ? { type: ShadingType.CLEAR, color: "auto", fill: o.fill } : undefined,
  margins: { top: 50, bottom: 50, left: 100, right: 100 },
  children: [p([t(text, { bold: o.bold, size: 19, color: o.color })], { after: 0 })] });
const keyTable = [
  new Paragraph({ pageBreakBefore: true, keepNext: true, spacing: { before: 0, after: 60 },
    children: [t("Key numbers at a glance", { bold: true, size: 24, color: ACCENT })] }),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [C1, C2], layout: TableLayoutType.FIXED,
    borders: { top: thin, bottom: thin, left: noBorder, right: noBorder, insideHorizontal: thin, insideVertical: noBorder }, rows:
    rows.map((r, i) => new TableRow({ cantSplit: true, children: [
      cell(r[0], C1, { bold: true, fill: i % 2 ? undefined : SOFT }), cell(r[1], C2, { fill: i % 2 ? undefined : SOFT })] })) }),
];

// ---------- meaning + next steps ----------
const closing = [
  h("In short"),
  p([t("Gemini has a good general picture of Bangalore — places, main roads, rough distances — but its sense of traffic is " +
       "a stereotype (“rush hour doubles everything”) rather than real knowledge of specific roads and hours. This fits our " +
       "midsem expectation that LLMs would be weak at estimating time, and partly that they know main roads better than smaller ones.")]),
  h("Next steps (to discuss)"),
  bullet([t("Let Gemini “think” more before answering — does reasoning reduce the rush-hour exaggeration?")]),
  bullet([t("Give it extra context (road lists, typical speeds) — the core question from the midsem plan.")]),
  bullet([t("Compare with ChatGPT once the model is available, and add more trips on smaller roads.")]),
  bullet([t("For your OK: we added the clock time to the prompt’s time line (e.g. “Evening Rush (18:00)”), and we would " +
    "like to know whether the GitHub repository can stay public.")]),
  p([t("Notes: Google’s answers are its predicted traffic for one week; one AI model tested so far. Full details, methods " +
       "and all plots: project repository, branch benchmark-v2, folder docs/benchmark_v2.", { size: 16, color: MUTED,
       italics: true })], { before: 120 }),
];

const doc = new Document({
  creator: "Ishan Mehta", title: "Benchmarking LLMs against Navigation Tools — progress update",
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1020, bottom: 1020, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [p([t("Benchmarking LLMs against Navigation Tools · Ishan Mehta · October 2026",
      { size: 14, color: MUTED })], { align: AlignmentType.RIGHT, after: 0 })] }) },
    children: process.argv[4] === "page2" ? [...keyTable.slice(1), ...closing] : [...title, ...question, ...whatWeDid, ...findings, ...keyTable, ...closing],
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("written", OUT, buf.length, "bytes"); });
