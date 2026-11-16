// Pannello Impostazioni: profili Google Cloud, modelli, istruzioni di sistema.

import { $, api, esc } from "./util.js";

const ETICHETTE_TIPO = {
  "chat": "Chat (Gemini)",
  "gemini-immagine": "Immagine (Gemini / Nano Banana)",
  "imagen": "Immagine (Imagen)",
  "veo": "Video (Veo)",
};

let bozza = null;
let alSalvataggio = () => {};

export function initImpostazioni(callback) {
  alSalvataggio = callback;
  const dlg = $("#dlg-impostazioni");

  $("#schede").addEventListener("click", (e) => {
    const s = e.target.dataset?.s;
    if (!s) return;
    for (const b of $("#schede").children) b.classList.toggle("attivo", b.dataset.s === s);
    for (const sez of dlg.querySelectorAll("[data-scheda]")) sez.hidden = sez.dataset.scheda !== s;
  });

  $("#add-profilo").onclick = () => {
    leggiForm();
    const id = Math.random().toString(36).slice(2, 10);
    bozza.profili.push({ id, nome: "Nuovo profilo", progetto: "", service_account: "", regione: "us-central1", regione_gemini: "global" });
    if (!bozza.profilo_attivo) bozza.profilo_attivo = id;
    disegnaProfili();
    $("#profili").lastElementChild?.querySelector("[data-k=progetto]")?.focus();
  };
  $("#add-modello").onclick = () => {
    leggiForm();
    bozza.modelli.push({ id: "", nome: "", tipo: "chat", regione: "" });
    disegnaModelli();
  };
  $("#reset-modelli").onclick = () => {
    leggiForm();
    bozza.modelli = structuredClone(bozza.predefiniti);
    disegnaModelli();
  };
  $("#annulla-impostazioni").onclick = () => dlg.close();
  $("#salva-impostazioni").onclick = salva;

  $("#profili").addEventListener("click", (e) => {
    const card = e.target.closest(".profilo");
    if (!card) return;
    if (e.target.matches("[data-elimina]")) {
      leggiForm();
      bozza.profili = bozza.profili.filter((p) => p.id !== card.dataset.id);
      if (bozza.profilo_attivo === card.dataset.id) bozza.profilo_attivo = bozza.profili[0]?.id ?? null;
      disegnaProfili();
    } else if (e.target.matches("input[type=radio]")) {
      leggiForm();
      bozza.profilo_attivo = card.dataset.id;
      disegnaProfili();
    }
  });
  $("#modelli").addEventListener("click", (e) => {
    if (!e.target.closest("[data-elimina]")) return;
    leggiForm();
    bozza.modelli.splice(+e.target.closest(".riga-modello").dataset.i, 1);
    disegnaModelli();
  });
}

export async function apriImpostazioni(scheda = "profili") {
  bozza = await api("/api/impostazioni");
  disegnaProfili();
  disegnaModelli();
  $("#istruzioni").value = bozza.istruzioni_sistema || "";
  $("#cartella-dati").textContent = bozza.cartella_dati;
  $("#err-impostazioni").textContent = "";
  $(`#schede [data-s=${scheda}]`).click();
  $("#dlg-impostazioni").showModal();
  if (!bozza.profili.length) $("#add-profilo").click();
}

function disegnaProfili() {
  $("#profili").innerHTML = bozza.profili.map((p) => `
    <div class="profilo ${p.id === bozza.profilo_attivo ? "attivo" : ""}" data-id="${esc(p.id)}">
      <div class="profilo-testa">
        <input type="radio" name="attivo" ${p.id === bozza.profilo_attivo ? "checked" : ""} title="Usa questo profilo">
        <input type="text" data-k="nome" value="${esc(p.nome)}" placeholder="Nome del profilo">
        <button type="button" class="btn ghost" data-elimina>Rimuovi</button>
      </div>
      <div class="griglia">
        <label class="campo">ID progetto Google Cloud
          <input type="text" data-k="progetto" value="${esc(p.progetto)}" placeholder="mio-progetto-123"></label>
        <label class="campo">Service account da impersonare
          <input type="text" data-k="service_account" value="${esc(p.service_account)}" placeholder="nome@progetto.iam.gserviceaccount.com"></label>
        <label class="campo">Regione (Imagen, Veo)
          <input type="text" data-k="regione" value="${esc(p.regione)}" placeholder="us-central1"></label>
        <label class="campo">Regione modelli Gemini
          <input type="text" data-k="regione_gemini" value="${esc(p.regione_gemini)}" placeholder="global"></label>
      </div>
    </div>`).join("") || `<p class="aiuto">Nessun profilo.</p>`;
}

function disegnaModelli() {
  const opzioni = (sel) => bozza.tipi.map((t) => `<option value="${t}" ${t === sel ? "selected" : ""}>${ETICHETTE_TIPO[t] || t}</option>`).join("");
  $("#modelli").innerHTML = `
    <div class="riga-modello intestazione"><span>Nome</span><span>ID modello</span><span>Tipo</span><span>Regione</span><span></span></div>
    ${bozza.modelli.map((m, i) => `
    <div class="riga-modello" data-i="${i}">
      <input type="text" data-k="nome" value="${esc(m.nome)}" placeholder="Nome">
      <input type="text" data-k="id" value="${esc(m.id)}" placeholder="es. gemini-2.5-flash">
      <select data-k="tipo">${opzioni(m.tipo)}</select>
      <input type="text" data-k="regione" value="${esc(m.regione)}" placeholder="del profilo">
      <button type="button" class="btn ghost icona" data-elimina title="Rimuovi">✕</button>
    </div>`).join("")}`;
}

function leggiForm() {
  for (const card of document.querySelectorAll("#profili .profilo")) {
    const p = bozza.profili.find((x) => x.id === card.dataset.id);
    for (const inp of card.querySelectorAll("[data-k]")) p[inp.dataset.k] = inp.value.trim();
  }
  for (const riga of document.querySelectorAll("#modelli .riga-modello[data-i]")) {
    const m = bozza.modelli[+riga.dataset.i];
    for (const inp of riga.querySelectorAll("[data-k]")) m[inp.dataset.k] = inp.value.trim();
  }
  bozza.istruzioni_sistema = $("#istruzioni").value;
}

async function salva() {
  leggiForm();
  const err = $("#err-impostazioni");
  err.textContent = "";
  const btn = $("#salva-impostazioni");
  btn.disabled = true;
  try {
    const { profili, profilo_attivo, modelli, istruzioni_sistema } = bozza;
    await api("/api/impostazioni", { method: "PUT", json: { profili, profilo_attivo, modelli, istruzioni_sistema } });
    $("#dlg-impostazioni").close();
    alSalvataggio();
  } catch (e) {
    err.textContent = e.message;
  } finally {
    btn.disabled = false;
  }
}
