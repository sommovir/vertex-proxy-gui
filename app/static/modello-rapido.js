// «+ Altro modello…» dal menu della chat: aggiunge un modello alle impostazioni e lo verifica.

import { $, api, toast } from "./util.js";
import { normalizzaId } from "./impostazioni.js";

export const VALORE_ALTRO = "__altro__";
const TIPO_PER_MODALITA = { chat: "chat", immagine: "gemini-immagine", video: "veo" };

let alAggiunto = () => {};

export function initModelloRapido(callback) {
  alAggiunto = callback;
  const dlg = $("#dlg-modello");
  $("#annulla-modello").onclick = () => dlg.close();
  $("#nuovo-id").oninput = () => {
    const id = normalizzaId($("#nuovo-id").value).toLowerCase();
    if (id.startsWith("imagen")) $("#nuovo-tipo").value = "imagen";
    else if (id.startsWith("veo")) $("#nuovo-tipo").value = "veo";
    else if (id.startsWith("gemini") && id.includes("image")) $("#nuovo-tipo").value = "gemini-immagine";
  };
  $("#form-modello").onsubmit = (e) => { e.preventDefault(); aggiungi(); };
}

export function apriModelloRapido(modalita) {
  $("#form-modello").reset();
  $("#err-modello").textContent = "";
  $("#nuovo-tipo").value = TIPO_PER_MODALITA[modalita] || "chat";
  $("#dlg-modello").showModal();
  $("#nuovo-id").focus();
}

async function aggiungi() {
  const id = normalizzaId($("#nuovo-id").value);
  if (!id) return;
  const modello = {
    id,
    nome: $("#nuovo-nome").value.trim() || id,
    tipo: $("#nuovo-tipo").value,
    regione: $("#nuovo-regione").value.trim(),
  };
  const btn = $("#salva-modello");
  btn.disabled = true;
  btn.textContent = "Verifico…";
  $("#err-modello").textContent = "";
  try {
    const imp = await api("/api/impostazioni");
    const modelli = imp.modelli.filter((m) => m.id !== id).concat(modello);
    await api("/api/impostazioni", {
      method: "PUT",
      json: { profili: imp.profili, profilo_attivo: imp.profilo_attivo, modelli, istruzioni_sistema: imp.istruzioni_sistema },
    });
    let esito = null;
    try {
      [esito] = await api("/api/modelli/verifica", { method: "POST", json: { modelli: [modello] } });
    } catch (e) {
      esito = { ok: false, messaggio: e.message };
    }
    $("#dlg-modello").close();
    toast(esito?.ok ? `${modello.nome} aggiunto e disponibile` : `${modello.nome} aggiunto, ma la verifica dice: ${esito?.messaggio}`);
    alAggiunto(modello);
  } catch (e) {
    $("#err-modello").textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Aggiungi e verifica";
  }
}
