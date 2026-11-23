/*
 * Conversor Markdown -> Word (ABNT) do relatório acadêmico.
 *
 * Uso (a partir de qualquer pasta):
 *   NODE_PATH=<pasta com node_modules/docx> node reports/relatorio/gerar_docx.js [entrada.md] [saida.docx]
 * Padrões: relatorio.md -> relatorio.docx, na mesma pasta deste script.
 *
 * O texto vem só do .md (nada é reescrito). Este script apenas formata:
 *  - A4; margens 3 cm (sup., esq.) e 2 cm (inf., dir.); Times New Roman 12; justificado;
 *    espaçamento 1,5; recuo de 1,25 cm na primeira linha.
 *  - Legendas, fontes, notas, tabelas e referências em fonte 10 e espaçamento simples.
 *  - Pré-textuais (capa, folha de rosto, resumo, abstract, sumário) sem número de página;
 *    a numeração (canto superior direito) começa na introdução, contando as pré-textuais.
 *  - Sumário como campo TOC do Word (atualiza ao abrir).
 *  - Marcadores [PREENCHER ...] e [VERIFY ...] com realce amarelo.
 *  - Comentários HTML do .md (inclusive o bloco de mensagens-chave) não entram no Word.
 */
const fs = require("fs");
const path = require("path");
const D = require("docx");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, Header,
  AlignmentType, HeadingLevel, LevelFormat, BorderStyle, WidthType, ShadingType,
  PageNumber, TableOfContents, ExternalHyperlink, LineRuleType,
} = D;

const MD = path.resolve(process.argv[2] || path.join(__dirname, "relatorio.md"));
const OUT = path.resolve(process.argv[3] || path.join(__dirname, "relatorio.docx"));
const BASE_DIR = path.dirname(MD);

const FONT = "Times New Roman";
const MONO = "Courier New";
const CONTENT_W = 9071; // 16 cm em DXA (21 - 3 - 2 cm)
const INDENT = 709; // 1,25 cm
const L15 = 360; // espaçamento 1,5
const L10 = 240; // espaçamento simples
const NO = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

// ---------------------------------------------------------------- inline
const INLINE_SRC = (
  [
    "\\*\\*(.+?)\\*\\*", // 1 negrito
    "\\*([^*]+?)\\*", // 2 itálico
    "`([^`]+)`", // 3 código
    "\\[([^\\]]+)\\]\\(([^)]+)\\)", // 4,5 link
    "(\\[(?:PREENCHER|VERIFY)[^\\]]*\\])", // 6 marcador
    "(https?:\\/\\/[^\\s]+)", // 7 URL solta
  ].join("|")
);
const MARK_RE = /^\[(PREENCHER|VERIFY)/;

function run(text, p) {
  const o = { text, font: p.font || FONT };
  if (p.size) o.size = p.size;
  if (p.bold) o.bold = true;
  if (p.italics) o.italics = true;
  if (p.highlight) o.highlight = p.highlight;
  return new TextRun(o);
}

function inline(text, p = {}) {
  const out = [];
  let last = 0;
  const INLINE_RE = new RegExp(INLINE_SRC, "g"); // por chamada: a função é recursiva
  let m;
  while ((m = INLINE_RE.exec(text))) {
    if (m.index > last) out.push(run(text.slice(last, m.index), p));
    if (m[1] !== undefined) out.push(...inline(m[1], { ...p, bold: true }));
    else if (m[2] !== undefined) out.push(...inline(m[2], { ...p, italics: true }));
    else if (m[3] !== undefined) {
      if (MARK_RE.test(m[3])) out.push(run(m[3], { ...p, highlight: "yellow" }));
      else out.push(run(m[3], { ...p, font: MONO, size: (p.size || 24) === 24 ? 20 : 18 }));
    } else if (m[4] !== undefined) {
      out.push(
        new ExternalHyperlink({
          link: m[5],
          children: [new TextRun({ text: m[4], font: FONT, size: p.size, style: "Hyperlink", bold: p.bold, italics: p.italics })],
        })
      );
    } else if (m[6] !== undefined) out.push(run(m[6], { ...p, highlight: "yellow" }));
    else if (m[7] !== undefined) {
      let url = m[7];
      let tail = "";
      const t = url.match(/[.,;:)]+$/);
      if (t) {
        tail = t[0];
        url = url.slice(0, -tail.length);
      }
      out.push(
        new ExternalHyperlink({
          link: url,
          children: [new TextRun({ text: url, font: FONT, size: p.size, style: "Hyperlink", bold: p.bold, italics: p.italics })],
        })
      );
      if (tail) out.push(run(tail, p));
    }
    last = INLINE_RE.lastIndex;
  }
  if (last < text.length) out.push(run(text.slice(last), p));
  return out;
}

