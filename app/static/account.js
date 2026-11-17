// Pulsante Accedi / Esci: login Google tramite gcloud, senza passare dal terminale.

import { $, api, toast } from "./util.js";

let account = "";
let dopoCambio = () => {};

export function initAccount(callback) {
  dopoCambio = callback;
  $("#btn-account").onclick = () => (account ? esci() : accedi());
}

export function aggiornaAccount(stato) {
  account = stato.account || "";
  const btn = $("#btn-account");
  btn.hidden = false;
  btn.disabled = false;
  btn.textContent = account ? "Esci" : "Accedi";
  btn.title = account ? `Disconnetti ${account} da questo computer` : "Accedi con il tuo account Google";
  btn.classList.toggle("evidente", !account);
}

async function accedi() {
  const btn = $("#btn-account");
  btn.disabled = true;
  btn.textContent = "Accesso…";
  try {
    let s = await api("/api/login", { method: "POST" });
    if (s.stato === "in_corso") toast("Scegli il tuo account nella pagina di Google che si è aperta.");
    while (s.stato === "in_corso") {
      await new Promise((r) => setTimeout(r, 2000));
      s = await api("/api/login");
    }
    toast(s.stato === "fatto" ? "Accesso eseguito" : s.messaggio);
  } catch (e) {
    toast(e.message);
  }
  dopoCambio();
}

async function esci() {
  if (!confirm(`Disconnettere ${account} da questo computer?\nPer usare l'app servirà accedere di nuovo.`)) return;
  try {
    const r = await api("/api/logout", { method: "POST" });
    toast(r.messaggio);
  } catch (e) {
    toast(e.message);
  }
  dopoCambio();
}
