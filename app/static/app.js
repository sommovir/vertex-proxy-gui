// Vertex Studio — logica principale dell'interfaccia.

import { $, api, esc, markdown, toast, leggiLocale, salvaLocale } from "./util.js";
import { initImpostazioni, apriImpostazioni } from "./impostazioni.js";
import { initAccount, aggiornaAccount } from "./account.js";

const TIPI_PER_MODALITA = { chat: ["chat"], immagine: ["gemini-immagine", "imagen"], video: ["veo"] };
const FORMATI = {
  immagine: ["1:1", "16:9", "9:16", "4:3", "3:4"],
  video: ["16:9", "9:16"],
};
const SEGNAPOSTO = {
  chat: "Scrivi un messaggio…",
  immagine: "Descrivi l'immagine da creare, o allegane una da modificare…",
  video: "Descrivi il video (puoi allegare un'immagine di partenza)…",
};
const MODALITA_DI_TIPO = { "chat": "chat", "gemini-immagine": "immagine", "imagen": "immagine", "veo": "video" };

const stato = {
  imp: null,
  conversazioni: [],
  convId: null,
  messaggi: [],
  modalita: leggiLocale("vs.modalita", "chat"),
  allegati: [],
  attese: new Map(), // convId -> [{job, tipo, inizio}]
};

// ---------------------------------------------------------------- avvio

initImpostazioni(async () => {
  await caricaImpostazioni();
  verificaStato();
  toast("Impostazioni salvate");
});

initAccount(() => verificaStato());
await caricaImpostazioni();
await caricaElenco();
verificaStato();
const iniziale = location.hash.slice(1);
if (iniziale && stato.conversazioni.some((c) => c.id === iniziale)) apri(iniziale);
else disegnaMessaggi();
if (!stato.imp.profili.length) apriImpostazioni();

// ---------------------------------------------------------------- impostazioni e stato

async function caricaImpostazioni() {
  stato.imp = await api("/api/impostazioni");
  impostaModalita(stato.modalita);
}

async function verificaStato() {
  const el = $("#stato");
  el.className = "stato";
  el.querySelector(".testo").textContent = "Verifica connessione…";
  el.title = "";
  try {
    const s = await api("/api/stato");
    aggiornaAccount(s);
    el.classList.add(s.ok ? "ok" : "ko");
    const chi = s.account ? ` · ${s.account}` : "";
    el.querySelector(".testo").textContent = s.ok ? `${s.profilo}${chi}` : (s.profilo ? `${s.profilo} · non connesso` : "Nessun profilo");
    el.title = s.messaggio;
    if (!s.ok && s.profilo && s.account) toast(s.messaggio);
  } catch (e) {
    el.classList.add("ko");
    el.querySelector(".testo").textContent = "Errore";
    el.title = e.message;
  }
}

$("#stato").onclick = verificaStato;
$("#btn-impostazioni").onclick = () => apriImpostazioni();
$("#btn-cartella").onclick = () => api("/api/apri-cartella", { method: "POST" });

// ---------------------------------------------------------------- modalità e modelli

function impostaModalita(m) {
  stato.modalita = m;
  salvaLocale("vs.modalita", m);
  for (const b of $("#modalita").children) b.classList.toggle("attivo", b.dataset.m === m);
  const modelli = stato.imp.modelli.filter((x) => TIPI_PER_MODALITA[m].includes(x.tipo));
  const scelto = leggiLocale(`vs.modello.${m}`, null);
  $("#modello").innerHTML = modelli.length
    ? modelli.map((x) => `<option value="${esc(x.id)}" ${x.id === scelto ? "selected" : ""}>${esc(x.nome)}</option>`).join("")
    : `<option value="">Nessun modello configurato</option>`;
  $("#formato").innerHTML = (FORMATI[m] || []).map((f) => `<option>${f}</option>`).join("");
  $("#formato").value = leggiLocale(`vs.formato.${m}`, FORMATI[m]?.[0]) || "";
  $("#input").placeholder = SEGNAPOSTO[m];
  aggiornaOpzioni();
}

function modelloScelto() {
  return stato.imp.modelli.find((x) => x.id === $("#modello").value);
}

function aggiornaOpzioni() {
  const tipo = modelloScelto()?.tipo;
  $("#formato").hidden = stato.modalita === "chat";
  $("#numero").hidden = tipo !== "imagen";
  $("#durata").hidden = tipo !== "veo";
  $("#audio-wrap").hidden = tipo !== "veo";
}

$("#modalita").onclick = (e) => e.target.dataset.m && impostaModalita(e.target.dataset.m);
$("#modello").onchange = () => { salvaLocale(`vs.modello.${stato.modalita}`, $("#modello").value); aggiornaOpzioni(); };
$("#formato").onchange = () => salvaLocale(`vs.formato.${stato.modalita}`, $("#formato").value);