const plain = (s) => s.replace(/\*\*|`/g, "").replace(/\*([^*]+)\*/g, "$1").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");

// ---------------------------------------------------------------- parse
let src = fs.readFileSync(MD, "utf8").replace(/\r\n/g, "\n");
src = src.replace(/<!--[\s\S]*?-->/g, ""); // comentários HTML (inclui mensagens-chave dos slides)
const lines = src.split("\n");

const blocks = [];
for (let i = 0; i < lines.length; i++) {
  const ln = lines[i].replace(/\s+$/, "");
  if (!ln.trim()) continue;
  if (/^---+$/.test(ln.trim())) continue;
  let m;
  if ((m = ln.match(/^(#{1,3}) (.*)$/))) {
    blocks.push({ t: "h" + m[1].length, text: m[2].trim() });
  } else if (ln.startsWith("> ")) {
    blocks.push({ t: "quote", text: ln.slice(2).trim() });
  } else if (/^- /.test(ln)) {
    blocks.push({ t: "ul", text: ln.slice(2).trim() });
  } else if ((m = ln.match(/^\d+\. (.*)$/))) {
    blocks.push({ t: "ol", text: m[1].trim() });
  } else if (ln.startsWith("|")) {
    const rows = [];
    while (i < lines.length && lines[i].trim().startsWith("|")) {
      rows.push(lines[i].trim());
      i++;
    }
    i--;
    const cells = (r) => r.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
    const header = cells(rows[0]);
    const aligns = cells(rows[1]).map((c) => (/:$/.test(c) ? "right" : /^:.*:$/.test(c) ? "center" : "left"));
    blocks.push({ t: "table", header, aligns, rows: rows.slice(2).map(cells) });
  } else if ((m = ln.match(/^!\[([^\]]*)\]\(([^)]+)\)$/))) {
    blocks.push({ t: "figure", alt: m[1], file: m[2] });
  } else if (ln.startsWith("```")) {
    const code = [];
    i++;
    while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
    blocks.push({ t: "code", lines: code });
  } else {
    blocks.push({ t: "p", text: ln.trim() });
  }
}

