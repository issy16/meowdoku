// Signing in, and keeping the game in the player's account too (R11.6–R11.11).
// It's optional: until account.json names a Supabase project, or if the
// service can't be reached, the account bar stays hidden and everyone plays
// as a guest, with the game saved on their device (R11.7a). Supabase's own
// rules decide whose save can be read (R11.9); the key here is public.

const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.118.0/+esm";  // pinned (NFR6)
const AUTH_KEY = "meowdoku-auth";  // where Supabase keeps the sign-in (R11.15)
const UPLOAD_AFTER_MS = 800;  // a quick burst of moves is written once

const account = (() => {
  let client = null;
  let user = null;
  let hooks = null;     // from app.js: restore(save), deviceSave(), t(key, args)
  let note = null;      // the account bar's message as {key, args, error}, worded again on language changes
  let waiting = null;   // the save to upload, while a burst of moves settles
  let timer = null;
  const $ = (id) => document.getElementById(id);

  // The page's own address, where Google and email links come back to (R11.15).
  const pageAddress = () => location.origin + location.pathname;

  function say(key, args = {}, error = false) {
    note = key ? { key, args, error } : null;
    render();
  }

  function render() {
    if (!hooks) return;
    $("signed-out").hidden = Boolean(user);
    $("signed-in").hidden = !user;
    if (user) $("who").textContent = hooks.t("ui.signed_in_as", { name: user.email || "" });
    const line = $("account-message");
    line.textContent = note ? hooks.t(note.key, note.args) : "";
    line.classList.toggle("error", Boolean(note && note.error));
  }

  async function start(appHooks) {
    hooks = appHooks;
    let config;
    try {
      const response = await fetch("account.json");
      config = response.ok ? await response.json() : {};
      if (!config.url || !config.key) return;  // no project yet: guests only
      const { createClient } = await import(SUPABASE_JS);
      client = createClient(config.url, config.key, {
        auth: { storageKey: AUTH_KEY, flowType: "pkce", persistSession: true, detectSessionInUrl: true },
      });
      // Coming back from Google or an email link: the sign-in finishes here,
      // then the address is put back as it was, since state never goes in the URL (R11.14).
      const returned = new URLSearchParams(location.search);
      const { data } = await client.auth.getSession();
      const failure = returned.get("error_description") || new URLSearchParams(location.hash.slice(1)).get("error_description");
      if (returned.has("code") || failure) history.replaceState(null, "", pageAddress());
      if (failure) say("ui.sign_in_failed", { reason: failure }, true);
      wireButtons();
      $("account").hidden = false;
      signedIn(data.session ? data.session.user : null);
      client.auth.onAuthStateChange((event, session) => {
        // Supabase asks that no other call is awaited inside this callback.
        setTimeout(() => signedIn(session ? session.user : null), 0);
      });
    } catch {
      client = null;  // the service can't be reached: playing goes on as a guest (R11.6)
    }
  }

  function signedIn(next) {
    const changed = (next && next.id) !== (user && user.id);
    user = next;
    render();
    if (changed && user) pickUp();
  }

  // After signing in, the newer of the account's game and this device's game wins (R11.7).
  async function pickUp() {
    const { data, error } = await client.from("saves").select("save, saved_at").eq("user_id", user.id).maybeSingle();
    if (error) { say("ui.account_load_failed", {}, true); return; }
    const device = hooks.deviceSave();
    const deviceTime = device && Date.parse(device.saved);
    if (data && !(deviceTime > Date.parse(data.saved_at))) {
      await hooks.restore(data.save);
      say("ui.account_restored");
    } else if (device) {
      keep(device);
      await flush();
    }
  }

  // Called with every save the device keeps; uploaded once moves pause.
  function keep(save) {
    if (!client || !user) return;
    waiting = save;
    clearTimeout(timer);
    timer = setTimeout(flush, UPLOAD_AFTER_MS);
  }

  async function flush() {
    clearTimeout(timer);
    if (!waiting || !user) return;
    const save = waiting;
    waiting = null;
    const { error } = await client.from("saves").upsert({
      user_id: user.id,
      save,
      saved_at: save.saved || new Date().toISOString(),
    });
    // R11.10: a failure is always said; the game stays on the device and the next move tries again.
    if (error) say("ui.account_save_failed", {}, true);
    else if (note && note.key === "ui.account_save_failed") say(null);
  }

  function wireButtons() {
    $("google").onclick = async () => {
      const { error } = await client.auth.signInWithOAuth({ provider: "google", options: { redirectTo: pageAddress() } });
      if (error) say("ui.sign_in_failed", { reason: error.message }, true);
    };
    $("email-start").onclick = () => {
      $("email-form").hidden = false;
      $("email").focus();
    };
    $("email-form").onsubmit = async (event) => {
      event.preventDefault();
      const { error } = await client.auth.signInWithOtp({
        email: $("email").value.trim(),
        options: { emailRedirectTo: pageAddress() },
      });
      if (error) { say("ui.sign_in_failed", { reason: error.message }, true); return; }
      $("email-form").hidden = true;
      say("ui.link_sent");
    };
    $("sign-out").onclick = async () => {
      await flush();
      const { error } = await client.auth.signOut();
      if (error) say("ui.account_error", { reason: error.message }, true);
      else say(null);
    };
    $("delete-account").onclick = async () => {
      if (!confirm(hooks.t("ui.delete_confirm"))) return;
      waiting = null;
      clearTimeout(timer);
      const { error } = await client.rpc("delete_account");  // R11.11, only the signed-in player
      if (error) { say("ui.account_error", { reason: error.message }, true); return; }
      await client.auth.signOut({ scope: "local" });
      signedIn(null);
      say("ui.account_deleted");
    };
    // Leaving the page uploads whatever is still waiting.
    document.addEventListener("visibilitychange", () => { if (document.hidden) flush(); });
  }

  return { start, keep, render };
})();