// ---------------------------------------------------------------- elenco conversazioni

async function caricaElenco() {
  stato.conversazioni = await api("/api/conversazioni");
  disegnaElenco();
}

function gruppoData(iso) {
  const giorno = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = (giorno(new Date()) - giorno(new Date(iso))) / 86400000;
  if (diff < 1) return "Oggi";
  if (diff < 2) return "Ieri";
  if (diff < 7) return "Ultimi 7 giorni";
  if (diff < 30) return "Ultimi 30 giorni";
  return "Più vecchie";
}

function disegnaElenco() {
  const q = $("#cerca").value.trim().toLowerCase();
  const filtrate = stato.conversazioni.filter((c) => !q || c.titolo.toLowerCase().includes(q));
  let html = "", gruppo = null;
  for (const c of filtrate) {
    const g = gruppoData(c.aggiornata);
    if (g !== gruppo) { html += `<div class="gruppo">${g}</div>`; gruppo = g; }
    html += `<a href="#${esc(c.id)}" data-id="${esc(c.id)}" class="${c.id === stato.convId ? "attiva" : ""}">${esc(c.titolo)}</a>`;
  }
  $("#lista").innerHTML = html || `<div class="vuota">${q ? "Nessun risultato" : "Ancora nessuna conversazione"}</div>`;
}

$("#cerca").oninput = disegnaElenco;
$("#lista").onclick = (e) => {
  const a = e.target.closest("a[data-id]");
  if (!a) return;
  e.preventDefault();
  apri(a.dataset.id);
  $("#sidebar").classList.remove("aperta");
};
$("#btn-nuova").onclick = () => {
  stato.convId = null;
  stato.messaggi = [];
  history.replaceState(null, "", location.pathname);
  disegnaElenco();
  disegnaMessaggi();
  $("#input").focus();
  $("#sidebar").classList.remove("aperta");
};
$("#btn-menu").onclick = () => $("#sidebar").classList.toggle("aperta");

async function apri(id) {
  try {
    const conv = await api(`/api/conversazioni/${id}`);
    stato.convId = id;
    stato.messaggi = conv.messaggi;
    history.replaceState(null, "", `#${id}`);
    disegnaElenco();
    disegnaMessaggi();
  } catch (e) {
    toast(e.message);
  }
}

// ---------------------------------------------------------------- titolo, elimina, cartella

const titolo = $("#titolo");
titolo.onclick = () => {
  if (!stato.convId || titolo.isContentEditable) return;
  titolo.contentEditable = "true";
  titolo.focus();
  getSelection().selectAllChildren(titolo);
};
titolo.onkeydown = (e) => {
  if (e.key === "Enter") { e.preventDefault(); titolo.blur(); }
  if (e.key === "Escape") { titolo.textContent = convCorrente()?.titolo; titolo.blur(); }
};
titolo.onblur = async () => {
  if (!titolo.isContentEditable) return;
  titolo.contentEditable = "false";
  const nuovo = titolo.textContent.trim();
  if (stato.convId && nuovo && nuovo !== convCorrente()?.titolo) {
    await api(`/api/conversazioni/${stato.convId}`, { method: "PATCH", json: { titolo: nuovo } });
    await caricaElenco();
  }
  titolo.textContent = convCorrente()?.titolo || "Vertex Studio";
};

$("#btn-elimina").onclick = async () => {
  const c = convCorrente();
  if (!c || !confirm(`Spostare «${c.titolo}» nel cestino?\nLa trovi nella cartella dati, sotto «cestino».`)) return;
  await api(`/api/conversazioni/${c.id}`, { method: "DELETE" });
  await caricaElenco();
  $("#btn-nuova").click();
};
$("#btn-media").onclick = () => stato.convId && api(`/api/apri-cartella?conv_id=${stato.convId}`, { method: "POST" });

function convCorrente() {
  return stato.conversazioni.find((c) => c.id === stato.convId);
}

// ---------------------------------------------------------------- messaggi

function urlMedia(f) {
  return `/media/${stato.convId}/${encodeURIComponent(f.nome)}`;
}

function htmlFile(f) {
  const url = urlMedia(f);
  const scarica = `<a class="scarica" href="${url}" download="${esc(f.nome)}" title="Scarica"><svg viewBox="0 0 24 24"><path d="M12 4v12M6 11l6 6 6-6M5 20h14"/></svg></a>`;
  if (f.mime.startsWith("image/")) return `<div class="media"><img src="${url}" alt="" loading="lazy" data-zoom>${scarica}</div>`;
  if (f.mime.startsWith("video/")) return `<div class="media"><video src="${url}" controls preload="metadata"></video>${scarica}</div>`;
  if (f.mime.startsWith("audio/")) return `<audio src="${url}" controls></audio>`;
  return `<a class="file-chip" href="${url}" target="_blank">📄 ${esc(f.nome)}</a>`;
}