// ---------------------------------------------------------------- estilos
const styles = {
  default: {
    document: { run: { font: FONT, size: 24, language: { value: "pt-BR" } } },
    heading1: {
      run: { font: FONT, size: 24, bold: true, allCaps: true },
      paragraph: { spacing: { before: 0, after: 360, line: L15 }, keepNext: true, keepLines: true },
    },
    heading2: {
      run: { font: FONT, size: 24, bold: true },
      paragraph: { spacing: { before: 360, after: 240, line: L15 }, keepNext: true, keepLines: true },
    },
    heading3: {
      run: { font: FONT, size: 24, bold: true, italics: true },
      paragraph: { spacing: { before: 240, after: 240, line: L15 }, keepNext: true, keepLines: true },
    },
  },
  paragraphStyles: [
    {
      id: "Corpo", name: "Corpo ABNT", basedOn: "Normal", quickFormat: true,
      run: { font: FONT, size: 24 },
      paragraph: { alignment: AlignmentType.JUSTIFIED, spacing: { line: L15, before: 0, after: 0 }, indent: { firstLine: INDENT } },
    },
    {
      id: "Destaque", name: "Destaque ABNT", basedOn: "Normal",
      run: { font: FONT, size: 24 },
      paragraph: {
        alignment: AlignmentType.JUSTIFIED, spacing: { line: L15, before: 120, after: 120 },
        indent: { left: INDENT, right: 0 },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: "A6A6A6", space: 8 } },
      },
    },
    {
      id: "Legenda", name: "Legenda ABNT", basedOn: "Normal",
      run: { font: FONT, size: 20 },
      paragraph: { alignment: AlignmentType.LEFT, spacing: { line: L10, before: 240, after: 120 }, keepNext: true, keepLines: true },
    },
    {
      id: "Fonte", name: "Fonte ABNT", basedOn: "Normal",
      run: { font: FONT, size: 20 },
      paragraph: { alignment: AlignmentType.LEFT, spacing: { line: L10, before: 80, after: 240 } },
    },
    {
      id: "Referencia", name: "Referencia ABNT", basedOn: "Normal",
      run: { font: FONT, size: 20 },
      paragraph: { alignment: AlignmentType.LEFT, spacing: { line: L10, before: 0, after: 240 } },
    },
    {
      id: "TabelaTexto", name: "Tabela ABNT", basedOn: "Normal",
      run: { font: FONT, size: 20 },
      paragraph: { spacing: { line: L10, before: 0, after: 0 } },
    },
    {
      id: "PreTitulo", name: "Titulo pre-textual", basedOn: "Normal",
      run: { font: FONT, size: 24, bold: true },
      paragraph: { alignment: AlignmentType.CENTER, spacing: { line: L15, before: 0, after: 360 }, keepNext: true },
    },
    {
      id: "Resumo", name: "Resumo ABNT", basedOn: "Normal",
      run: { font: FONT, size: 24 },
      paragraph: { alignment: AlignmentType.JUSTIFIED, spacing: { line: L10, before: 0, after: 0 } },
    },
    {
      id: "Codigo", name: "Codigo ABNT", basedOn: "Normal",
      run: { font: MONO, size: 20 },
      paragraph: { spacing: { line: L10, before: 0, after: 0 }, indent: { left: INDENT } },
    },
    {
      id: "TOC1", name: "toc 1", basedOn: "Normal", next: "Normal",
      run: { font: FONT, size: 24, bold: true },
      paragraph: { spacing: { line: L10, before: 120, after: 60 } },
    },
    {
      id: "TOC2", name: "toc 2", basedOn: "Normal", next: "Normal",
      run: { font: FONT, size: 24 },
      paragraph: { spacing: { line: L10, before: 0, after: 60 }, indent: { left: 284 } },
    },
    {
      id: "TOC3", name: "toc 3", basedOn: "Normal", next: "Normal",
      run: { font: FONT, size: 24 },
      paragraph: { spacing: { line: L10, before: 0, after: 60 }, indent: { left: 568 } },
    },
  ],
  characterStyles: [
    { id: "Hyperlink", name: "Hyperlink", basedOn: "DefaultParagraphFont", run: { color: "0000FF", underline: { type: "single" } } },
  ],
};

const numbering = { config: [] };
numbering.config.push({
  reference: "bullets",
  levels: [{
    level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 1069, hanging: 360 } } },
  }],
});
numbering.config.push({
  reference: "numeros",
  levels: [{
    level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 1069, hanging: 360 } } },
  }],
});

// ---------------------------------------------------------------- construtores
const P = (opts) => new Paragraph(opts);
const body = (text, extra = {}) => P({ style: "Corpo", children: inline(text), ...extra });
const small = { size: 20 };

function listItem(b, kind, inst) {
  return P({
    style: "Corpo",
    indent: { left: 1069, hanging: 360, firstLine: undefined },
    numbering: { reference: kind === "ul" ? "bullets" : "numeros", level: 0, instance: inst },
    children: inline(b.text),
  });
}

function buildTable(b, boxed) {
  const n = b.header.length;
  const all = [b.header, ...b.rows];
  const weights = [];
  for (let c = 0; c < n; c++) {
    const vals = all.map((r) => plain(r[c] || ""));
    const maxLen = Math.max(...vals.map((v) => v.length));
    const avg = vals.reduce((s, v) => s + v.length, 0) / vals.length;
    const lw = Math.max(...vals.map((v) => Math.max(0, ...v.split(/\s+/).map((w) => w.length))));
    weights.push(Math.max(lw + 2, Math.min(maxLen, 34) * 0.8, 5));
  }
  const sum = weights.reduce((a, c) => a + c, 0);
  let widths = weights.map((w) => Math.max(750, Math.floor((w / sum) * CONTENT_W)));
  const diff = CONTENT_W - widths.reduce((a, c) => a + c, 0);
  widths[widths.indexOf(Math.max(...widths))] += diff;

  const line = (sz) => ({ style: BorderStyle.SINGLE, size: sz, color: "000000" });
  const keepTogether = all.length <= 12; // tabelas curtas não se partem entre páginas
  const mkRow = (cells, ri, isHeader) => {
    const last = ri === all.length - 1;
    return new TableRow({
      tableHeader: isHeader,
      cantSplit: true,
      children: cells.map((txt, c) => {
        const borders = boxed
          ? { top: line(4), bottom: line(4), left: line(4), right: line(4) }
          : {
              top: ri === 0 ? line(8) : NO,
              bottom: isHeader ? line(6) : last ? line(8) : NO,
              left: NO,
              right: NO,
            };
        return new TableCell({
          width: { size: widths[c], type: WidthType.DXA },
          borders,
          margins: { top: 40, bottom: 40, left: 80, right: 80 },
          shading: boxed && isHeader ? { type: ShadingType.CLEAR, fill: "EDEDED", color: "auto" } : undefined,
          children: [
            P({
              style: "TabelaTexto",
              keepNext: keepTogether && ri < all.length - 1,
              alignment: b.aligns[c] === "right" ? AlignmentType.RIGHT : b.aligns[c] === "center" ? AlignmentType.CENTER : AlignmentType.LEFT,
              children: inline(txt || "", { size: 20, bold: isHeader || undefined }),
            }),
          ],
        });
      }),
    });
  };
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    alignment: AlignmentType.CENTER,
    borders: { top: NO, bottom: NO, left: NO, right: NO, insideHorizontal: NO, insideVertical: NO },
    rows: all.map((r, ri) => mkRow(r, ri, ri === 0)),
  });
}

