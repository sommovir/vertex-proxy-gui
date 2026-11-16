// Funzioni di supporto condivise.

export const $ = (sel, el = document) => el.querySelector(sel);

export async function api(url, opzioni = {}) {
  const init = { ...opzioni };
  if (init.json !== undefined) {
    init.body = JSON.stringify(init.json);
    init.headers = { "Content-Type": "application/json" };
    delete init.json;
  }
  const r = await fetch(url, init);
  const corpo = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(corpo?.detail || corpo || `Errore ${r.status}`);
  return corpo;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let timerToast;
export function toast(testo) {
  const t = $("#toast");
  t.textContent = testo;
  t.hidden = false;
  clearTimeout(timerToast);
  timerToast = setTimeout(() => (t.hidden = true), 3500);
}

// Markdown essenziale: titoli, liste, codice, grassetto, corsivo, link, citazioni.
export function markdown(src) {
  const blocchi = [];
  let testo = String(src ?? "").replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _lang, codice) => {
    blocchi.push(`<pre><code>${esc(codice.replace(/\n$/, ""))}</code></pre>`);
    return `\u0000${blocchi.length - 1}\u0000`;
  });
  const inline = (s) =>
    esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  const righe = testo.split("\n");
  const out = [];
  let lista = null, para = [];
  const chiudiPara = () => { if (para.length) { out.push(`<p>${para.map(inline).join("<br>")}</p>`); para = []; } };
  const chiudiLista = () => { if (lista) { out.push(`</${lista}>`); lista = null; } };

  for (const riga of righe) {
    const blocco = riga.match(/^\u0000(\d+)\u0000$/);
    const titolo = riga.match(/^(#{1,4})\s+(.*)/);
    const ul = riga.match(/^\s*[-*•]\s+(.*)/);
    const ol = riga.match(/^\s*\d+[.)]\s+(.*)/);
    const cit = riga.match(/^>\s?(.*)/);
    if (blocco) { chiudiPara(); chiudiLista(); out.push(blocchi[+blocco[1]]); }
    else if (titolo) { chiudiPara(); chiudiLista(); out.push(`<h${titolo[1].length}>${inline(titolo[2])}</h${titolo[1].length}>`); }
    else if (ul || ol) {
      chiudiPara();
      const tipo = ul ? "ul" : "ol";
      if (lista !== tipo) { chiudiLista(); out.push(`<${tipo}>`); lista = tipo; }
      out.push(`<li>${inline((ul || ol)[1])}</li>`);
    }
    else if (cit) { chiudiPara(); chiudiLista(); out.push(`<blockquote>${inline(cit[1])}</blockquote>`); }
    else if (!riga.trim()) { chiudiPara(); chiudiLista(); }
    else { chiudiLista(); para.push(riga); }
  }
  chiudiPara(); chiudiLista();
  return out.join("");
}

export function leggiLocale(chiave, predefinito) {
  try { return JSON.parse(localStorage.getItem(chiave)) ?? predefinito; } catch { return predefinito; }
}
export function salvaLocale(chiave, valore) {
  try { localStorage.setItem(chiave, JSON.stringify(valore)); } catch { /* niente */ }
}