function nomeModello(id) {
  return stato.imp.modelli.find((m) => m.id === id)?.nome || id;
}

function htmlMessaggio(m, i) {
  const galleria = m.file?.length ? `<div class="galleria">${m.file.map(htmlFile).join("")}</div>` : "";
  const ora = new Date(m.creato).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  if (m.ruolo === "utente") {
    return `<div class="msg utente">${galleria}${m.testo ? `<div class="bolla">${esc(m.testo)}</div>` : ""}</div>`;
  }
  if (m.ruolo === "errore") {
    return `<div class="msg errore"><div class="bolla">${esc(m.testo)}</div>
      <div class="meta"><span>${esc(nomeModello(m.modello))} · ${ora}</span><button data-riprova="${i}">Riprova</button></div></div>`;
  }
  const immagini = (m.file || []).filter((f) => f.mime.startsWith("image/"));
  return `<div class="msg modello">
    ${m.testo ? `<div class="bolla md">${markdown(m.testo)}</div>` : ""}${galleria}
    <div class="meta"><span>${esc(nomeModello(m.modello))} · ${ora}</span>
      ${m.testo ? `<button data-copia="${i}">Copia</button>` : ""}
      ${immagini.length ? `<button data-riusa="${i}" title="Allega queste immagini al prossimo messaggio">Riusa immagine</button>` : ""}
    </div></div>`;
}

function durata(inizio) {
  const sec = Math.floor((Date.now() - inizio) / 1000);
  return sec >= 60 ? `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}` : `${sec}s`;
}

function htmlAttesa(a) {
  if (a.tipo === "chat") return `<div class="msg modello attesa"><span class="puntini"><span></span><span></span><span></span></span></div>`;
  const cosa = a.tipo === "veo" ? "Genero il video (di solito 1–3 minuti)" : "Genero l'immagine";
  return `<div class="msg modello"><div class="attesa"><div class="scheletro"></div>
    <span>${cosa}… <span data-inizio="${a.inizio}">${durata(a.inizio)}</span></span></div></div>`;
}

// Aggiorna solo i contatori, senza ridisegnare la chat (i video non si interrompono).
setInterval(() => {
  for (const el of document.querySelectorAll("[data-inizio]")) el.textContent = durata(+el.dataset.inizio);
}, 1000);

function disegnaMessaggi() {
  const box = $("#messaggi");
  const c = convCorrente();
  $("#titolo").textContent = c?.titolo || "Vertex Studio";
  $("#azioni-conv").hidden = !c;
  const attese = stato.attese.get(stato.convId) || [];
  if (!stato.messaggi.length && !attese.length) {
    box.innerHTML = `<div class="benvenuto">
      <h2>Cosa creiamo oggi?</h2>
      <p>Chat con Gemini, immagini con Nano Banana e Imagen, video con Veo. Tutto salvato solo su questo computer.</p>
      <div class="suggerimenti">
        <button data-esempio="chat|Riassumi in 5 punti i vantaggi dell'impersonation dei service account">
          <b>Chat</b><span>Riassumi i vantaggi dell'impersonation…</span></button>
        <button data-esempio="immagine|Un laboratorio di ricerca luminoso al tramonto, stile illustrazione editoriale">
          <b>Immagine</b><span>Un laboratorio al tramonto, stile editoriale…</span></button>
        <button data-esempio="video|Ripresa aerea lenta su una città italiana all'alba, luce dorata">
          <b>Video</b><span>Ripresa aerea su una città all'alba…</span></button>
      </div></div>`;
    return;
  }
  const inFondo = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  box.innerHTML = stato.messaggi.map(htmlMessaggio).join("") + attese.map(htmlAttesa).join("");
  if (inFondo || attese.length) box.scrollTop = box.scrollHeight;
}

$("#messaggi").onclick = async (e) => {
  const t = e.target;
  const es = t.closest("[data-esempio]");
  if (es) {
    const [m, testo] = es.dataset.esempio.split("|");
    impostaModalita(m);
    $("#input").value = testo;
    autoAltezza();
    $("#input").focus();
    return;
  }
  if (t.matches("[data-zoom]")) {
    const lb = document.createElement("div");
    lb.className = "lightbox";
    lb.innerHTML = `<img src="${t.src}" alt="">`;
    lb.onclick = () => lb.remove();
    document.body.append(lb);
    return;
  }
  if (t.dataset.copia) {
    await navigator.clipboard.writeText(stato.messaggi[+t.dataset.copia].testo);
    toast("Copiato");
  }
  if (t.dataset.riusa) {
    for (const f of stato.messaggi[+t.dataset.riusa].file.filter((x) => x.mime.startsWith("image/"))) {
      const blob = await (await fetch(urlMedia(f))).blob();
      aggiungiAllegati([new File([blob], f.nome, { type: f.mime })]);
    }
    if (stato.modalita === "chat") impostaModalita("immagine");
    $("#input").focus();
  }
  if (t.dataset.riprova) {
    const ultimoUtente = [...stato.messaggi.slice(0, +t.dataset.riprova)].reverse().find((m) => m.ruolo === "utente");
    if (ultimoUtente) {
      $("#input").value = ultimoUtente.testo;
      autoAltezza();
      $("#input").focus();
    }
  }
};