function pngSize(file) {
  const buf = fs.readFileSync(file);
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

function buildFigure(b, capText) {
  const file = path.resolve(BASE_DIR, b.file);
  const { w, h } = pngSize(file);
  const maxW = 604; // 16 cm a 96 dpi
  const maxH = 430; // ~11,4 cm, para caber título + imagem + fonte na página
  let scale = Math.min(maxW / w, maxH / h, 1.0);
  if (w * scale < 300) scale = Math.min(maxW / w, maxH / h);
  const out = [];
  const m = capText.match(/^\*\*(.+?)\*\*\s*(.*)$/s);
  const title = m ? m[1] : capText;
  const rest = m ? m[2] : "";
  const iF = rest.indexOf("Fonte:");
  const desc = (iF >= 0 ? rest.slice(0, iF) : rest).trim();
  const fonte = iF >= 0 ? rest.slice(iF).trim() : "";
  out.push(P({ style: "Legenda", children: inline(title, { size: 20, bold: true }) }));
  out.push(
    P({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { line: L10, before: 0, after: 80 },
      children: [
        new ImageRun({
          type: "png",
          data: fs.readFileSync(file),
          transformation: { width: Math.round(w * scale), height: Math.round(h * scale) },
          altText: { title: title, description: b.alt + ": " + title, name: b.file },
        }),
      ],
    })
  );
  if (desc) out.push(P({ style: "Fonte", keepNext: !!fonte, spacing: { line: L10, before: 40, after: fonte ? 0 : 240 }, children: inline(desc, small) }));
  if (fonte) out.push(P({ style: "Fonte", spacing: { line: L10, before: 40, after: 240 }, children: inline(fonte, small) }));
  return out;
}

// ---------------------------------------------------------------- pré-textuais
const pre = {};
let idx = 0;
// bloco inicial "ELEMENTOS PRÉ-TEXTUAIS"
if (blocks[0].t === "h1") idx = 1;
let cur = null;
while (idx < blocks.length && !(blocks[idx].t === "h1")) {
  const b = blocks[idx];
  if (b.t === "h2") {
    cur = b.text;
    pre[cur] = [];
  } else if (cur) pre[cur].push(b);
  idx++;
}

const C = (text, extra = {}) => P({ alignment: AlignmentType.CENTER, spacing: { line: L15, before: 0, after: 0 }, ...extra, children: inline(text, extra.run || {}) });

function capa() {
  const it = pre["Capa"];
  const [inst, curso, autor, titulo, cidade, ano] = it.map((b) => b.text);
  return [
    C(inst), C(curso), C(autor),
    C(titulo, { spacing: { line: L15, before: 3800, after: 0 } }),
    C(cidade, { spacing: { line: L15, before: 7300, after: 0 } }),
    C(ano),
  ];
}

function folhaRosto() {
  const it = pre["Folha de rosto"];
  const [autor, titulo, natureza, prof, cidade, ano] = it.map((b) => b.text);
  const nat = (t, before) =>
    P({
      alignment: AlignmentType.JUSTIFIED, indent: { left: 4536 }, spacing: { line: L10, before, after: 0 },
      children: inline(t, { size: 20 }),
    });
  return [
    C(autor, { pageBreakBefore: true }),
    C(titulo, { spacing: { line: L15, before: 3200, after: 0 } }),
    nat(natureza, 2400),
    nat(prof, 240),
    C(cidade, { spacing: { line: L15, before: 5000, after: 0 } }),
    C(ano),
  ];
}

function resumoSec(name, title) {
  const it = pre[name];
  const out = [P({ style: "PreTitulo", pageBreakBefore: true, children: [new TextRun({ text: title, bold: true, font: FONT })] })];
  it.forEach((b, i) => {
    out.push(P({ style: "Resumo", spacing: { line: L10, before: i === 0 ? 0 : 360, after: 0 }, children: inline(b.text) }));
  });
  return out;
}

const preChildren = [
  ...capa(),
  ...folhaRosto(),
  ...resumoSec("Resumo", "RESUMO"),
  ...resumoSec("Abstract", "ABSTRACT"),
  P({ style: "PreTitulo", pageBreakBefore: true, children: [new TextRun({ text: "SUMÁRIO", bold: true, font: FONT })] }),
  new TableOfContents("Sumário", { hyperlink: true, headingStyleRange: "1-3" }),
];

// ---------------------------------------------------------------- corpo
const main = [];
let firstH1 = true;
let olInst = 0;
let inReferencias = false;
let inQuadro = false;
for (; idx < blocks.length; idx++) {
  const b = blocks[idx];
  switch (b.t) {
    case "h1": {
      const numbered = /^\d/.test(b.text);
      main.push(
        P({
          heading: HeadingLevel.HEADING_1,
          alignment: numbered ? AlignmentType.LEFT : AlignmentType.CENTER,
          pageBreakBefore: !firstH1,
          children: [new TextRun({ text: b.text, font: FONT })],
        })
      );
      firstH1 = false;
      break;
    }
    case "h2":
      main.push(P({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: b.text, font: FONT })] }));
      break;
    case "h3":
      main.push(P({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: b.text, font: FONT })] }));
      break;
    case "quote": {
      const isFrase = /^\*\*Em uma frase:\*\*/.test(b.text);
      main.push(P({ style: "Destaque", children: inline(b.text, isFrase ? { italics: true } : {}) }));
      break;
    }
    case "ul":
      main.push(listItem(b, "ul", 0));
      break;
    case "ol": {
      if (blocks[idx - 1] && blocks[idx - 1].t !== "ol") olInst++;
      main.push(listItem(b, "ol", olInst));
      break;
    }
    case "table": {
      main.push(buildTable(b, inQuadro));
      break;
    }
    case "figure": {
      // legenda correspondente: próximo bloco "p" que começa com **Figura
      const nxt = blocks[idx + 1];
      if (!nxt || nxt.t !== "p" || !/^\*\*Figura/.test(nxt.text)) throw new Error("Figura sem legenda: " + b.file);
      main.push(...buildFigure(b, nxt.text));
      idx++;
      break;
    }
    case "code":
      b.lines.forEach((l) => main.push(P({ style: "Codigo", children: [new TextRun({ text: l, font: MONO, size: 20 })] })));
      break;
    case "p": {
      if (/^\*\*(Tabela|Quadro) /.test(b.text)) {
        main.push(P({ style: "Legenda", children: inline(b.text, { size: 20 }) }));
      } else if (/^Fonte:/.test(b.text)) {
        main.push(P({ style: "Fonte", children: inline(b.text, small) }));
      } else if (inReferencias) {
        main.push(P({ style: "Referencia", children: inline(b.text, small) }));
      } else {
        main.push(body(b.text));
      }
      break;
    }
  }
  if (b.t === "h1") {
    inReferencias = /^REFERÊNCIAS$/.test(b.text);
    inQuadro = /^QUADRO /.test(b.text);
  }
}

// ---------------------------------------------------------------- documento
const pageSize = { width: 11906, height: 16838 };
const margin = { top: 1701, left: 1701, bottom: 1134, right: 1134, header: 709, footer: 709 };

const doc = new Document({
  creator: "",
  title: "Risco de dengue grave ou óbito por perfil de comorbidades",
  description: "Relatório acadêmico (ABNT) gerado de relatorio.md por gerar_docx.js",
  features: { updateFields: true },
  styles,
  numbering,
  sections: [
    { properties: { page: { size: pageSize, margin } }, children: preChildren },
    {
      properties: { page: { size: pageSize, margin } },
      headers: {
        default: new Header({
          children: [
            P({
              alignment: AlignmentType.RIGHT,
              children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })],
            }),
          ],
        }),
      },
      children: main,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("OK", OUT, buf.length, "bytes;", blocks.length, "blocos");
});