// ---------------------------------------------------------------- allegati

function aggiungiAllegati(files) {
  stato.allegati.push(...files);
  disegnaAllegati();
}

function disegnaAllegati() {
  const box = $("#allegati");
  box.innerHTML = "";
  stato.allegati.forEach((f, i) => {
    const el = document.createElement("div");
    el.className = "allegato";
    el.title = f.name;
    if (f.type.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = URL.createObjectURL(f);
      el.append(img);
    } else {
      el.textContent = f.name.slice(0, 24);
    }
    const x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.onclick = () => { stato.allegati.splice(i, 1); disegnaAllegati(); };
    el.append(x);
    box.append(el);
  });
}

$("#file").onchange = (e) => { aggiungiAllegati([...e.target.files]); e.target.value = ""; };
const composer = $("#composer");
composer.ondragover = (e) => { e.preventDefault(); composer.classList.add("trascina"); };
composer.ondragleave = () => composer.classList.remove("trascina");
composer.ondrop = (e) => {
  e.preventDefault();
  composer.classList.remove("trascina");
  aggiungiAllegati([...e.dataTransfer.files]);
};
$("#input").onpaste = (e) => {
  const files = [...e.clipboardData.files];
  if (files.length) { e.preventDefault(); aggiungiAllegati(files); }
};

// ---------------------------------------------------------------- invio

function autoAltezza() {
  const t = $("#input");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 240) + "px";
}
$("#input").oninput = autoAltezza;
$("#input").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); composer.requestSubmit(); }
};

composer.onsubmit = async (e) => {
  e.preventDefault();
  const testo = $("#input").value.trim();
  const m = modelloScelto();
  if (!testo && !stato.allegati.length) return;
  if (!m) { toast("Nessun modello per questa modalità: aggiungilo nelle Impostazioni."); return; }

  const opzioni = {};
  if (!$("#formato").hidden) opzioni.formato = $("#formato").value;
  if (!$("#numero").hidden) opzioni.numero = +$("#numero").value;
  if (!$("#durata").hidden) { opzioni.durata = +$("#durata").value; opzioni.audio = $("#audio").checked; }

  const fd = new FormData();
  fd.append("modello", m.id);
  fd.append("testo", testo);
  fd.append("opzioni", JSON.stringify(opzioni));
  for (const f of stato.allegati) fd.append("allegati", f, f.name);

  $("#invia").disabled = true;
  try {
    if (!stato.convId) {
      const c = await api("/api/conversazioni", { method: "POST" });
      stato.convId = c.id;
      stato.messaggi = [];
      history.replaceState(null, "", `#${c.id}`);
    }
    const convId = stato.convId;
    const r = await api(`/api/conversazioni/${convId}/messaggi`, { method: "POST", body: fd });
    stato.messaggi.push(r.messaggio);
    $("#input").value = "";
    autoAltezza();
    stato.allegati = [];
    disegnaAllegati();
    attendi(convId, r.job, m.tipo);
    await caricaElenco();
    disegnaMessaggi();
  } catch (err) {
    toast(err.message);
  } finally {
    $("#invia").disabled = false;
  }
};

function attendi(convId, job, tipo) {
  const voce = { job, tipo, inizio: Date.now() };
  stato.attese.set(convId, [...(stato.attese.get(convId) || []), voce]);
  const intervallo = tipo === "veo" ? 5000 : 1500;

  const fine = () => {
    stato.attese.set(convId, (stato.attese.get(convId) || []).filter((a) => a !== voce));
  };
  const controlla = async () => {
    try {
      const s = await api(`/api/job/${job}`);
      if (s.stato === "in_corso") return setTimeout(controlla, intervallo);
      fine();
      if (stato.convId === convId) stato.messaggi.push(s.messaggio);
      else toast(s.stato === "fatto" ? "Una generazione è pronta in un'altra conversazione" : "Una generazione è fallita");
      await caricaElenco();
      if (stato.convId === convId) disegnaMessaggi();
    } catch (err) {
      fine();
      toast(err.message);
      if (stato.convId === convId) apri(convId);
    }
  };
  setTimeout(controlla, intervallo);
}
