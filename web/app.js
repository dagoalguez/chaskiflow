/* ChaskiFlow — interfaz (JavaScript puro, sin dependencias, sin innerHTML: todo el texto va con textContent). */
(function () {
  "use strict";

  // ============================================================ utilidades
  var I18N = {
    es: {
      schedule: "Programar", schedules: "Programaciones", no_sched: "Sin programaciones.", sched_what: "Qué", sched_next: "Próxima", sched_last: "Última",
      sched_daily: "Diaria (hora fija)", sched_interval: "Cada cierto tiempo", sched_time: "Hora (del servidor)", sched_every: "Cada (minutos)",
      sched_new: "Nueva programación", sched_hint: "Usa la hora de la PC que corre el servidor y los permisos de quien la crea. Si el servidor estaba apagado a esa hora, esa ejecución se omite (no se acumulan).",
      app: "ChaskiFlow", user: "Usuario", password: "Contraseña", enter: "Entrar", setup_title: "Crear administrador",
      setup_hint: "Primera vez: cree la cuenta del administrador.", display_name: "Nombre para mostrar",
      create: "Crear", logout: "Salir", new_wf: "+ Nuevo", wf_new_name: "Nuevo workflow", no_wf: "Aún no hay workflows.",
      pick_wf: "Elija o cree un workflow", pick_hint: "Un workflow es una cadena de pasos (plugins) que se ejecutan en orden.",
      trash: "Papelera", restore: "Restaurar", deleted: "Workflow eliminado", undo: "Deshacer", import_: "Importar", import_report: "Informe de importación (formato G1G)",
      steps: "Pasos", graph: "Editor", runs: "Ejecuciones", run: "▶ Ejecutar", stop: "■ Parar", validate: "Validar", share: "Compartir",
      export_: "Exportar", duplicate: "Duplicar", saved: "Guardado", saving: "Guardando…", unsaved: "Cambios sin guardar",
      conflict: "Otra persona modificó este workflow. Recargue para continuar.", reload: "Recargar",
      add_step: "Añadir paso", choose_plugin: "Elija un plugin…", label: "Nombre del paso", depends: "Depende de",
      on_error: "Si falla", stop_all: "Detener todo", continue_: "Continuar", enabled: "Activo", remove: "Quitar",
      refs: "Insertar referencia", advanced: "Opciones avanzadas", variables: "Variables", add_var: "+ Variable",
      valid_ok: "El workflow es válido.", errors: "Errores", warnings: "Avisos", readonly: "Solo lectura",
      invalid_json: "JSON inválido", required: "obligatorio", plugins: "Plugins", users: "Usuarios", audit: "Auditoría",
      secrets: "Claves", settings: "Ajustes", close: "Cerrar", save: "Guardar", cancel: "Cancelar",
      status: "Estado", enable: "Habilitar", disable: "Deshabilitar", reload_plugins: "Releer carpeta",
      approve: "Aprobar", name: "Nombre", role: "Rol", active: "Activo", new_user: "Nuevo usuario",
      reset_pw: "Cambiar contraseña", value: "Valor", scope: "Alcance", mine: "Mío", global: "Global",
      add_secret: "Guardar clave", team_access: "Acceso del equipo", none: "Ninguno", view: "Ver", run_: "Ejecutar",
      edit: "Editar", change_pw: "Debe cambiar su contraseña", new_pw: "Nueva contraseña", current_pw: "Contraseña actual",
      queued: "En cola…", running: "Ejecutando", ok: "OK", error: "Error", partial: "Parcial", cancelled: "Cancelado",
      skipped: "Omitido", pending: "Pendiente", no_runs: "Sin ejecuciones todavía.", result: "Resultado",
      language: "Idioma", theme: "Tema", dark: "Oscuro", light: "Claro", empty_wf: "Este workflow no tiene pasos. Añada el primero.",
      confirm_del: "¿Enviar a la papelera?", run_started: "Ejecución iniciada", history: "Historial", by: "por",
      none_plugins: "No hay plugins habilitados. Pida al administrador que los habilite.", rename: "Renombrar",
      sec_hint: "Las claves (API keys, tokens) se guardan en la base de datos del servidor y nunca se muestran de nuevo. Use el nombre que quiera; luego escríbalo en el campo «Clave» del paso.",
      pw_min: "Mínimo 8 caracteres", must_change: "Cambiar al entrar", copy: "Copiar", details: "Detalles", server_error: "No se pudo conectar con el servidor"
    },
    en: {
      schedule: "Schedule", schedules: "Schedules", no_sched: "No schedules.", sched_what: "What", sched_next: "Next", sched_last: "Last",
      sched_daily: "Daily (fixed time)", sched_interval: "Every so often", sched_time: "Time (server clock)", sched_every: "Every (minutes)",
      sched_new: "New schedule", sched_hint: "Uses the clock of the PC running the server and the permissions of its creator. If the server was off at that time the run is skipped (no catch-up).",
      app: "ChaskiFlow", user: "User", password: "Password", enter: "Sign in", setup_title: "Create administrator",
      setup_hint: "First run: create the administrator account.", display_name: "Display name",
      create: "Create", logout: "Sign out", new_wf: "+ New", wf_new_name: "New workflow", no_wf: "No workflows yet.",
      pick_wf: "Pick or create a workflow", pick_hint: "A workflow is a chain of steps (plugins) run in order.",
      trash: "Trash", restore: "Restore", deleted: "Workflow deleted", undo: "Undo", import_: "Import", import_report: "Import report (G1G format)",
      steps: "Steps", graph: "Editor", runs: "Runs", run: "▶ Run", stop: "■ Stop", validate: "Validate", share: "Share",
      export_: "Export", duplicate: "Duplicate", saved: "Saved", saving: "Saving…", unsaved: "Unsaved changes",
      conflict: "Someone else changed this workflow. Reload to continue.", reload: "Reload",
      add_step: "Add step", choose_plugin: "Choose a plugin…", label: "Step name", depends: "Depends on",
      on_error: "On failure", stop_all: "Stop everything", continue_: "Continue", enabled: "Enabled", remove: "Remove",
      refs: "Insert reference", advanced: "Advanced options", variables: "Variables", add_var: "+ Variable",
      valid_ok: "The workflow is valid.", errors: "Errors", warnings: "Warnings", readonly: "Read-only",
      invalid_json: "Invalid JSON", required: "required", plugins: "Plugins", users: "Users", audit: "Audit log",
      secrets: "Secrets", settings: "Settings", close: "Close", save: "Save", cancel: "Cancel",
      status: "Status", enable: "Enable", disable: "Disable", reload_plugins: "Rescan folder",
      approve: "Approve", name: "Name", role: "Role", active: "Active", new_user: "New user",
      reset_pw: "Change password", value: "Value", scope: "Scope", mine: "Mine", global: "Global",
      add_secret: "Save secret", team_access: "Team access", none: "None", view: "View", run_: "Run",
      edit: "Edit", change_pw: "You must change your password", new_pw: "New password", current_pw: "Current password",
      queued: "Queued…", running: "Running", ok: "OK", error: "Error", partial: "Partial", cancelled: "Cancelled",
      skipped: "Skipped", pending: "Pending", no_runs: "No runs yet.", result: "Result",
      language: "Language", theme: "Theme", dark: "Dark", light: "Light", empty_wf: "This workflow has no steps. Add the first one.",
      confirm_del: "Move to trash?", run_started: "Run started", history: "History", by: "by",
      none_plugins: "No plugins enabled. Ask the administrator to enable them.", rename: "Rename",
      sec_hint: "Secrets are stored in the server database and never shown again.",
      pw_min: "At least 8 characters", must_change: "Change on first login", copy: "Copy", details: "Details", server_error: "Cannot reach the server"
    }
  };
  var lang = "es";
  try { lang = localStorage.getItem("cf_lang") || ((navigator.language || "es").slice(0, 2) === "en" ? "en" : "es"); } catch (e) {}
  if (!I18N[lang]) lang = "es";
  function t(k) { return (I18N[lang] && I18N[lang][k]) || I18N.es[k] || k; }

  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else if (k === "style") { String(v).split(";").forEach(function (decl) { var i = decl.indexOf(":"); if (i > 0) el.style.setProperty(decl.slice(0, i).trim(), decl.slice(i + 1).trim()); }); }
      else if (k === "value") el.value = v;
      else if (k === "checked" || k === "disabled" || k === "selected") el[k] = !!v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c === null || c === undefined || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { add(el, x); }); return; }
    el.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
  function debounce(fn, ms) { var id; return function () { var a = arguments; clearTimeout(id); id = setTimeout(function () { fn.apply(null, a); }, ms); }; }
  function fmtDate(s) { if (!s) return ""; try { return new Date(s).toLocaleString(lang === "en" ? "en-GB" : "es-PE", { dateStyle: "short", timeStyle: "short" }); } catch (e) { return s; } }
  function fmtDur(sec) { if (sec === null || sec === undefined) return ""; sec = Number(sec); return sec < 60 ? sec.toFixed(1) + " s" : Math.floor(sec / 60) + " min " + Math.round(sec % 60) + " s"; }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  var token = null;
  function api(method, path, body) {
    var opt = { method: method, headers: { "Content-Type": "application/json" }, credentials: "same-origin" };
    if (body !== undefined) opt.body = JSON.stringify(body);
    return fetch(path, opt).then(function (r) {
      return r.text().then(function (txt) {
        var d = {};
        try { d = txt ? JSON.parse(txt) : {}; } catch (e) {}
        if (!r.ok) {
          var err = new Error(d.error || ("HTTP " + r.status));
          err.status = r.status; err.data = d;
          if (r.status === 401 && S.user) { S.user = null; showLogin(); }
          throw err;
        }
        return d;
      });
    }, function () { var e = new Error(t("server_error")); e.status = 0; e.data = {}; throw e; });
  }
  function toast(msg, actionLabel, action, ms) {
    var old = document.getElementById("toast"); if (old) old.remove();
    var el = h("div", { class: "toast", id: "toast" }, h("span", { text: msg }));
    if (actionLabel) el.appendChild(h("button", { text: actionLabel, onclick: function () { el.remove(); action(); } }));
    document.body.appendChild(el);
    setTimeout(function () { if (el.parentNode) el.remove(); }, ms || 6000);
  }

  // ============================================================ estado
  var S = { user: null, plugins: [], pmap: {}, workflows: [], current: null, runs: [], tab: "graph", live: null,
            collapsed: {}, saveState: "saved", conflict: false, view: null };
  var root = document.getElementById("app");

  function applyTheme() {
    var th = "light";
    try { th = localStorage.getItem("cf_theme") || (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); } catch (e) {}
    document.documentElement.setAttribute("data-theme", th);
    document.documentElement.lang = lang;
  }
  function setTheme(th) { try { localStorage.setItem("cf_theme", th); } catch (e) {} applyTheme(); }
  function setLang(l) { lang = l; try { localStorage.setItem("cf_lang", l); } catch (e) {} applyTheme(); if (S.user) renderShell(); else showLogin(); }

  // ============================================================ acceso
  function showLogin(needsSetup, msg) {
    document.title = "ChaskiFlow";
    stopPolling();
    var u = h("input", { type: "text", id: "lg-user", autocomplete: "username" });
    var p = h("input", { type: "password", id: "lg-pass", autocomplete: needsSetup ? "new-password" : "current-password" });
    var dn = h("input", { type: "text", id: "lg-dn" });
    var err = h("div", { class: "errmsg", text: msg || "" });
    function submit() {
      err.textContent = "";
      var body = { username: u.value.trim(), password: p.value };
      if (needsSetup) body.display_name = dn.value.trim();
      api("POST", needsSetup ? "/api/setup" : "/api/login", body).then(function (d) { S.user = d.user; boot(); },
        function (e) { err.textContent = e.message; });
    }
    var form = h("form", { class: "login", onsubmit: function (ev) { ev.preventDefault(); submit(); } },
      logoSvg("login-logo"),
      h("h1", { text: "ChaskiFlow" }),
      h("div", { class: "muted", text: needsSetup ? t("setup_hint") : "" }),
      h("div", { class: "field" }, h("div", { class: "fl", text: t("user") }), u),
      needsSetup ? h("div", { class: "field" }, h("div", { class: "fl", text: t("display_name") }), dn) : null,
      h("div", { class: "field" }, h("div", { class: "fl", text: t("password") }), p,
        needsSetup ? h("div", { class: "help", text: t("pw_min") }) : null),
      h("button", { class: "btn primary", type: "submit", text: needsSetup ? t("create") : t("enter") }),
      err,
      h("div", { style: "margin-top:12px;display:flex;gap:8px;justify-content:center" },
        h("button", { class: "btn sm", type: "button", text: lang === "es" ? "English" : "Español", onclick: function () { setLang(lang === "es" ? "en" : "es"); } }),
        h("button", { class: "btn sm", type: "button", text: document.documentElement.getAttribute("data-theme") === "dark" ? t("light") : t("dark"),
          onclick: function () { setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"); showLogin(needsSetup, msg); } })));
    clear(root).appendChild(h("div", { class: "login-wrap" }, form, aboutLine("about-login")));
    u.focus();
  }

  function start() {
    applyTheme();
    api("GET", "/api/health").then(function (d) {
      S.about = { version: d.version, author: d.author, contributions: d.contributions, license: d.license };
      if (d.needs_setup) return showLogin(true);
      return api("GET", "/api/me").then(function (m) { S.user = m.user; boot(); }, function () { showLogin(false); });
    }, function (e) { showLogin(false, e.message); });
  }

  function boot() {
    if (S.user.must_change_password) return forcePasswordChange();
    Promise.all([api("GET", "/api/plugins"), api("GET", "/api/workflows")]).then(function (r) {
      setPlugins(r[0].plugins); S.workflows = r[1].workflows; S.current = null; S.runs = []; watchList();
      renderShell();
    }, function (e) { toast(e.message); });
  }
  function setPlugins(list) { S.plugins = list; S.pmap = {}; list.forEach(function (p) { S.pmap[p.id] = p; }); }

  function forcePasswordChange() {
    var cur = h("input", { type: "password" }), nw = h("input", { type: "password" }), err = h("div", { class: "errmsg" });
    var form = h("form", { class: "login", onsubmit: function (ev) {
      ev.preventDefault();
      api("POST", "/api/me/password", { current: cur.value, "new": nw.value }).then(function () { S.user.must_change_password = false; boot(); },
        function (e) { err.textContent = e.message; });
    } }, h("h1", { text: t("change_pw") }),
      h("div", { class: "field" }, h("div", { class: "fl", text: t("current_pw") }), cur),
      h("div", { class: "field" }, h("div", { class: "fl", text: t("new_pw") }), nw, h("div", { class: "help", text: t("pw_min") })),
      h("button", { class: "btn primary", type: "submit", text: t("save") }), err);
    clear(root).appendChild(h("div", { class: "login-wrap" }, form));
  }

  // ============================================================ diálogos
  function dialog(title, body, buttons, wide) {
    var ov = h("div", { class: "overlay", onclick: function (e) { if (e.target === ov) close(); } });
    function close() { ov.remove(); }
    var df = h("div", { class: "df" });
    (buttons || [{ label: t("close"), cls: "" }]).forEach(function (b) {
      df.appendChild(h("button", { class: "btn " + (b.cls || ""), text: b.label, onclick: function () {
        var r = b.fn ? b.fn(close) : null; if (!b.keep && r !== false) close(); } }));
    });
    ov.appendChild(h("div", { class: "dialog" + (wide ? " wide" : "") },
      h("div", { class: "dh" }, h("span", { text: title }), h("button", { class: "btn icon x", text: "✕", onclick: close })),
      h("div", { class: "db" }, body), df));
    document.body.appendChild(ov);
    return { close: close, el: ov };
  }
  function confirm_(title, message, okLabel, cb) {
    dialog(title, h("div", { text: message, style: "white-space:pre-line" }),
      [{ label: t("cancel") }, { label: okLabel, cls: "danger", fn: function () { cb(); } }]);
  }
  function prompt_(title, label, value, cb) {
    var inp = h("input", { type: "text", value: value || "" });
    var d = dialog(title, h("div", { class: "field" }, h("div", { class: "fl", text: label }), inp),
      [{ label: t("cancel") }, { label: t("save"), cls: "primary", fn: function () { var v = inp.value.trim(); if (v) cb(v); } }]);
    inp.focus(); inp.select();
    inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { var v = inp.value.trim(); if (v) { d.close(); cb(v); } } });
  }


  // ---- paneles que se ocultan con ☰ (se recuerdan en este navegador)
  var PANELS = { sb: "cf_hide_sb", insp: "cf_hide_insp" };
  function panelHidden(k) { try { return localStorage.getItem(PANELS[k]) === "1"; } catch (e) { return !!S["hide_" + k]; } }
  function setPanelHidden(k, v) {
    S["hide_" + k] = v; try { localStorage.setItem(PANELS[k], v ? "1" : "0"); } catch (e) { /* sin almacenamiento */ }
    applyPanels();
  }
  function applyPanels() {
    var sh = document.querySelector(".shell"); if (!sh) return;
    Object.keys(PANELS).forEach(function (k) { sh.classList.toggle("hide-" + k, panelHidden(k)); });
    document.querySelectorAll("[data-panel]").forEach(function (b) {
      var k = b.getAttribute("data-panel"); b.setAttribute("aria-pressed", panelHidden(k) ? "false" : "true");
      b.classList.toggle("on", !panelHidden(k));
    });
    if (S.graphRefresh) { try { S.graphRefresh(); } catch (e) { /* aún no hay grafo */ } }
  }
  function panelBtn(k, title, label) {
    return h("button", { class: "btn sm panel-toggle", "data-panel": k, title: title, "aria-label": title, text: label || "☰",
      onclick: function () { setPanelHidden(k, !panelHidden(k)); } });
  }

  // ============================================================ estructura principal
  var els = {};
  function renderShell() {
    stopPolling();
    var isAdmin = S.user.role === "admin";
    var top = h("div", { class: "topbar" },
      h("button", { class: "panel-toggle", "data-panel": "sb", title: lang === "es" ? "Mostrar u ocultar la lista de workflows" : "Show or hide the workflow list", "aria-label": "Workflows", text: "☰",
        onclick: function () { setPanelHidden("sb", !panelHidden("sb")); } }),
      h("span", { class: "brand" }, h("img", { class: "logo", src: "/static/logo.svg", alt: "" }), "ChaskiFlow"), h("span", { class: "spacer" }),
      h("span", { class: "who", text: (S.user.display_name || S.user.username) + " · " + S.user.role }),
      h("button", { text: "⚙", title: t("settings"), onclick: settingsDialog }),
      h("button", { text: t("logout"), onclick: function () { api("POST", "/api/logout").then(function () { S.user = null; showLogin(); }); } }));
    els.list = h("div", { class: "list" });
    var canCreate = S.user.role !== "viewer";
    function link(ic, label, fn) { return h("button", { class: "sb-link", onclick: fn }, h("span", { class: "ic", text: ic }), h("span", { text: label })); }
    var sbFoot = h("div", { class: "sb-foot" },
      h("div", { class: "sb-sec", text: lang === "es" ? "Mi espacio" : "My space" }),
      link("⏰", t("schedules"), allSchedulesDialog),
      link("🔑", t("secrets"), secretsDialog),
      link("🗑", t("trash"), trashDialog),
      isAdmin ? [h("div", { class: "sb-sec", text: lang === "es" ? "Administración" : "Administration" }),
                 link("🧩", t("plugins"), pluginsDialog),
                 link("👥", t("users"), usersDialog),
                 link("📜", t("audit"), auditDialog)] : null);
    sbFoot.appendChild(aboutLine("about-side"));
    var side = h("div", { class: "sidebar" },
      h("div", { class: "sb-head" },
        canCreate ? h("button", { class: "btn primary", style: "flex:1", text: t("new_wf"), onclick: createWorkflow }) : null,
        canCreate ? h("button", { class: "btn", text: t("import_"), onclick: importDialog }) : null),
      els.list, sbFoot);
    els.main = h("div", { class: "main" });
    clear(root).appendChild(h("div", { class: "shell" }, top, h("div", { class: "body" }, side, els.main)));
    renderList(); renderMain(); applyPanels();
  }

  // logo en línea (sin fondo); el color sigue al tema mediante la clase .logo-svg
  function logoSvg(cls) {
    var NS = "http://www.w3.org/2000/svg";
    function e(tag, attrs) { var n = document.createElementNS(NS, tag); Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); }); return n; }
    var s = e("svg", { viewBox: "0 0 64 64", "class": "logo-svg " + (cls || ""), role: "img", "aria-label": "ChaskiFlow" });
    s.appendChild(e("path", { d: "M9 46C21 46 21 20 33 20S45 44 55 17" }));
    s.appendChild(e("circle", { cx: 9, cy: 46, r: 3.5, "class": "dot" }));
    s.appendChild(e("circle", { cx: 33, cy: 20, r: 3.5, "class": "dot" }));
    s.appendChild(e("circle", { cx: 55, cy: 17, r: 4.5, "class": "dot" }));
    s.appendChild(e("path", { d: "M49 14l6-1-2 6" }));
    return s;
  }
  // créditos: línea discreta + diálogo «Acerca de»
  function aboutText() {
    var a = S.about || {};
    return "ChaskiFlow" + (a.version ? " v" + a.version : "") + " · " + (a.author || "Diego Guevara B.") + " · " + (a.license || "Apache-2.0");
  }
  function aboutLine(cls) {
    return h("button", { class: "about-line " + cls, text: aboutText(), title: lang === "es" ? "Acerca de ChaskiFlow" : "About ChaskiFlow", onclick: aboutDialog });
  }
  function aboutDialog() {
    var a = S.about || {}, es = lang === "es";
    dialog(es ? "Acerca de ChaskiFlow" : "About ChaskiFlow", h("div", null,
      h("div", { style: "display:flex;align-items:center;gap:12px;margin-bottom:10px" },
        logoSvg("about-logo"),
        h("div", null, h("div", { style: "font-weight:600;font-size:16px", text: "ChaskiFlow" }), h("div", { class: "muted", text: "v" + (a.version || "") }))),
      h("div", { text: es ? "Plataforma de workflows con plugins." : "Workflow platform with plugins." }),
      h("table", { style: "margin-top:10px" }, h("tbody", null,
        h("tr", null, h("td", { class: "muted", text: es ? "Autor" : "Author" }), h("td", { text: a.author || "Diego Guevara B." })),
        h("tr", null, h("td", { class: "muted", text: es ? "Contribuciones" : "Contributions" }), h("td", { text: a.contributions || "Claude" })),
        h("tr", null, h("td", { class: "muted", text: es ? "Licencia" : "License" }), h("td", { text: (a.license || "Apache-2.0") + (es ? " (código abierto)" : " (open source)") })))),
      h("div", { class: "muted", style: "margin-top:10px;font-size:12px", text: es
        ? "Copyright 2026 Diego Guevara B. Licenciado bajo la Licencia Apache, Versión 2.0. Los archivos LICENSE y NOTICE están en la carpeta del programa y deben conservarse al redistribuirlo."
        : "Copyright 2026 Diego Guevara B. Licensed under the Apache License, Version 2.0. The LICENSE and NOTICE files in the program folder must be kept when redistributing." })));
  }

  function renderList() {
    clear(els.list);
    if (!S.workflows.length) els.list.appendChild(h("div", { class: "muted", style: "padding:10px", text: t("no_wf") }));
    S.workflows.forEach(function (w) {
      var lr = w.last_run;
      var acts = h("div", { class: "acts" });
      if (w.access === "edit") {
        var mine = S.user.role === "admin" || w.owner_id === S.user.id;
        acts.appendChild(h("button", { class: "btn icon", title: t("rename"), text: "✎", onclick: function (e) { e.stopPropagation(); renameWorkflow(w); } }));
        if (mine) acts.appendChild(h("button", { class: "btn icon", title: t("remove"), text: "✕", onclick: function (e) { e.stopPropagation(); deleteWorkflow(w); } }));
      }
      els.list.appendChild(h("div", { class: "wf-item" + (S.current && S.current.id === w.id ? " active" : ""), onclick: function () { openWorkflow(w.id); } },
        h("span", { class: "dot " + (lr ? lr.status : ""), title: lr ? lr.status : "" }),
        h("div", { class: "nm" }, h("div", { text: w.name }), h("div", { class: "sub", text: w.owner + (w.access !== "edit" ? " · " + t(w.access === "run" ? "run_" : "view") : "") })),
        acts));
    });
  }
  function refreshList() { return api("GET", "/api/workflows").then(function (d) { S.workflows = d.workflows; renderList(); }); }

  function createWorkflow() {
    prompt_(t("new_wf"), t("name"), t("wf_new_name"), function (name) {
      api("POST", "/api/workflows", { name: name, definition: { nodes: [], edges: [], variables: {} } }).then(function (d) {
        return refreshList().then(function () { openWorkflow(d.workflow.id); });
      }, function (e) { toast(e.message); });
    });
  }
  function renameWorkflow(w) {
    prompt_(t("rename"), t("name"), w.name, function (name) {
      api("GET", "/api/workflows/" + w.id).then(function (d) {
        return api("PUT", "/api/workflows/" + w.id, { name: name, version: d.workflow.version });
      }).then(function () { if (S.current && S.current.id === w.id) S.current.name = name; return refreshList(); })
        .then(function () { if (S.current && S.current.id === w.id) renderMain(); }, function (e) { toast(e.message); });
    });
  }
  function deleteWorkflow(w) {
    api("DELETE", "/api/workflows/" + w.id).then(function (d) {
      if (S.current && S.current.id === w.id) { S.current = null; stopPolling(); renderMain(); }
      refreshList();
      toast(t("deleted") + ": " + w.name, t("undo"), function () {
        api("POST", "/api/workflows/" + w.id + "/restore").then(refreshList, function (e) { toast(e.message); });
      }, 9000);
    }, function (e) { toast(e.message); });
  }
  function trashDialog() {
    var es = lang === "es";
    var body = h("div", { text: "…" });
    var d = dialog(t("trash"), body, [{ label: t("close") }, { label: es ? "Vaciar papelera" : "Empty trash", cls: "danger", keep: true, fn: function () {
      confirm_(es ? "Vaciar papelera" : "Empty trash", es
        ? "Se eliminarán para siempre todos los workflows de la papelera, con sus ejecuciones y programaciones. No se puede deshacer."
        : "All workflows in the trash will be permanently deleted with their runs and schedules. This cannot be undone.",
        es ? "Eliminar todo" : "Delete all", function () {
          api("POST", "/api/workflows/trash/empty").then(function (r) {
            toast((es ? "Eliminados definitivamente: " : "Permanently deleted: ") + r.purged + (r.skipped ? " · " + (es ? "omitidos: " : "skipped: ") + r.skipped : ""));
            draw();
          }, function (e) { toast(e.message); });
        });
      return false; } }]);
    function draw() {
      api("GET", "/api/workflows/trash").then(function (r) {
        clear(body);
        if (!r.workflows.length) body.appendChild(h("div", { class: "muted", text: es ? "La papelera está vacía." : "Trash is empty." }));
        body.appendChild(h("div", { class: "muted", style: "font-size:12px;margin-bottom:6px", text: es
          ? "«Eliminar definitivamente» borra el workflow con su historial de ejecuciones y programaciones." : "“Delete permanently” removes the workflow with its run history and schedules." }));
        r.workflows.forEach(function (w) {
          body.appendChild(h("div", { style: "display:flex;gap:8px;align-items:center;padding:4px 0" },
            h("span", { style: "flex:1", text: w.name + " · " + fmtDate(w.deleted_at) }),
            h("button", { class: "btn sm", text: t("restore"), onclick: function () {
              api("POST", "/api/workflows/" + w.id + "/restore").then(function () { draw(); refreshList(); }, function (e) { toast(e.message); }); } }),
            h("button", { class: "btn sm danger", text: es ? "Eliminar definitivamente" : "Delete permanently", onclick: function () {
              confirm_(es ? "Eliminar definitivamente" : "Delete permanently", (es ? "¿Eliminar para siempre «" : "Permanently delete “") + w.name + (es ? "» y su historial? No se puede deshacer." : "” and its history? This cannot be undone."),
                es ? "Eliminar" : "Delete", function () {
                  api("DELETE", "/api/workflows/" + w.id + "/purge").then(function () { draw(); }, function (e) { toast(e.message); }); }); } })));
        });
      }, function (e) { clear(body); body.appendChild(h("div", { text: e.message })); });
    }
    draw();
  }
  function importDialog() {
    var ta = h("textarea", { rows: 14, placeholder: "{ \"name\": \"...\", \"nodes\": [...], \"edges\": [...] }" });
    var file = h("input", { type: "file", accept: ".json,application/json", onchange: function () {
      var f = file.files[0]; if (!f) return; var r = new FileReader(); r.onload = function () { ta.value = r.result; }; r.readAsText(f); } });
    dialog(t("import_"), h("div", null, file, h("div", { style: "height:8px" }), ta), [{ label: t("cancel") },
      { label: t("import_"), cls: "primary", keep: true, fn: function (close) {
        var def; try { def = JSON.parse(ta.value); } catch (e) { toast(t("invalid_json")); return false; }
        api("POST", "/api/workflows/import", { name: def.name, definition: def }).then(function (d) {
          close(); return refreshList().then(function () {
            openWorkflow(d.workflow.id);
            if (d.import_report) importReport(d.import_report);
          });
        }, function (e) { toast(e.message); });
      } }], true);
  }
  function importReport(rep) {
    var box = h("div", { class: "imp-report" });
    rep.forEach(function (r) {
      box.appendChild(h("div", { class: "imp-row " + r.level },
        h("b", { text: (r.level === "warn" ? "⚠ " : r.level === "error" ? "✖ " : "• ") + (r.node ? r.node + ": " : "") }),
        h("span", { text: r.message })));
    });
    dialog(t("import_report"), box, [{ label: t("close") }], true);
  }

  // ============================================================ abrir y guardar
  function openWorkflow(id) {
    flushSave();
    stopPolling();
    api("GET", "/api/workflows/" + id).then(function (d) {
      var w = d.workflow;
      S.current = { id: w.id, name: w.name, description: w.description, version: w.version, access: w.access, owner_id: w.owner_id,
                    owner: w.owner, team_access: w.team_access, shares: w.shares, def: w.definition, problems: null };
      S.saveState = "saved"; S.conflict = false; S.tab = "graph"; S.live = null; S.viewRun = null; S.runs = []; S.selRun = null; S.dkSel = null; S.dkAuto = true;
      renderList(); renderMain();
      loadRuns();
    }, function (e) { toast(e.message); });
  }
  function closeWorkflow() {
    flushSave(); stopPolling();
    S.current = null; S.live = null; S.viewRun = null; S.runs = []; S.selRun = null; S.conflict = false;
    document.title = "ChaskiFlow";
    renderList(); renderMain();
  }
  // estado de un paso para pintar el grafo: en Editor, la ejecución en vivo; en Ejecuciones, la ejecución elegida de la lista
  function runStatusOf(id) {
    var src = runSrc(); if (!src) return "";
    if (src.kind === "live") return src.L.nodes[id] ? src.L.nodes[id].status : "";
    var ns = src.run.nodes || [];
    for (var i = 0; i < ns.length; i++) if (ns[i].node_id === id) return ns[i].status || "";
    return "";
  }
  function canEdit() { return S.current && S.current.access === "edit" && S.user.role !== "viewer"; }
  function canRun() { return S.current && (S.current.access === "edit" || S.current.access === "run") && S.user.role !== "viewer"; }

  var saveSoon = debounce(doSave, 1200);
  function touch() {
    if (!canEdit() || S.conflict) return;
    S.saveState = "dirty"; updateSaveState(); saveSoon();
  }
  var saving = false, pendingSave = false;
  function flushSave() { if (S.saveState === "dirty") doSave(); }
  function doSave() {
    if (!S.current || S.conflict) return;
    if (saving) { pendingSave = true; return; }
    saving = true; S.saveState = "saving"; updateSaveState();
    var w = S.current;
    api("PUT", "/api/workflows/" + w.id, { definition: w.def, version: w.version }).then(function (d) {
      w.version = d.workflow.version; saving = false;
      if (pendingSave) { pendingSave = false; S.saveState = "dirty"; doSave(); return; }
      S.saveState = "saved"; updateSaveState(); w.problems = null;
    }, function (e) {
      saving = false;
      if (S.current !== w) return;
      if (e.status === 409) { S.conflict = true; S.saveState = "conflict"; renderMain(); }
      else { S.saveState = "error"; updateSaveState(e.message); }
    });
  }
  function updateSaveState(msg) {
    var el = document.getElementById("savestate"); if (!el) return;
    var m = { saved: t("saved"), saving: t("saving"), dirty: t("unsaved"), error: msg || "Error", conflict: t("conflict") };
    el.textContent = m[S.saveState] || ""; el.className = "savestate" + (S.saveState === "error" || S.saveState === "conflict" ? " err" : "");
  }

  // ============================================================ vista del workflow
  function renderMain() {
    stopPolling(true); S.gkey = null;
    clear(els.main);
    var w = S.current;
    if (!w) {
      els.main.appendChild(h("div", { class: "empty" }, h("h2", { text: t("pick_wf") }), h("div", { text: t("pick_hint") })));
      return;
    }
    document.title = w.name + " · ChaskiFlow";
    var title = h("input", { class: "title", type: "text", value: w.name, disabled: !canEdit(), onchange: function () {
      var v = title.value.trim(); if (!v) { title.value = w.name; return; }
      api("PUT", "/api/workflows/" + w.id, { name: v, version: w.version }).then(function (d) { w.name = v; w.version = d.workflow.version; refreshList(); },
        function (e) { if (e.status === 409) { S.conflict = true; renderMain(); } else toast(e.message); }); } });
    var runBtn = h("button", { class: "btn primary", id: "runbtn", text: t("run"), disabled: !canRun(), onclick: function () { startRun(); } });
    var stopBtn = h("button", { class: "btn danger hidden", id: "stopbtn", text: t("stop"), onclick: cancelRun });
    var bar = h("div", { class: "wf-bar" }, title,
      h("span", { id: "savestate", class: "savestate" }),
      h("span", { class: "grow" }),
      !canEdit() ? h("span", { class: "badge", text: t("readonly") }) : null,
      h("button", { class: "btn", text: t("validate"), onclick: validate }),
      runBtn, stopBtn,
      h("button", { class: "btn", text: "⋯", title: t("details"), onclick: moreMenu }),
      h("button", { class: "btn icon close-wf", text: "✕", title: lang === "es" ? "Cerrar este workflow" : "Close this workflow",
        "aria-label": lang === "es" ? "Cerrar workflow" : "Close workflow", onclick: closeWorkflow }));
    var tabs = h("div", { class: "tabs" },
      h("button", { class: "tab" + (S.tab === "graph" ? " active" : ""), text: t("graph"), onclick: function () { S.tab = "graph"; renderMain(); } }),
      h("button", { class: "tab" + (S.tab === "runs" ? " active" : ""), text: t("runs"), onclick: function () { S.tab = "runs"; renderMain(); } }),
      h("span", { class: "grow", style: "flex:1" }));
    els.editor = h("div", { class: "editor" });
    els.dock = h("div", { class: "logdock" });
    els.main.appendChild(bar); els.main.appendChild(tabs);
    if (S.tab === "runs") {
      els.runlist = h("div", { class: "runlist" });
      els.main.appendChild(h("div", { class: "content runsview" }, els.runlist, h("div", { class: "runright" }, els.editor, els.dock)));
    } else {
      els.runlist = null;
      els.main.appendChild(h("div", { class: "content col" }, els.editor, els.dock));
    }
    if (S.conflict) {
      els.editor.appendChild(h("div", { class: "banner err" }, h("span", { text: t("conflict") + " " }),
        h("button", { class: "btn sm", text: t("reload"), onclick: function () { openWorkflow(w.id); } })));
    }
    if (S.tab === "runs") { renderGraph(els.editor, true); autoSelectRun(); } else renderGraph();
    renderRunPane();
    updateSaveState();
    applyPanels();
    if (S.live && !S.live.done) { setRunning(true); poll(); }
  }

  function moreMenu() {
    var w = S.current;
    var items = [
      { label: t("share"), show: canEdit() && (S.user.role === "admin" || w.owner_id === S.user.id), fn: shareDialog },
      { label: "⏰ " + t("schedule"), show: canRun(), fn: scheduleDialog },
      { label: t("duplicate"), show: S.user.role !== "viewer", fn: function () {
        api("POST", "/api/workflows/" + w.id + "/duplicate").then(function (d) { return refreshList().then(function () { openWorkflow(d.workflow.id); }); }, function (e) { toast(e.message); }); } },
      { label: t("export_"), show: true, fn: function () {
        api("GET", "/api/workflows/" + w.id + "/export").then(function (d) { downloadJson(d, (w.name || "workflow") + ".json"); }, function (e) { toast(e.message); }); } }
    ].filter(function (i) { return i.show; });
    var body = h("div", { style: "display:flex;flex-direction:column;gap:8px" });
    var dlg = dialog(w.name, body);
    items.forEach(function (i) { body.appendChild(h("button", { class: "btn", text: i.label, onclick: function () { dlg.close(); i.fn(); } })); });
  }
  function downloadJson(obj, name) {
    var blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
    var a = h("a", { href: URL.createObjectURL(blob), download: name.replace(/[\\/:*?"<>|]/g, "_") });
    document.body.appendChild(a); a.click(); a.remove();
  }

  // ---------------------------------------------------------------- pasos
  function nodeIds() { return S.current.def.nodes.map(function (n) { return n.id; }); }
  function ancestors(id) {
    var preds = {}; S.current.def.edges.forEach(function (e) { (preds[e.target] = preds[e.target] || []).push(e.source); });
    var seen = {}, stack = (preds[id] || []).slice();
    while (stack.length) { var x = stack.pop(); if (seen[x]) continue; seen[x] = 1; (preds[x] || []).forEach(function (y) { stack.push(y); }); }
    return seen;
  }
  function descendants(id) {
    var succ = {}; S.current.def.edges.forEach(function (e) { (succ[e.source] = succ[e.source] || []).push(e.target); });
    var seen = {}, stack = (succ[id] || []).slice();
    while (stack.length) { var x = stack.pop(); if (seen[x]) continue; seen[x] = 1; (succ[x] || []).forEach(function (y) { stack.push(y); }); }
    return seen;
  }
  function newNodeId() {
    var ids = nodeIds(), i = 1; while (ids.indexOf("n" + i) >= 0) i++; return "n" + i;
  }
  function uniqueLabel(base) {
    var labels = S.current.def.nodes.map(function (n) { return n.label; }), l = base, i = 2;
    while (labels.indexOf(l) >= 0) l = base + i++;
    return l;
  }
  function labelOf(n) { return n.label || n.id; }

  // ---------------------------------------------------------------- copiar / pegar / duplicar pasos
  // El paso se pega SIN conexiones. Las plantillas {{Paso.result...}} que apuntan a otros pasos se vacían (no hay
  // a qué referirse sin la conexión); {{vars.x}} se conserva y la variable se crea en el workflow destino si falta.
  var clip = null;
  function clipLoad() {
    if (clip) return clip;
    try { var raw = window.localStorage.getItem("cf_clip"); if (raw) clip = JSON.parse(raw); } catch (e) { clip = null; }
    return clip;
  }
  function clipCopy(n) {
    var def = S.current.def, vars = {};
    clip = { wf: S.current.id, node: JSON.parse(JSON.stringify({ label: n.label, type: n.type, config: n.config || {}, on_error: n.on_error || "stop",
              enabled: n.enabled !== false, })), pos: n.position, vars: {} };
    Object.keys(def.variables || {}).forEach(function (k) { vars[k] = def.variables[k]; });
    clip.vars = vars;
    try { window.localStorage.setItem("cf_clip", JSON.stringify(clip)); } catch (e) { /* sin almacenamiento: queda en memoria */ }
  }
  function scrubRefs(value, st) {
    if (typeof value === "string") {
      return value.replace(/\{\{([\s\S]*?)\}\}/g, function (m, expr) {
        var root = expr.trim().split(/[.\[|\s]/)[0];
        if (root === "vars") { var mm = /vars\.([^.\[|\s}]+)/.exec(expr); if (mm) st.vars[mm[1]] = 1; return m; }
        st.removed++; return "";
      });
    }
    if (Array.isArray(value)) return value.map(function (v) { return scrubRefs(v, st); });
    if (value && typeof value === "object") { var o = {}; Object.keys(value).forEach(function (k) { o[k] = scrubRefs(value[k], st); }); return o; }
    return value;
  }
  // pos = punto del grafo donde pegar (opcional); duplicate = pegar junto al original
  function clipPaste(pos, around) {
    var c = clipLoad(), w = S.current, def = w && w.def;
    if (!c || !def || !canEdit()) return null;
    if (!S.pmap[c.node.type]) { toast(lang === "es" ? "Ese tipo de paso no está disponible en este servidor" : "That step type is not available"); return null; }
    var st = { removed: 0, vars: {} }, cfg = scrubRefs(c.node.config, st), addedVars = [];
    def.variables = def.variables || {};
    Object.keys(st.vars).forEach(function (k) { if (!(k in def.variables) && k in (c.vars || {})) { def.variables[k] = c.vars[k]; addedVars.push(k); } });
    var node = { id: newNodeId(), label: uniqueLabel(c.node.label || "Paso"), type: c.node.type, config: cfg, on_error: c.node.on_error || "stop",
                 enabled: c.node.enabled !== false, position: { x: 0, y: 0 } };
    var p = pos || (around ? { x: around.x + 40, y: around.y + NH + 30 } : { x: c.pos ? c.pos.x + 40 : 40, y: c.pos ? c.pos.y + NH + 30 : 40 });
    p = { x: Math.round(p.x), y: Math.round(p.y) };
    var busy = function () { return def.nodes.some(function (o) { return Math.abs(o.position.x - p.x) < NW && Math.abs(o.position.y - p.y) < NH + 10; }); };
    while (busy()) p.y += NH + 30;
    node.position = p;
    def.nodes.push(node);
    S.gv.sel = node.id; S.gv.selEdge = null; S.collapsed[node.id] = false;
    touch(); renderMain();
    var es = lang === "es", msg = (es ? "Pegado «" : "Pasted «") + node.label + (es ? "» sin conexiones." : "» without connections.");
    if (st.removed) msg += es ? " Se vaciaron " + st.removed + " referencia(s) a otros pasos: conéctelo y elíjalas de nuevo." : " " + st.removed + " reference(s) to other steps were cleared: connect it and choose them again.";
    if (addedVars.length) msg += es ? " Variable(s) agregada(s): " + addedVars.join(", ") + "." : " Variable(s) added: " + addedVars.join(", ") + ".";
    toast(msg, t("undo"), function () {
      var d2 = S.current && S.current.def; if (!d2) return;
      d2.nodes = d2.nodes.filter(function (o) { return o.id !== node.id; });
      addedVars.forEach(function (k) { delete d2.variables[k]; });
      S.gv.sel = null; touch(); renderMain();
    }, st.removed ? 12000 : 7000);
    return node;
  }
  var ctxCleanup = null;
  function closeCtxMenu() { if (ctxCleanup) { ctxCleanup(); ctxCleanup = null; } var m = document.getElementById("ctxmenu"); if (m) m.remove(); }
  // selector de pasos con búsqueda: lista agrupada por categoría, flechas + Enter, o clic
  function stepPicker(ev, onPick, extra) {
    closeCtxMenu();
    var es = lang === "es", m = h("div", { class: "ctxmenu picker", id: "ctxmenu", role: "menu" });
    var q = h("input", { type: "search", placeholder: es ? "Buscar paso…" : "Search step…", autocomplete: "off", "aria-label": es ? "Buscar paso" : "Search step" });
    var list = h("div", { class: "pk-list" }), cur = 0, shown = [];
    var plugins = S.plugins.filter(function (p) { return p.ok && p.status === "enabled"; });
    function pick(p) { closeCtxMenu(); onPick(p); }
    function draw() {
      clear(list); shown = [];
      var f = q.value.trim().toLowerCase(), cats = {};
      plugins.forEach(function (p) {
        var hay = (p.name + " " + p.id + " " + (p.category || "") + " " + (p.description || "")).toLowerCase();
        if (!f || f.split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; })) (cats[p.category || ""] = cats[p.category || ""] || []).push(p);
      });
      Object.keys(cats).sort().forEach(function (c) {
        if (c) list.appendChild(h("div", { class: "pk-cat", text: c }));
        cats[c].forEach(function (p) {
          var i = shown.length; shown.push(p);
          var b = h("button", { class: "mi pk-item" + (i === cur ? " cur" : ""), role: "menuitem", onclick: function (e) { e.stopPropagation(); pick(p); } },
            h("span", { class: "pk-ic", text: p.icon || "🧩" }),
            h("span", { class: "pk-tx" }, h("span", { text: p.name }), h("small", { class: "muted", text: (p.description || "").slice(0, 80) })));
          b.addEventListener("pointermove", function () { if (cur !== i) { cur = i; mark(); } });
          list.appendChild(b);
        });
      });
      if (!shown.length) list.appendChild(h("div", { class: "muted", style: "padding:10px", text: es ? "Ningún paso coincide." : "No matching step." }));
    }
    function mark() {
      var items = list.querySelectorAll(".pk-item");
      for (var i = 0; i < items.length; i++) items[i].classList.toggle("cur", i === cur);
      if (items[cur] && items[cur].scrollIntoView) items[cur].scrollIntoView({ block: "nearest" });
    }
    q.addEventListener("input", function () { cur = 0; draw(); });
    q.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); if (shown.length) { cur = (cur + 1) % shown.length; mark(); } }
      else if (e.key === "ArrowUp") { e.preventDefault(); if (shown.length) { cur = (cur - 1 + shown.length) % shown.length; mark(); } }
      else if (e.key === "Enter") { e.preventDefault(); if (shown[cur]) pick(shown[cur]); }
    });
    m.appendChild(q); m.appendChild(list); draw();
    (extra || []).forEach(function (it) {
      var b = h("button", { class: "mi", role: "menuitem", disabled: it.disabled ? "disabled" : null }, h("span", { text: it.label }), it.key ? h("span", { class: "k", text: it.key }) : null);
      b.addEventListener("click", function (e) { e.stopPropagation(); closeCtxMenu(); if (!it.disabled) it.fn(); });
      m.appendChild(b);
    });
    mountCtx(ev, m); q.focus();
  }
  function showCtxMenu(ev, items) {
    closeCtxMenu();
    var m = h("div", { class: "ctxmenu", id: "ctxmenu", role: "menu" });
    items.forEach(function (it) {
      if (it === "-") { m.appendChild(h("div", { class: "sep" })); return; }
      var b = h("button", { class: "mi" + (it.danger ? " danger" : ""), role: "menuitem", disabled: it.disabled ? "disabled" : null }, h("span", { text: it.label }), it.key ? h("span", { class: "k", text: it.key }) : null);
      b.addEventListener("click", function (e) { e.stopPropagation(); closeCtxMenu(); if (!it.disabled) it.fn(); });
      m.appendChild(b);
    });
    mountCtx(ev, m);
  }
  function mountCtx(ev, m) {
    document.body.appendChild(m);
    var r = m.getBoundingClientRect();
    m.style.left = Math.max(4, Math.min(ev.clientX, window.innerWidth - r.width - 4)) + "px";
    m.style.top = Math.max(4, Math.min(ev.clientY, window.innerHeight - r.height - 4)) + "px";
    setTimeout(function () {
      if (!m.parentNode) return;
      var down = function (e) { if (!m.contains(e.target)) closeCtxMenu(); };
      var esc = function (e) { if (e.key === "Escape") closeCtxMenu(); };
      document.addEventListener("pointerdown", down, true); document.addEventListener("keydown", esc, true); window.addEventListener("blur", closeCtxMenu);
      ctxCleanup = function () { document.removeEventListener("pointerdown", down, true); document.removeEventListener("keydown", esc, true); window.removeEventListener("blur", closeCtxMenu); };
    }, 0);
  }
  document.addEventListener("keydown", function (ev) {
    if (!S.gkey || !(ev.ctrlKey || ev.metaKey) || ev.altKey) return;
    var t0 = ev.target, tag = t0 && t0.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t0 && t0.isContentEditable)) return;
    if (document.querySelector(".overlay")) return;
    S.gkey(ev);
  });

  // panel de variables del workflow (se muestra en el inspector cuando no hay nodo seleccionado)
  function varsPanel() {
    var def = S.current.def;
    var vars = h("details", { class: "vars card" });
    var vkeys = Object.keys(def.variables || {});
    vars.appendChild(h("summary", { style: "padding:10px 14px;cursor:pointer", text: t("variables") + " (" + vkeys.length + ")" }));
    var vbody = h("div", { style: "padding:0 14px 12px" });
    vkeys.forEach(function (k) {
      var kin = h("input", { type: "text", value: k, disabled: !canEdit() });
      var vin = h("input", { type: "text", value: typeof def.variables[k] === "string" ? def.variables[k] : JSON.stringify(def.variables[k]), disabled: !canEdit() });
      kin.addEventListener("change", function () {
        var nk = kin.value.trim(); if (!nk || nk === k) { kin.value = k; return; }
        var val = def.variables[k]; delete def.variables[k]; def.variables[nk] = val; touch(); renderMain();
      });
      vin.addEventListener("input", function () { def.variables[k] = vin.value; touch(); });
      vbody.appendChild(h("div", { class: "vrow" }, kin, vin,
        canEdit() ? h("button", { class: "btn icon", text: "✕", onclick: function () { delete def.variables[k]; touch(); renderMain(); } }) : h("span")));
    });
    if (canEdit()) vbody.appendChild(h("button", { class: "btn sm", style: "margin-top:8px", text: t("add_var"), onclick: function () {
      var k = "var", i = 1; while (k in def.variables) k = "var" + (++i); def.variables[k] = ""; touch(); renderMain(); } }));
    vars.appendChild(vbody);
    vars.open = S.varsOpen !== false;
    vars.addEventListener("toggle", function () { S.varsOpen = vars.open; });
    return vars;
  }

  function stepCard(n, idx) {
    var def = S.current.def, p = S.pmap[n.type], edit = canEdit();
    var card = h("div", { class: "card" + (n.enabled === false ? " disabled" : ""), "data-node": n.id });
    var open = S.collapsed[n.id] === false;
    var body = h("div", { class: "cb" + (open ? "" : " hidden") });
    var lbl = h("input", { class: "lbl", type: "text", value: n.label || n.id, disabled: !edit, onclick: function (e) { e.stopPropagation(); } });
    lbl.addEventListener("change", function () { renameNode(n, lbl.value.trim()); });
    var head = h("div", { class: "ch", onclick: function () { S.collapsed[n.id] = open ? true : false; renderMain(); } },
      h("span", { class: "ic", text: p ? (p.icon || "🧩") : "⚠" }), lbl,
      h("span", { class: "type", text: p ? p.name : n.type + " (no disponible)" }),
      edit ? h("button", { class: "btn icon", text: "↑", title: "↑", disabled: idx === 0, onclick: function (e) { e.stopPropagation(); moveNode(idx, -1); } }) : null,
      edit ? h("button", { class: "btn icon", text: "↓", title: "↓", disabled: idx === def.nodes.length - 1, onclick: function (e) { e.stopPropagation(); moveNode(idx, 1); } }) : null,
      edit ? h("button", { class: "btn icon", text: "✕", title: t("remove"), onclick: function (e) { e.stopPropagation(); removeNode(n); } }) : null);
    card.appendChild(head);

    if (open) {
      if (p && p.description) body.appendChild(h("div", { class: "muted", style: "margin-top:8px", text: p.description }));
      // dependencias
      var anc = ancestors(n.id), desc = descendants(n.id);
      var deps = h("div", { class: "deps" }, h("b", { text: t("depends") + ":" }));
      var others = def.nodes.filter(function (o) { return o.id !== n.id && !desc[o.id]; });
      if (!others.length) deps.appendChild(h("span", { class: "muted", text: "—" }));
      others.forEach(function (o) {
        var direct = def.edges.some(function (e) { return e.source === o.id && e.target === n.id; });
        deps.appendChild(h("label", { class: "chk" }, h("input", { type: "checkbox", checked: direct, disabled: !edit, onchange: function (ev) {
          if (ev.target.checked) def.edges.push({ source: o.id, target: n.id });
          else def.edges = def.edges.filter(function (e) { return !(e.source === o.id && e.target === n.id); });
          touch(); renderMain(); } }), h("span", { text: labelOf(o) })));
      });
      body.appendChild(deps);
      // campos
      var fields = h("div");
      var adv = h("details", { style: "margin-top:10px" }, h("summary", { class: "muted", style: "cursor:pointer", text: t("advanced") }));
      var advCount = 0, testPlaced = false;
      if (p) {
        (p.fields || []).forEach(function (f) {
          if (f.hidden) return;
          var fe = fieldEditor(n, f, edit);
          if (f.advanced) { adv.appendChild(fe); advCount++; } else fields.appendChild(fe);
          if (p.test && edit && f.key === (p.test.after || "model") && !f.advanced) { fields.appendChild(testBox(n, p)); testPlaced = true; }
        });
        body.appendChild(fields);
        if (p.test && edit && !testPlaced) body.appendChild(testBox(n, p));
        if (advCount) body.appendChild(adv);
        (p.secrets || []).length && body.appendChild(h("div", { class: "muted", style: "margin-top:8px;font-size:12px", text: "🔑 " + t("secrets") + ": " +
          p.secrets.map(function (s) { return typeof s === "string" ? s : s.name; }).join(", ") }));
      } else {
        body.appendChild(h("div", { class: "banner err", style: "margin-top:10px", text: "Plugin '" + n.type + "' no disponible o no aprobado." }));
      }
      // referencias
      var anc2 = Object.keys(anc).map(function (id) { return def.nodes.filter(function (x) { return x.id === id; })[0]; }).filter(Boolean);
      if (edit && anc2.length) {
        var refs = h("details", { class: "refs" }, h("summary", { text: t("refs") }));
        var chips = h("div", { class: "refchips" });
        anc2.forEach(function (a) {
          var ap = S.pmap[a.type];
          var outs = ap && ap.outputs && ap.outputs.length ? ap.outputs.map(function (o) { return o.key; }) : [];
          chips.appendChild(h("span", { class: "chip", text: "{{" + labelOf(a) + ".result}}", onclick: function () { insertRef("{{" + labelOf(a) + ".result}}"); } }));
          outs.forEach(function (k) { chips.appendChild(h("span", { class: "chip", text: "{{" + labelOf(a) + ".result." + k + "}}", onclick: function () { insertRef("{{" + labelOf(a) + ".result." + k + "}}"); } })); });
        });
        Object.keys(def.variables || {}).forEach(function (k) { chips.appendChild(h("span", { class: "chip", text: "{{vars." + k + "}}", onclick: function () { insertRef("{{vars." + k + "}}"); } })); });
        refs.appendChild(chips); body.appendChild(refs);
      }
      // opciones del paso
      body.appendChild(h("div", { style: "display:flex;gap:16px;margin-top:12px;align-items:center;flex-wrap:wrap" },
        h("label", { class: "chk" }, h("input", { type: "checkbox", checked: n.enabled !== false, disabled: !edit, onchange: function (ev) { n.enabled = ev.target.checked; touch(); renderMain(); } }), h("span", { text: t("enabled") })),
        h("label", { class: "chk" }, h("span", { text: t("on_error") + ":" }),
          h("select", { style: "width:auto", disabled: !edit, onchange: function (ev) { n.on_error = ev.target.value; touch(); } },
            h("option", { value: "stop", text: t("stop_all"), selected: (n.on_error || "stop") === "stop" }),
            h("option", { value: "continue", text: t("continue_"), selected: n.on_error === "continue" })))));
    }
    card.appendChild(body);
    return card;
  }

  var lastFocus = null;
  document.addEventListener("focusin", function (e) {
    var el = e.target;
    if ((el.tagName === "INPUT" && el.type === "text") || el.tagName === "TEXTAREA") if (el.dataset && el.dataset.ref) lastFocus = el;
  });
  function insertRef(text) {
    var el = lastFocus && document.body.contains(lastFocus) ? lastFocus : null;
    if (!el) { toast(lang === "es" ? "Haga clic primero en el campo donde quiere insertarla" : "Click the target field first"); return; }
    var s = el.selectionStart == null ? el.value.length : el.selectionStart, e = el.selectionEnd == null ? s : el.selectionEnd;
    el.value = el.value.slice(0, s) + text + el.value.slice(e);
    el.selectionStart = el.selectionEnd = s + text.length;
    el.dispatchEvent(new Event("input", { bubbles: true })); el.focus();
  }

  function renameNode(n, nl) {
    if (!nl) { renderMain(); return; }
    var old = n.label;
    if (nl === old) return;
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(nl)) { toast(lang === "es" ? "El nombre del paso solo admite letras, números y _ (sin espacios) para poder referenciarlo" : "Step name: letters, digits and _ only"); renderMain(); return; }
    if (S.current.def.nodes.some(function (o) { return o !== n && o.label === nl; })) { toast(lang === "es" ? "Ya existe un paso con ese nombre" : "Name already used"); renderMain(); return; }
    n.label = nl;
    // actualizar referencias {{Viejo.…}} en los demás pasos
    var rx = new RegExp("\\{\\{\\s*" + old.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\.", "g");
    function walk(v) {
      if (typeof v === "string") return v.replace(rx, "{{" + nl + ".");
      if (Array.isArray(v)) return v.map(walk);
      if (v && typeof v === "object") { var o = {}; Object.keys(v).forEach(function (k) { o[k] = walk(v[k]); }); return o; }
      return v;
    }
    S.current.def.nodes.forEach(function (o) { o.config = walk(o.config); });
    touch(); renderMain();
  }
  function moveNode(i, d) {
    var a = S.current.def.nodes, j = i + d; if (j < 0 || j >= a.length) return;
    var x = a[i]; a[i] = a[j]; a[j] = x; touch(); renderMain();
  }
  function removeNode(n) {
    var def = S.current.def;
    def.nodes = def.nodes.filter(function (o) { return o !== n; });
    var preds = def.edges.filter(function (e) { return e.target === n.id; }).map(function (e) { return e.source; });
    var succs = def.edges.filter(function (e) { return e.source === n.id; }).map(function (e) { return e.target; });
    def.edges = def.edges.filter(function (e) { return e.source !== n.id && e.target !== n.id; });
    preds.forEach(function (a) { succs.forEach(function (b) { if (!def.edges.some(function (e) { return e.source === a && e.target === b; })) def.edges.push({ source: a, target: b }); }); });
    touch(); renderMain();
  }

  // ---------------------------------------------------------------- campos generados
  // botón «Probar conexión» de los plugins que declaran "test" en plugin.json
  function testBox(n, p) {
    var out = h("div", { class: "testout hidden" });
    var btn = h("button", { class: "btn sm", text: "🔌 " + ((p.test && p.test.label) || "Probar conexión") });
    btn.addEventListener("click", function () {
      btn.disabled = true; btn.textContent = "⏳ Probando…";
      out.className = "testout"; out.textContent = "";
      api("POST", "/api/plugins/" + encodeURIComponent(p.id) + "/test", { config: n.config, variables: S.current.def.variables || {} }).then(function (d) {
        btn.disabled = false; btn.textContent = "🔌 " + ((p.test && p.test.label) || "Probar conexión");
        out.className = "testout " + (d.ok ? "ok" : "bad");
        out.appendChild(h("div", { class: "tt", text: (d.ok ? "✔ " : "✖ ") + (d.ok ? (d.message || "Prueba correcta") : (d.error || d.message || "La prueba falló")) }));
        if (d.logs && d.logs.length) out.appendChild(h("pre", { text: d.logs.join("\n") }));
        if (out.scrollIntoView) out.scrollIntoView({ block: "nearest" });
      }, function (e) {
        btn.disabled = false; btn.textContent = "🔌 " + ((p.test && p.test.label) || "Probar conexión");
        out.className = "testout bad"; out.appendChild(h("div", { class: "tt", text: "✖ " + e.message }));
      });
    });
    return h("div", { class: "testbox" }, btn, out);
  }

  function fieldEditor(n, f, edit) {
    var key = f.key, cfg = n.config, type = f.type || "string";
    var has = Object.prototype.hasOwnProperty.call(cfg, key);
    var cur = has ? cfg[key] : f.default;
    function setVal(v, remove) { if (remove) delete cfg[key]; else cfg[key] = v; touch(); }
    var input;
    if (type === "boolean") {
      input = h("label", { class: "chk" }, h("input", { type: "checkbox", checked: cur === true || cur === "true", disabled: !edit,
        onchange: function (ev) { setVal(ev.target.checked); } }), h("span", { text: f.label || key }));
      var wrap = h("div", { class: "field" }, input);
      if (f.help) wrap.appendChild(h("div", { class: "help", text: f.help }));
      return wrap;
    }
    if (type === "select") {
      var opts = (f.options || []).map(function (o) { var v = typeof o === "object" ? o.value : o, l = typeof o === "object" ? (o.label || o.value) : o;
        return h("option", { value: v, text: l, selected: String(cur) === String(v) }); });
      input = h("select", { disabled: !edit, onchange: function (ev) { setVal(ev.target.value); } }, opts);
    } else if (type === "text" || type === "json" || type === "any") {
      var txt = cur === undefined || cur === null ? "" : (typeof cur === "string" ? cur : JSON.stringify(cur, null, 2));
      input = h("textarea", { rows: type === "text" ? 4 : 3, value: txt, disabled: !edit, "data-ref": "1", placeholder: f.placeholder || "" });
      input.addEventListener("input", function () {
        var v = input.value;
        if (v.trim() === "") { input.classList.remove("invalid"); setVal(null, true); return; }
        if (type === "json") {
          if (/^\s*\{\{.*\}\}\s*$/s.test(v)) { input.classList.remove("invalid"); setVal(v); return; }
          try { setVal(JSON.parse(v)); input.classList.remove("invalid"); } catch (e) { input.classList.add("invalid"); }
        } else if (type === "any" && /^\s*[\[{]/.test(v) && !/^\s*\{\{/.test(v)) {
          try { setVal(JSON.parse(v)); input.classList.remove("invalid"); } catch (e) { input.classList.add("invalid"); }
        } else { input.classList.remove("invalid"); setVal(v); }
      });
    } else if (type === "number") {
      input = h("input", { type: "text", value: cur === undefined || cur === null ? "" : String(cur), disabled: !edit, "data-ref": "1", placeholder: f.placeholder || "" });
      input.addEventListener("input", function () {
        var v = input.value.trim();
        if (v === "") { setVal(null, true); return; }
        setVal(v !== "" && !isNaN(Number(v)) && !/\{\{/.test(v) ? Number(v) : v);
      });
    } else if (type === "secret") {
      var listId = "sec-" + n.id + "-" + key;
      var dl = h("datalist", { id: listId });
      input = h("input", { type: "text", value: cur === undefined || cur === null ? "" : String(cur), disabled: !edit, "data-ref": "1",
        placeholder: f.placeholder || "nombre de la clave (opcional)", autocomplete: "off", list: listId });
      input.addEventListener("input", function () { if (input.value === "") setVal(null, true); else setVal(input.value); });
      api("GET", "/api/secrets").then(function (d) { (d.secrets || []).forEach(function (s) { dl.appendChild(h("option", { value: s.name })); }); }, function () {});
      return h("div", { class: "field" },
        h("div", { class: "fl" }, h("span", { text: "🔑 " + (f.label || key) })), input, dl,
        f.help ? h("div", { class: "help", text: f.help }) : null);
    } else {
      input = h("input", { type: type === "password" ? "password" : "text", value: cur === undefined || cur === null ? "" : String(cur),
        disabled: !edit, "data-ref": "1", placeholder: f.placeholder || "", autocomplete: "off" });
      input.addEventListener("input", function () { if (input.value === "") setVal(null, true); else setVal(input.value); });
    }
    return h("div", { class: "field" },
      h("div", { class: "fl" }, h("span", { text: f.label || key }), f.required ? h("span", { class: "req", text: "*", title: t("required") }) : null),
      input, f.help ? h("div", { class: "help", text: f.help }) : null);
  }

  // ---------------------------------------------------------------- editor visual (SVG)
  var NW = 200, NH = 58, SVGNS = "http://www.w3.org/2000/svg";
  function sv(tag, attrs) {
    var el = document.createElementNS(SVGNS, tag);
    if (attrs) for (var k in attrs) { var v = attrs[k]; if (v === null || v === undefined) continue;
      if (k === "text") el.textContent = v; else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v); else el.setAttribute(k, v); }
    for (var i = 2; i < arguments.length; i++) if (arguments[i]) el.appendChild(arguments[i]);
    return el;
  }
  S.gv = { x: 20, y: 20, k: 1, sel: null, selEdge: null, fitted: null };
  S.gv2 = { x: 20, y: 20, k: 1, sel: null, selEdge: null, fitted: null };   // grafo de solo lectura (pestaña Ejecuciones)

  function autoLayout(force) {
    var def = S.current.def, preds = {}, changed = false;
    def.edges.forEach(function (e) { (preds[e.target] = preds[e.target] || []).push(e.source); });
    var layer = {};
    function depth(id, seen) {
      if (layer[id] !== undefined) return layer[id];
      if (seen[id]) return 0; seen[id] = 1;
      var d = 0; (preds[id] || []).forEach(function (p) { d = Math.max(d, depth(p, seen) + 1); });
      return (layer[id] = d);
    }
    def.nodes.forEach(function (n) { depth(n.id, {}); });
    var rows = {};
    def.nodes.forEach(function (n) {
      var l = layer[n.id], r = rows[l] || 0; rows[l] = r + 1;
      if (force || !n.position || typeof n.position.x !== "number") { n.position = { x: 40 + l * (NW + 70), y: 40 + r * (NH + 36) }; changed = true; }
    });
    return changed;
  }
  function portY(n) { return n.position.y + NH / 2; }
  function edgePath(a, b) {
    var x1 = a.position.x + NW, y1 = portY(a), x2 = b.position.x, y2 = portY(b), dx = Math.max(50, Math.abs(x2 - x1) / 2);
    return "M" + x1 + "," + y1 + " C" + (x1 + dx) + "," + y1 + " " + (x2 - dx) + "," + y2 + " " + x2 + "," + y2;
  }
  function wouldCycle(src, tgt) { return src === tgt || !!descendants(tgt)[src]; }

  var addStepAt = function () {};
  function renderGraph(ed, ro) {
    ed = ed || els.editor;
    var w = S.current, def = w.def, edit = !ro && canEdit(), G = ro ? S.gv2 : S.gv;
    ed.classList.add("graph"); clear(ed);
    if (edit && autoLayout(false)) touch();
    var nmap = {}; def.nodes.forEach(function (n) { nmap[n.id] = n; });
    if (G.sel && !nmap[G.sel]) G.sel = null;

    var svg = sv("svg", { class: "gsvg", tabindex: "0" });
    var defs = sv("defs", null, sv("marker", { id: "arr", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" },
      sv("path", { d: "M0,0 L10,5 L0,10 z", class: "garrow" })));
    var view = sv("g");
    var gEdges = sv("g"), gNodes = sv("g"), gTemp = sv("g");
    view.appendChild(gEdges); view.appendChild(gNodes); view.appendChild(gTemp);
    svg.appendChild(defs); svg.appendChild(view);
    function applyView() { view.setAttribute("transform", "translate(" + G.x + "," + G.y + ") scale(" + G.k + ")"); }
    applyView();
    function toGraph(ev) { var r = svg.getBoundingClientRect(); return { x: (ev.clientX - r.left - G.x) / G.k, y: (ev.clientY - r.top - G.y) / G.k }; }

    var edgeEls = [], nodeEls = {};
    function drawEdges() {
      clear(gEdges); edgeEls = [];
      def.edges.forEach(function (e) {
        var a = nmap[e.source], b = nmap[e.target]; if (!a || !b) return;
        var d = edgePath(a, b), sel = G.selEdge && G.selEdge.s === e.source && G.selEdge.t === e.target;
        var vis = sv("path", { d: d, class: "gedge" + (sel ? " sel" : ""), "marker-end": "url(#arr)" });
        var hit = sv("path", { d: d, class: "gedge-hit", onclick: function (ev) { ev.stopPropagation(); if (ro) return; G.selEdge = { s: e.source, t: e.target }; G.sel = null; renderMain(); } });
        gEdges.appendChild(vis); gEdges.appendChild(hit); edgeEls.push({ e: e, vis: vis, hit: hit });
      });
    }
    function updateEdgePaths() {
      edgeEls.forEach(function (x) { var d = edgePath(nmap[x.e.source], nmap[x.e.target]); x.vis.setAttribute("d", d); x.hit.setAttribute("d", d); });
    }
    def.nodes.forEach(function (n) {
      var p = S.pmap[n.type], st = runStatusOf(n.id);
      var g = sv("g", { class: "gnode" + ((ro ? S.dkSel === n.id : G.sel === n.id) ? " sel" : "") + (n.enabled === false ? " off" : "") + (st ? " st-" + st : "") + (p ? "" : " bad"),
        transform: "translate(" + n.position.x + "," + n.position.y + ")" });
      g.appendChild(sv("rect", { class: "gbox", width: NW, height: NH, rx: 12 }));
      g.appendChild(sv("text", { class: "gicon", x: 12, y: 36, text: p ? (p.icon || "🧩") : "⚠" }));
      g.appendChild(sv("text", { class: "glabel", x: 40, y: 25, text: labelOf(n).slice(0, 22) }));
      g.appendChild(sv("text", { class: "gsub", x: 40, y: 43, text: (p ? p.name : n.type + " (no disp.)").slice(0, 26) }));
      g.appendChild(sv("circle", { class: "gstat", cx: NW - 14, cy: 14, r: 5 }));
      // puertos
      var pin = sv("circle", { class: "gport in", cx: 0, cy: NH / 2, r: 9, "data-in": n.id });
      var pout = sv("circle", { class: "gport out", cx: NW, cy: NH / 2, r: 9 });
      g.appendChild(pin); g.appendChild(pout);
      nodeEls[n.id] = g; gNodes.appendChild(g);

      g.addEventListener("pointerdown", function (ev) {
        if (ev.target === pout || ev.button !== 0) return;
        ev.stopPropagation();
        var sx = ev.clientX, sy = ev.clientY, ox = n.position.x, oy = n.position.y, moved = false;
        g.setPointerCapture(ev.pointerId);
        function mv(e2) {
          var dx = (e2.clientX - sx) / G.k, dy = (e2.clientY - sy) / G.k;
          if (!moved && Math.abs(dx) + Math.abs(dy) < 3) return;
          if (!edit) return;
          moved = true; n.position = { x: Math.round(ox + dx), y: Math.round(oy + dy) };
          g.setAttribute("transform", "translate(" + n.position.x + "," + n.position.y + ")"); updateEdgePaths();
        }
        function up() {
          g.removeEventListener("pointermove", mv); g.removeEventListener("pointerup", up); g.removeEventListener("pointercancel", up);
          if (moved) { touch(); } else if (ro) { pickStep(n.id); } else { G.sel = n.id; G.selEdge = null; S.collapsed[n.id] = false; renderMain(); }
        }
        g.addEventListener("pointermove", mv); g.addEventListener("pointerup", up); g.addEventListener("pointercancel", up);
      });
      // conectar arrastrando desde el puerto de salida
      pout.addEventListener("pointerdown", function (ev) {
        if (!edit || ev.button !== 0) return;
        ev.stopPropagation(); pout.setPointerCapture(ev.pointerId);
        var x1 = n.position.x + NW, y1 = portY(n);
        var tmp = sv("path", { class: "gedge temp", d: "M" + x1 + "," + y1 + " L" + x1 + "," + y1 });
        gTemp.appendChild(tmp);
        function mv(e2) { var q = toGraph(e2); tmp.setAttribute("d", "M" + x1 + "," + y1 + " C" + (x1 + 60) + "," + y1 + " " + (q.x - 60) + "," + q.y + " " + q.x + "," + q.y);
          Object.keys(nodeEls).forEach(function (id) { nodeEls[id].classList.remove("target-ok", "target-bad"); });
          var t2 = targetAt(e2); if (t2) nodeEls[t2].classList.add(wouldCycle(n.id, t2) ? "target-bad" : "target-ok"); }
        function up(e2) {
          pout.removeEventListener("pointermove", mv); pout.removeEventListener("pointerup", up); pout.removeEventListener("pointercancel", up);
          clear(gTemp);
          var t2 = e2.type === "pointerup" ? targetAt(e2) : null;
          Object.keys(nodeEls).forEach(function (id) { nodeEls[id].classList.remove("target-ok", "target-bad"); });
          if (t2) {
            if (wouldCycle(n.id, t2)) toast(lang === "es" ? "Esa conexión crearía un ciclo" : "That link would create a cycle");
            else if (!def.edges.some(function (e) { return e.source === n.id && e.target === t2; })) { def.edges.push({ source: n.id, target: t2 }); touch(); renderMain(); }
          }
        }
        pout.addEventListener("pointermove", mv); pout.addEventListener("pointerup", up); pout.addEventListener("pointercancel", up);
      });
    });
    function targetAt(ev) {
      var q = toGraph(ev), best = null;
      def.nodes.forEach(function (m) { if (q.x >= m.position.x - 10 && q.x <= m.position.x + NW + 10 && q.y >= m.position.y - 6 && q.y <= m.position.y + NH + 6) best = m.id; });
      return best;
    }
    drawEdges();

    // desplazar y zoom
    svg.addEventListener("pointerdown", function (ev) {
      if (ev.target !== svg || ev.button !== 0) return;
      var sx = ev.clientX, sy = ev.clientY, ox = G.x, oy = G.y, moved = false;
      svg.setPointerCapture(ev.pointerId);
      function mv(e2) { var dx = e2.clientX - sx, dy = e2.clientY - sy; if (Math.abs(dx) + Math.abs(dy) > 3) moved = true; G.x = ox + dx; G.y = oy + dy; applyView(); }
      function up() { svg.removeEventListener("pointermove", mv); svg.removeEventListener("pointerup", up);
        if (!moved && (G.sel || G.selEdge)) { G.sel = null; G.selEdge = null; renderMain(); } }
      svg.addEventListener("pointermove", mv); svg.addEventListener("pointerup", up);
    });
    svg.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      var r = svg.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
      var k2 = Math.max(0.3, Math.min(2.2, G.k * (ev.deltaY < 0 ? 1.1 : 1 / 1.1)));
      G.x = mx - (mx - G.x) * (k2 / G.k); G.y = my - (my - G.y) * (k2 / G.k); G.k = k2; applyView();
    }, { passive: false });
    svg.addEventListener("keydown", function (ev) {
      if (ev.key !== "Delete" && ev.key !== "Backspace") return;
      if (!edit) return;
      deleteSelection();
    });
    // Ctrl+C / Ctrl+V / Ctrl+D sobre el grafo (el paso se pega sin conexiones)
    if (!ro) S.gkey = function (ev) {
      var k = (ev.key || "").toLowerCase(), n = G.sel && nmap[G.sel];
      if (k === "c" && n) { ev.preventDefault(); clipCopy(n); toast(lang === "es" ? "Paso copiado: «" + n.label + "». Use Ctrl+V para pegarlo (también en otro workflow)." : "Step copied. Press Ctrl+V to paste it.", null, null, 3500); }
      else if (k === "v" && edit && clipLoad()) { ev.preventDefault(); clipPaste(null, null); }
      else if (k === "d" && edit && n) { ev.preventDefault(); clipCopy(n); clipPaste(null, n.position); }
    };
    svg.addEventListener("contextmenu", function (ev) {
      ev.preventDefault(); if (ro) return;
      var gn = ev.target.closest ? ev.target.closest(".gnode") : null, es = lang === "es", q = toGraph(ev);
      if (gn) {
        var id = Object.keys(nodeEls).filter(function (k) { return nodeEls[k] === gn; })[0], n = nmap[id];
        if (!n) return;
        G.sel = id; G.selEdge = null; renderMain();
        showCtxMenu(ev, [
          { label: es ? "Duplicar" : "Duplicate", key: "Ctrl+D", disabled: !edit, fn: function () { clipCopy(n); clipPaste(null, n.position); } },
          { label: es ? "Añadir paso después…" : "Add step after…", disabled: !edit, fn: function () { addStepAt({ clientX: ev.clientX, clientY: ev.clientY }, null, n); } },
          { label: es ? "Copiar" : "Copy", key: "Ctrl+C", fn: function () { clipCopy(n); toast(es ? "Paso copiado. Pegue con clic derecho en el fondo o Ctrl+V." : "Step copied.", null, null, 3500); } },
          "-",
          { label: es ? "Eliminar" : "Delete", key: "Supr", danger: true, disabled: !edit, fn: function () { G.sel = null; removeNode(n); } }]);
      } else {
        var pos = { x: q.x - NW / 2, y: q.y - NH / 2 };
        if (edit) addStepAt(ev, pos, null, [{ label: es ? "Pegar aquí" : "Paste here", key: "Ctrl+V", disabled: !clipLoad(), fn: function () { clipPaste(pos, null); } }]);
        else showCtxMenu(ev, [{ label: es ? "Pegar aquí" : "Paste here", key: "Ctrl+V", disabled: true, fn: function () {} }]);
      }
    });
    function deleteSelection() {
      if (G.selEdge) { def.edges = def.edges.filter(function (e) { return !(e.source === G.selEdge.s && e.target === G.selEdge.t); }); G.selEdge = null; touch(); renderMain(); }
      else if (G.sel && nmap[G.sel]) { var nd = nmap[G.sel]; G.sel = null; removeNode(nd); }
    }
    function fit() {
      if (!def.nodes.length) { G.x = 20; G.y = 20; G.k = 1; applyView(); return; }
      var r = svg.getBoundingClientRect(), minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
      def.nodes.forEach(function (n) { minx = Math.min(minx, n.position.x); miny = Math.min(miny, n.position.y); maxx = Math.max(maxx, n.position.x + NW); maxy = Math.max(maxy, n.position.y + NH); });
      var k = Math.min(1.2, Math.max(0.3, Math.min((r.width - 60) / (maxx - minx), (r.height - 60) / (maxy - miny))));
      G.k = k; G.x = (r.width - (maxx - minx) * k) / 2 - minx * k; G.y = (r.height - (maxy - miny) * k) / 2 - miny * k; applyView();
    }

    // barra de herramientas
    // añadir un paso: pos explícita (clic derecho) o a la derecha del seleccionado / centro de la vista; ref = paso al que se conecta
    function addStep(p, pos, ref) {
      var id = newNodeId(), r = svg.getBoundingClientRect();
      var busy = function () { return def.nodes.some(function (o) { return Math.abs(o.position.x - pos.x) < NW && Math.abs(o.position.y - pos.y) < NH + 20; }); };
      if (!pos) {
        if (ref) pos = { x: Math.round(ref.position.x + NW + 70), y: Math.round(ref.position.y) };
        else pos = { x: Math.round((r.width / 2 - G.x) / G.k - NW / 2), y: Math.round((r.height / 2 - G.y) / G.k - NH / 2) };
        while (busy()) pos.y += NH + 30;
      } else pos = { x: Math.round(pos.x), y: Math.round(pos.y) };
      var node = { id: id, label: uniqueLabel(p.name.replace(/[^\w]+/g, "") || id), type: p.id, config: {}, on_error: "stop", enabled: true, position: pos };
      if (ref) def.edges.push({ source: ref.id, target: id });
      def.nodes.push(node); G.sel = id; G.selEdge = null; S.collapsed[id] = false; touch(); renderMain();
    }
    var addBtn = h("button", { class: "btn sm", text: "+ " + t("add_step"), "aria-haspopup": "menu", onclick: function (ev) {
      var r0 = ev.currentTarget.getBoundingClientRect(), ref = G.sel && nmap[G.sel] ? nmap[G.sel] : null;
      stepPicker({ clientX: r0.left, clientY: r0.bottom + 4 }, function (p) { addStep(p, null, ref); });
    } });
    addStepAt = function (ev, pos, ref, withPaste) {
      stepPicker(ev, function (p) { addStep(p, pos, ref); }, withPaste);
    };
    var tools = ro ? h("div", { class: "gtools" },
      h("button", { class: "btn sm", text: lang === "es" ? "Ajustar" : "Fit", onclick: fit }),
      h("span", { class: "muted", style: "font-size:12px", text: lang === "es" ? "Vista de solo lectura de la ejecución elegida. Pulse un paso para ver su registro." : "Read-only view of the selected run. Click a step to see its log." })) :
      h("div", { class: "gtools" },
      edit ? addBtn : null,
      h("button", { class: "btn sm", text: lang === "es" ? "Ajustar" : "Fit", onclick: fit }),
      panelBtn("insp", lang === "es" ? "Mostrar u ocultar el panel del paso" : "Show or hide the step panel", lang === "es" ? "☰ Panel" : "☰ Panel"),
      edit ? h("button", { class: "btn sm", text: lang === "es" ? "Ordenar" : "Auto-layout", onclick: function () { autoLayout(true); G.fitted = null; touch(); renderMain(); } }) : null,
      edit ? h("button", { class: "btn sm danger", text: t("remove"), disabled: !(G.sel || G.selEdge), onclick: deleteSelection }) : null,
      (G.sel && nmap[G.sel] && canRun()) ? h("span", { class: "gplay" },
        h("button", { class: "btn sm", text: "▶ " + (lang === "es" ? "Este paso" : "This step"),
          title: lang === "es" ? "Ejecuta solo este paso con los últimos resultados de los pasos anteriores" : "Runs only this step using the latest results of earlier steps",
          onclick: function () { runPartial(G.sel, "only"); } }),
        h("button", { class: "btn sm", text: "▶ " + (lang === "es" ? "Hasta aquí" : "Up to here"),
          title: lang === "es" ? "Ejecuta los pasos anteriores y este" : "Runs earlier steps and this one",
          onclick: function () { runPartial(G.sel, "until"); } }),
        h("button", { class: "btn sm", text: "▶ " + (lang === "es" ? "Desde aquí" : "From here"),
          title: lang === "es" ? "Ejecuta este paso y los siguientes, reutilizando los resultados anteriores" : "Runs this step and the following ones, reusing earlier results",
          onclick: function () { runPartial(G.sel, "from"); } })) : null,
      h("span", { class: "muted", style: "font-size:12px", text: lang === "es" ? "Clic derecho en el fondo para añadir un paso. Un paso nuevo se conecta al nodo seleccionado. Arrastre del punto derecho de un nodo al izquierdo de otro para conectar" : "Right-click the background to add a step. Drag from a node's right dot to another's left dot to connect" }));

    var inspector = h("div", { class: "inspector" });
    if (ro) { /* sin inspector */ }
    else if (G.sel && nmap[G.sel]) {
      inspector.appendChild(stepCard(nmap[G.sel], def.nodes.indexOf(nmap[G.sel])));
    } else if (G.selEdge) {
      inspector.appendChild(h("div", { class: "muted", style: "padding:14px", text: (lang === "es" ? "Conexión: " : "Link: ") + labelOf(nmap[G.selEdge.s] || {}) + " → " + labelOf(nmap[G.selEdge.t] || {}) + (lang === "es" ? ". Pulse Suprimir o «Quitar»." : ". Press Delete or Remove.") }));
    } else {
      inspector.appendChild(h("div", { class: "muted", style: "padding:14px", text: lang === "es" ? "Seleccione un nodo para editar sus campos." : "Select a node to edit its fields." }));
      inspector.appendChild(varsPanel());
    }
    if (w.problems && !ro) {
      var pb = h("div", { class: "problems", style: "margin:8px" });
      if (w.problems.valid && !w.problems.warnings.length) pb.appendChild(h("div", { text: "✓ " + t("valid_ok") }));
      w.problems.errors.forEach(function (m) { pb.appendChild(h("div", { class: "e", text: "✗ " + m })); });
      w.problems.warnings.forEach(function (m) { pb.appendChild(h("div", { class: "w", text: "! " + m })); });
      inspector.insertBefore(pb, inspector.firstChild);
    }
    var canvas = h("div", { class: "gcanvas" }, tools, svg);
    if (S.conflict && !ro) canvas.insertBefore(h("div", { class: "banner err", style: "margin:8px" }, h("span", { text: t("conflict") + " " }),
      h("button", { class: "btn sm", text: t("reload"), onclick: function () { openWorkflow(w.id); } })), canvas.firstChild);
    ed.appendChild(canvas); if (!ro) ed.appendChild(inspector);
    if (G.fitted !== w.id) { G.fitted = w.id; setTimeout(fit, 0); }
    S.graphRefresh = function () {
      def.nodes.forEach(function (n) {
        var g = nodeEls[n.id]; if (!g) return;
        var st = runStatusOf(n.id);
        var base = g.getAttribute("class").replace(/\bst-\S+/g, "").trim();
        if (ro) base = base.replace(/\bsel\b/g, "").trim() + (S.dkSel === n.id ? " sel" : "");
        g.setAttribute("class", base + (st ? " st-" + st : ""));
      });
    };
  }

  // ---------------------------------------------------------------- validar
  function validate() {
    flushSave();
    var w = S.current;
    api("POST", "/api/workflows/" + w.id + "/validate", { definition: w.def }).then(function (r) {
      w.problems = r; if (S.tab === "runs") S.tab = "graph"; renderMain();
    }, function (e) { toast(e.message); });
  }

  // ============================================================ ejecución
  var pollTimer = null;
  function stopPolling(keepLive) { if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; } }
  function setRunning(on) {
    var r = document.getElementById("runbtn"), s = document.getElementById("stopbtn");
    if (r) r.disabled = on || !canRun();
    if (s) s.classList.toggle("hidden", !on);
  }
  function startRun(only) {
    var w = S.current;
    if (S.live && !S.live.done) { toast(lang === "es" ? "Ya hay una ejecución en curso" : "A run is already in progress"); return; }
    doSaveNow().then(function () {
      var vars = clone(w.def.variables || {});
      var body = { variables: vars }; if (only) body.only = only;
      return api("POST", "/api/workflows/" + w.id + "/run", body);
    }).then(function (d) {
      S.live = { id: d.run_id, after: 0, nodes: {}, order: [], status: "queued", done: false, logs: {}, wfname: w.name, started: Date.now(), reused: d.reused || [], partial: !!only };
      S.selRun = d.run_id; S.dkAuto = true; S.dkSel = null; S.dkOpen = true;
      setRunning(true); renderRunPane(); poll(); refreshList().catch(function () {}); loadRuns();
    }, function (e) { toast(e.message); });
  }
  // ejecución parcial desde el grafo: modo "only" (solo este), "until" (hasta aquí), "from" (desde aquí)
  function runPartial(id, mode) {
    var ids = {}; ids[id] = 1;
    if (mode === "until") Object.keys(ancestors(id)).forEach(function (k) { ids[k] = 1; });
    if (mode === "from") Object.keys(descendants(id)).forEach(function (k) { ids[k] = 1; });
    var list = Object.keys(ids).filter(function (k) { var n = S.current.def.nodes.filter(function (x) { return x.id === k; })[0]; return n && n.enabled !== false; });
    startRun(list);
  }
  function doSaveNow() {
    return new Promise(function (resolve) {
      if (S.saveState !== "dirty" && S.saveState !== "saving") return resolve();
      var iv = setInterval(function () { if (S.saveState === "saved" || S.saveState === "error" || S.saveState === "conflict") { clearInterval(iv); resolve(); } }, 80);
      if (S.saveState === "dirty") doSave();
    });
  }
  function cancelRun() {
    if (S.live && !S.live.done) api("POST", "/api/runs/" + S.live.id + "/cancel").catch(function (e) { toast(e.message); });
  }
  function poll() {
    var L = S.live; if (!L || L.done) return;
    api("GET", "/api/runs/" + L.id + "/events?after=" + L.after).then(function (d) {
      d.events.forEach(function (ev) { applyEvent(L, ev); });
      L.after = d.seq; L.status = d.status || L.status;
      if (d.done) { L.done = true; setRunning(false); renderRunPane(); onRunFinished(L); return; }
      if (d.events.length) renderRunPane();
      pollTimer = setTimeout(poll, 600);
    }, function (e) { if (e.status === 401) return; pollTimer = setTimeout(poll, 2000); });
  }
  function applyEvent(L, ev) {
    function nd(id, label) { if (!L.nodes[id]) { L.nodes[id] = { id: id, label: label || id, status: "pending", logs: [] }; L.order.push(id); } return L.nodes[id]; }
    switch (ev.type) {
      case "queued": L.status = "queued"; break;
      case "run_start": L.status = "running"; (ev.nodes || []).forEach(function (x) { var o = nd(x.id, x.label); o.type = x.type; }); break;
      case "node_start": var a = nd(ev.node_id, ev.label); a.status = "running"; a.t0 = Date.now(); break;
      case "node_end": var b = nd(ev.node_id, ev.label); b.status = ev.status; b.summary = ev.summary; b.error = ev.error; b.duration = ev.duration; break;
      case "log": var c = nd(ev.node_id, ev.label); c.logs.push({ level: ev.level || "info", message: ev.message }); break;
      case "run_end": L.duration = ev.duration; L.endStatus = ev.status; break;
      case "run_final": L.status = ev.status; L.error = ev.error; break;
    }
  }
  function onRunFinished(L) {
    refreshList(); loadRuns();
  }
  function loadRuns() {
    var w = S.current; if (!w) return;
    api("GET", "/api/workflows/" + w.id + "/runs?limit=100").then(function (d) {
      if (S.current && S.current.id === w.id) {
        S.runs = d.runs;
        // reconectar con una ejecución que sigue en curso (p. ej. al volver de otro workflow)
        var act = d.runs.filter(function (r) { return r.status === "queued" || r.status === "running"; })[0];
        if (act && (!S.live || S.live.done)) {
          S.live = { id: act.id, after: 0, nodes: {}, order: [], status: act.status, done: false, logs: {}, wfname: w.name, started: Date.now(), reused: [], partial: false };
          stopPolling(); setRunning(true); poll();
        }
        if (S.tab === "runs") autoSelectRun();
        renderRunPane();
      }
    }, function () {});
  }
  // la barra lateral se refresca sola mientras haya ejecuciones en curso
  var listTimer = null;
  function watchList() {
    if (listTimer) return;
    listTimer = setInterval(function () {
      if (!S.user) return;
      var any = S.workflows.some(function (w) { return w.last_run && (w.last_run.status === "running" || w.last_run.status === "queued"); });
      if (any) refreshList().catch(function () {});
    }, 4000);
  }

  // ---------------------------------------------------------------- registro (dock) y lista de ejecuciones
  var STEP_ICON = { ok: "✓", error: "✗", partial: "◐", skipped: "↷", cancelled: "■", pending: "·" };
  S.dkOpen = true; S.dkAuto = true; S.dkSel = null; S.selRun = null;
  // ejecución que pintan el grafo y el registro: en Editor, la última en vivo; en Ejecuciones, la elegida de la lista
  function runSrc() {
    if (S.tab === "runs") {
      if (S.live && S.selRun === S.live.id) return { kind: "live", L: S.live };
      if (S.viewRun && S.viewRun.id === S.selRun) return { kind: "past", run: S.viewRun };
      return null;
    }
    return S.live ? { kind: "live", L: S.live } : null;
  }
  function stepsOf(src) {
    if (!src) return null;
    if (src.kind === "live") {
      var L = src.L;
      return { id: L.id, status: L.status, done: L.done, started: new Date(L.started).toISOString(), duration: L.duration, error: L.error, partial: L.partial, reused: L.reused || [],
        steps: L.order.map(function (id) {
          var n = L.nodes[id];
          return { id: id, label: n.label, type: n.type, status: n.status, duration: n.duration, summary: n.summary, error: n.error, logs: n.logs || [],
            has_result: L.done && n.status !== "pending" && n.status !== "running" };
        }) };
    }
    var r = src.run;
    return { id: r.id, status: r.status, done: true, started: r.started, duration: r.duration, error: r.error, partial: false, reused: [],
      steps: (r.nodes || []).slice().sort(function (a, b) { return (a.started || "") < (b.started || "") ? -1 : 1; }).map(function (n) {
        return { id: n.node_id, label: n.label, type: n.type, status: n.status, duration: n.duration, summary: n.summary, error: n.error, logs: n.logs || [], has_result: !!n.has_result };
      }) };
  }
  function autoPick(info) {
    var st = info.steps; if (!st.length) return null;
    var i, run = null;
    for (i = st.length - 1; i >= 0; i--) if (st[i].status === "running") { run = st[i]; break; }
    if (run) return run.id;
    if (info.done) { for (i = 0; i < st.length; i++) if (st[i].status === "error") return st[i].id; }
    for (i = st.length - 1; i >= 0; i--) if (st[i].status !== "pending" && st[i].status !== "skipped") return st[i].id;
    return st[0].id;
  }
  function pickStep(id) { S.dkSel = id; S.dkAuto = false; S.dkOpen = true; renderRunPane(); }
  function stepStatusText(stp, info) {
    var st = stp.status;
    var txt = (st === "pending" && info.partial && (info.done || info.reused.some(function (r) { return r.node === stp.label; }))) ? (lang === "es" ? "Reutilizado" : "Reused") : (t(st) || st);
    return txt + (stp.duration != null ? " · " + fmtDur(stp.duration) : "");
  }
  function renderDock() {
    var dk = els.dock; if (!dk) return;
    var es = lang === "es";
    var oldDet = dk.querySelector(".dk-detail"), oldList = dk.querySelector(".dk-steps");
    var oldTop = oldDet ? oldDet.scrollTop : 0, oldListTop = oldList ? oldList.scrollTop : 0, sameSel = dk._lastSel === S.dkSel;
    clear(dk);
    dk.classList.toggle("closed", !S.dkOpen);
    var info = stepsOf(runSrc());
    var head = h("div", { class: "dk-head", onclick: function (ev) { if (ev.target.closest && ev.target.closest("button")) return; S.dkOpen = !S.dkOpen; renderDock(); } },
      h("span", { class: "dk-caret", text: S.dkOpen ? "▾" : "▸" }), h("b", { text: es ? "Registro" : "Log" }),
      info ? h("span", { class: "badge " + (info.status === "ok" ? "ok" : info.status === "error" ? "err" : ""), text: t(info.status) || info.status }) : null,
      info ? h("span", { class: "muted", style: "font-size:12px", text: fmtDate(info.started) + (info.duration != null ? " · " + fmtDur(info.duration) : "") }) : null,
      h("span", { style: "flex:1" }));
    var src = runSrc();
    if (info && src.kind === "past") {
      if (canRun()) head.appendChild(h("button", { class: "btn sm", text: "↻ " + t("run"), onclick: function () { startRun(); } }));
      if (canEdit() && info.status !== "running" && info.status !== "queued")
        head.appendChild(h("button", { class: "btn sm danger", text: "🗑 " + (es ? "Eliminar esta ejecución" : "Delete this run"), onclick: function () { deleteRun(info.id); } }));
    }
    dk.appendChild(head);
    if (!S.dkOpen) return;
    var body = h("div", { class: "dk-body" }); dk.appendChild(body);
    if (!info) {
      body.appendChild(h("div", { class: "muted dk-empty", text: S.tab === "runs" ? (S.runs.length ? "…" : t("no_runs"))
        : (es ? "Aquí verá el registro paso a paso al pulsar «Ejecutar». El historial completo está en la pestaña Ejecuciones." : "Run the workflow to see the step-by-step log here. Full history is in the Runs tab.") }));
      return;
    }
    if (S.dkAuto || !info.steps.some(function (x) { return x.id === S.dkSel; })) S.dkSel = autoPick(info);
    dk._lastSel = S.dkSel;
    var list = h("div", { class: "dk-steps" });
    if (info.partial) list.appendChild(h("div", { class: "dk-note", text: es ? "Ejecución parcial" : "Partial run" }));
    info.reused.forEach(function (r) { list.appendChild(h("div", { class: "dk-note", text: (es ? "Reutiliza el resultado de " : "Reuses the result of ") + r.node + (r.finished ? " (" + fmtDate(r.finished) + ")" : "") })); });
    if (info.error) list.appendChild(h("div", { class: "dk-note err", text: info.error }));
    info.steps.forEach(function (x) {
      list.appendChild(h("div", { class: "dk-step " + x.status + (x.id === S.dkSel ? " sel" : ""), onclick: function () { pickStep(x.id); } },
        x.status === "running" ? h("span", { class: "spin" }) : h("span", { class: "dk-ic", text: STEP_ICON[x.status] || "·" }),
        h("span", { class: "dk-lb", text: x.label }),
        h("span", { class: "dk-st", text: stepStatusText(x, info) })));
    });
    body.appendChild(list);
    var det = h("div", { class: "dk-detail" }), cur = info.steps.filter(function (x) { return x.id === S.dkSel; })[0];
    if (cur) {
      det.appendChild(h("div", { class: "dk-dh" }, h("b", { text: cur.label }), cur.type ? h("span", { class: "muted", text: cur.type }) : null,
        h("span", { style: "flex:1" }),
        cur.has_result ? h("button", { class: "btn sm", text: es ? "Ver resultado" : "View result", onclick: function () { showNodeResult(info.id, cur.id); } }) : null));
      if (cur.summary) det.appendChild(h("div", { class: "summ", text: typeof cur.summary === "string" ? cur.summary : JSON.stringify(cur.summary) }));
      if (cur.error) det.appendChild(h("div", { class: "err-text", text: cur.error }));
      if (cur.logs.length) {
        var lg = h("div", { class: "dk-log" });
        cur.logs.forEach(function (l) { lg.appendChild(h("div", { class: l.level, text: l.message })); });
        det.appendChild(lg);
      } else if (!cur.summary && !cur.error) {
        det.appendChild(h("div", { class: "muted", text: cur.status === "pending" ? (es ? "Aún no se ejecuta." : "Not run yet.") : (es ? "Sin mensajes." : "No messages.") }));
      }
    }
    body.appendChild(det);
    det.scrollTop = (S.dkAuto && info.status === "running") ? det.scrollHeight : (sameSel ? oldTop : 0);
    list.scrollTop = oldListTop;
  }
  function renderRunPane() {
    if (S.graphRefresh) { try { S.graphRefresh(); } catch (e) { /* aún no hay grafo */ } }
    if (S.tab === "runs") renderRunList();
    renderDock();
  }
  function renderRunList() {
    var box = els.runlist; if (!box) return;
    var es = lang === "es", oldB = box.querySelector(".rl-body"), top = oldB ? oldB.scrollTop : 0;
    clear(box);
    var rows = S.runs.slice();
    if (S.live && !rows.some(function (r) { return r.id === S.live.id; }))
      rows.unshift({ id: S.live.id, status: S.live.status, started: new Date(S.live.started).toISOString(), started_by_name: S.user.display_name || S.user.username, duration: null });
    box.appendChild(h("div", { class: "rl-head" }, h("b", { text: t("runs") }), h("span", { class: "muted", text: rows.length ? String(rows.length) : "" }), h("span", { style: "flex:1" }),
      (canEdit() && rows.length) ? h("button", { class: "btn sm icon", title: es ? "Limpiar historial…" : "Clear history…", "aria-label": es ? "Limpiar historial" : "Clear history", text: "🧹", onclick: clearHistoryDialog }) : null));
    var body = h("div", { class: "rl-body" });
    if (!rows.length) body.appendChild(h("div", { class: "muted", style: "padding:14px;text-align:center", text: t("no_runs") }));
    rows.forEach(function (r) {
      var st = (S.live && S.live.id === r.id) ? S.live.status : r.status;
      var dur = (S.live && S.live.id === r.id && !S.live.done) ? null : ((S.live && S.live.id === r.id && S.live.duration != null) ? S.live.duration : r.duration);
      body.appendChild(h("div", { class: "rl-row" + (r.id === S.selRun ? " sel" : ""), onclick: function () { openPastRun(r.id); } },
        st === "running" || st === "queued" ? h("span", { class: "spin" }) : h("span", { class: "dot " + st }),
        h("div", { class: "rl-mid" }, h("div", { text: fmtDate(r.started) }),
          h("div", { class: "muted", style: "font-size:12px", text: (t(st) || st) + (r.started_by_name ? " · " + r.started_by_name : "") + (r.error ? " · " + String(r.error).slice(0, 60) : "") })),
        h("span", { class: "muted", text: dur != null ? fmtDur(dur) : "" }),
        delRunBtn(r)));
    });
    box.appendChild(body); body.scrollTop = top;
  }
  // elige una ejecución al entrar en la pestaña: la que está en curso o, si no, la más reciente
  function autoSelectRun() {
    if (S.selRun && (S.runs.some(function (r) { return r.id === S.selRun; }) || (S.live && S.live.id === S.selRun))) {
      if (!(S.live && S.live.id === S.selRun) && !(S.viewRun && S.viewRun.id === S.selRun)) openPastRun(S.selRun);
      return;
    }
    S.selRun = S.live ? S.live.id : (S.runs[0] ? S.runs[0].id : null);
    S.dkAuto = true; S.dkSel = null;
    if (S.selRun && !(S.live && S.live.id === S.selRun)) openPastRun(S.selRun);
  }
  function delRunBtn(r, after) {
    if (!canEdit() || r.status === "running" || r.status === "queued") return null;
    return h("button", { class: "btn icon del", text: "✕", title: lang === "es" ? "Eliminar esta ejecución del historial" : "Delete this run from history",
      "aria-label": lang === "es" ? "Eliminar ejecución" : "Delete run", onclick: function (e) { e.stopPropagation(); deleteRun(r.id, after); } });
  }
  function deleteRun(id, after) {
    var es = lang === "es";
    confirm_(es ? "Eliminar ejecución" : "Delete run", es ? "Se quitará esta ejecución y sus resultados del historial. No se puede deshacer." : "This run and its results will be removed from history. This cannot be undone.",
      es ? "Eliminar" : "Delete", function () {
        api("DELETE", "/api/runs/" + id).then(function () {
          if (S.viewRun && S.viewRun.id === id) S.viewRun = null;
          if (S.selRun === id) S.selRun = null;
          toast(es ? "Ejecución eliminada" : "Run deleted"); loadRuns(); refreshList(); if (after) after();
        }, function (e) { toast(e.message); });
      });
  }
  function clearHistoryDialog() {
    var es = lang === "es", keep = h("input", { type: "number", min: 0, max: 1000, value: 10, style: "width:90px" });
    dialog(es ? "Limpiar historial" : "Clear history", h("div", null,
      h("div", { class: "field" }, h("div", { class: "fl", text: es ? "Conservar las últimas N ejecuciones (0 = borrar todas)" : "Keep the last N runs (0 = delete all)" }), keep),
      h("div", { class: "muted", style: "font-size:12px", text: es ? "Las ejecuciones en curso no se tocan. No se puede deshacer." : "Runs in progress are not touched. This cannot be undone." })),
      [{ label: t("cancel") }, { label: es ? "Eliminar" : "Delete", cls: "danger", fn: function () {
        api("POST", "/api/workflows/" + S.current.id + "/runs/clear", { keep: parseInt(keep.value, 10) || 0 }).then(function (r) {
          S.viewRun = null; S.selRun = null; toast((es ? "Ejecuciones eliminadas: " : "Runs deleted: ") + r.deleted); loadRuns(); refreshList();
        }, function (e) { toast(e.message); }); } }]);
  }
  function openPastRun(id) {
    if (S.selRun !== id) { S.dkAuto = true; S.dkSel = null; }
    S.selRun = id;
    if (S.live && S.live.id === id) { renderRunPane(); return; }
    api("GET", "/api/runs/" + id).then(function (d) {
      if (S.selRun !== id) return;
      S.viewRun = d.run; renderRunPane();
    }, function (e) { toast(e.message); });
  }
  function showNodeResult(runId, nodeId) {
    var pre = h("pre", { class: "json", text: "…" });
    dialog(t("result") + " · " + nodeId, pre, null, true);
    api("GET", "/api/runs/" + runId + "/nodes/" + encodeURIComponent(nodeId)).then(function (d) {
      var s; try { s = JSON.stringify(d.node.result, null, 2); } catch (e) { s = String(d.node.result); }
      if (s && s.length > 200000) s = s.slice(0, 200000) + "\n… (recortado)";
      pre.textContent = s === undefined ? "—" : s;
    }, function (e) { pre.textContent = e.message; });
  }
  // ============================================================ compartir
  function shareDialog() {
    var w = S.current;
    api("GET", "/api/users/directory").then(function (ud) {
      var team = h("select", null,
        ["none", "view", "run", "edit"].map(function (v) { return h("option", { value: v, text: v === "none" ? t("none") : v === "view" ? t("view") : v === "run" ? t("run_") : t("edit"), selected: w.team_access === v }); }));
      var perms = {}; (w.shares || []).forEach(function (s) { perms[s.user_id] = s.permission; });
      var tb = h("tbody");
      ud.users.filter(function (u) { return u.id !== w.owner_id; }).forEach(function (u) {
        var sel = h("select", { "data-uid": u.id },
          ["", "view", "run", "edit"].map(function (v) { return h("option", { value: v, text: v === "" ? t("none") : v === "view" ? t("view") : v === "run" ? t("run_") : t("edit"), selected: (perms[u.id] || "") === v }); }));
        tb.appendChild(h("tr", null, h("td", { text: (u.display_name || u.username) + " (" + u.role + ")" }), h("td", null, sel)));
      });
      dialog(t("share") + " · " + w.name, h("div", null,
        h("div", { class: "field" }, h("div", { class: "fl", text: t("team_access") }), team),
        h("table", { style: "margin-top:10px" }, tb)),
        [{ label: t("cancel") }, { label: t("save"), cls: "primary", fn: function (close) {
          var shares = [];
          tb.querySelectorAll("select").forEach(function (s) { if (s.value) shares.push({ user_id: Number(s.dataset.uid), permission: s.value }); });
          api("PUT", "/api/workflows/" + w.id + "/shares", { team_access: team.value, shares: shares }).then(function (r) {
            w.team_access = r.team_access; w.shares = r.shares; refreshList();
          }, function (e) { toast(e.message); });
        } }]);
    });
  }

  // ============================================================ programación
  var DAYS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"], DAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  var SCH_STATUS = { iniciada: "✓", omitida: "↷", error: "✗" };
  function schedRow(s, reload, showWf) {
    var edit = S.user.role !== "viewer";
    var last = s.last_fire ? (SCH_STATUS[s.last_status] || "") + " " + fmtDate(s.last_fire) + (s.last_run_status ? " · " + (t(s.last_run_status) || s.last_run_status) : "") : "—";
    return h("tr", null,
      h("td", null, h("div", { text: s.name }), showWf ? h("div", { class: "muted", style: "font-size:12px", text: s.workflow_name }) : null,
        h("div", { class: "muted", style: "font-size:12px", text: s.description })),
      h("td", { text: s.enabled ? fmtDate(s.next_run) : "—" }),
      h("td", null, h("div", { text: last }), s.last_message && s.last_status !== "iniciada" ? h("div", { class: "muted", style: "font-size:12px", text: s.last_message }) : null),
      h("td", null, h("label", { class: "chk" }, h("input", { type: "checkbox", checked: s.enabled, disabled: !edit, onchange: function (e) {
        api("PUT", "/api/schedules/" + s.id, { enabled: e.target.checked }).then(reload, function (er) { toast(er.message); reload(); }); } }))),
      h("td", null, edit ? h("button", { class: "btn sm danger", text: "✕", onclick: function () {
        api("DELETE", "/api/schedules/" + s.id).then(reload, function (er) { toast(er.message); }); } }) : null));
  }
  function schedTable(list, reload, showWf) {
    if (!list.length) return h("div", { class: "muted", text: t("no_sched") });
    return h("table", null, h("thead", null, h("tr", null, h("th", { text: t("sched_what") }), h("th", { text: t("sched_next") }),
      h("th", { text: t("sched_last") }), h("th", { text: t("enabled") }), h("th"))),
      h("tbody", null, list.map(function (s) { return schedRow(s, reload, showWf); })));
  }
  function scheduleDialog() {
    var w = S.current, box = h("div", { text: "…" }), form = h("div");
    var d = dialog(t("schedule") + " · " + w.name, h("div", null, box, form), null, true);
    function load() {
      api("GET", "/api/workflows/" + w.id + "/schedules").then(function (r) { clear(box).appendChild(schedTable(r.schedules, load, false)); }, function (e) { box.textContent = e.message; });
    }
    var nm = h("input", { type: "text", placeholder: t("name"), value: "" });
    var kind = h("select", null, h("option", { value: "daily", text: t("sched_daily") }), h("option", { value: "interval", text: t("sched_interval") }));
    var tm = h("input", { type: "time", value: "07:30" });
    var ev = h("input", { type: "number", value: "60", min: "1", max: "10080" });
    var names = lang === "en" ? DAYS_EN : DAYS_ES, dayBoxes = [];
    var daysRow = h("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:6px" }, names.map(function (n, i) {
      var cb = h("input", { type: "checkbox", checked: true }); dayBoxes.push(cb); return h("label", { class: "chk" }, cb, h("span", { text: n })); }));
    var dailyBox = h("div", null, h("div", { class: "field" }, h("div", { class: "fl", text: t("sched_time") }), tm), daysRow);
    var intBox = h("div", { class: "hidden" }, h("div", { class: "field" }, h("div", { class: "fl", text: t("sched_every") }), ev));
    kind.addEventListener("change", function () { dailyBox.classList.toggle("hidden", kind.value !== "daily"); intBox.classList.toggle("hidden", kind.value !== "interval"); });
    clear(form).appendChild(h("div", { style: "margin-top:16px;padding-top:12px;border-top:1px solid var(--border)" }, h("b", { text: t("sched_new") }),
      h("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px" }, nm, kind), dailyBox, intBox,
      h("div", { class: "muted", style: "margin-top:8px;font-size:12px", text: t("sched_hint") }),
      h("button", { class: "btn primary", style: "margin-top:10px", text: t("create"), onclick: function () {
        var body = { name: nm.value.trim() || w.name, kind: kind.value };
        if (kind.value === "daily") { body.time = tm.value; body.days = dayBoxes.map(function (c, i) { return c.checked ? i : -1; }).filter(function (i) { return i >= 0; });
          if (!body.days.length) { toast(lang === "es" ? "Marque al menos un día" : "Select at least one day"); return; } }
        else body.every_minutes = Number(ev.value);
        api("POST", "/api/workflows/" + w.id + "/schedules", body).then(function () { nm.value = ""; load(); }, function (e) { toast(e.message); });
      } })));
    load();
  }
  function allSchedulesDialog() {
    var box = h("div", { text: "…" });
    dialog(t("schedules"), box, null, true);
    function load() { api("GET", "/api/schedules").then(function (r) { clear(box).appendChild(schedTable(r.schedules, load, true)); }, function (e) { box.textContent = e.message; }); }
    load();
  }

  // ============================================================ ajustes y administración
  function settingsDialog() {
    var pwc = h("input", { type: "password" }), pwn = h("input", { type: "password" });
    dialog(t("settings"), h("div", null,
      h("div", { class: "field" }, h("div", { class: "fl", text: t("language") }),
        h("select", { onchange: function (e) { setLang(e.target.value); } }, h("option", { value: "es", text: "Español", selected: lang === "es" }), h("option", { value: "en", text: "English", selected: lang === "en" }))),
      h("div", { class: "field" }, h("div", { class: "fl", text: t("theme") }),
        h("select", { onchange: function (e) { setTheme(e.target.value); } },
          h("option", { value: "light", text: t("light"), selected: document.documentElement.getAttribute("data-theme") === "light" }),
          h("option", { value: "dark", text: t("dark"), selected: document.documentElement.getAttribute("data-theme") === "dark" }))),
      h("hr", { style: "border:none;border-top:1px solid var(--border);margin:14px 0" }),
      h("div", { class: "field" }, h("div", { class: "fl", text: t("current_pw") }), pwc),
      h("div", { class: "field" }, h("div", { class: "fl", text: t("new_pw") }), pwn)),
      [{ label: t("close") }, { label: t("reset_pw"), cls: "primary", keep: true, fn: function (close) {
        if (!pwc.value || !pwn.value) return false;
        api("POST", "/api/me/password", { current: pwc.value, "new": pwn.value }).then(function () { close(); toast(t("saved")); }, function (e) { toast(e.message); });
      } }]);
  }

  var STATUS_ES = { enabled: "Habilitado", pending: "Pendiente de aprobación", changed: "Cambió (reaprobar)", disabled: "Deshabilitado", invalid: "Inválido" };
  function pluginsDialog() {
    var body = h("div", { text: "…" });
    var dlg = dialog(t("plugins"), body, [{ label: lang === "es" ? "✨ Crear con IA" : "✨ Create with AI", cls: "primary", keep: true, fn: function () { pluginAiDialog(function (list) { refresh(list); }); } }, { label: t("reload_plugins"), keep: true, fn: function () {
      api("POST", "/api/plugins/reload").then(function (d) { setPlugins(d.plugins); draw(d.plugins); }, function (e) { toast(e.message); }); } }, { label: t("close") }], true);
    function draw(list) {
      clear(body);
      var tb = h("tbody");
      list.forEach(function (p) {
        var cls = p.status === "enabled" ? "ok" : p.status === "invalid" ? "err" : "warn";
        var act = null;
        if (p.ok) act = p.status === "enabled"
          ? h("button", { class: "btn sm", text: t("disable"), onclick: function () { act_(p, "disable"); } })
          : h("button", { class: "btn sm primary", text: p.status === "disabled" ? t("enable") : t("approve"), onclick: function () { act_(p, "enable"); } });
        tb.appendChild(h("tr", null,
          h("td", { text: (p.icon || "🧩") + " " + p.name }),
          h("td", null, h("div", { class: "mono", text: p.id + (p.version ? " v" + p.version : "") }), h("div", { class: "muted", style: "font-size:12px", text: (p.description || "").slice(0, 140) })),
          h("td", { text: p.kind || "" }), h("td", null, h("span", { class: "badge " + cls, text: STATUS_ES[p.status] || p.status }),
            p.errors && p.errors.length ? h("div", { class: "err-text", style: "font-size:12px;color:var(--err)", text: p.errors.join("; ") }) : null),
          h("td", { class: "mono muted", style: "font-size:11px", text: (p.hash || "").slice(0, 10) }),
          h("td", { style: "white-space:nowrap" }, act, " ", canAdm(p) ? [
            h("button", { class: "btn sm", text: lang === "es" ? "Editar" : "Edit", onclick: function () { pluginEditDialog(p, refresh); } }), " ",
            h("button", { class: "btn sm", text: lang === "es" ? "Renombrar" : "Rename", onclick: function () { pluginRenameDialog(p, refresh); } }), " ",
            h("button", { class: "btn sm danger", text: lang === "es" ? "Eliminar" : "Delete", onclick: function () { pluginDeleteDialog(p, refresh); } })] : null)));
      });
      body.appendChild(h("table", null, h("thead", null, h("tr", null, h("th", { text: t("name") }), h("th", { text: "ID" }), h("th", { text: "Tipo" }), h("th", { text: t("status") }), h("th", { text: "Hash" }), h("th"))), tb));
      body.appendChild(h("div", { class: "muted", style: "margin-top:10px;font-size:12px", text: lang === "es"
        ? "Un plugin es código que se ejecuta en este servidor. Apruebe solo los que haya revisado. Si un plugin cambia en disco, queda bloqueado hasta que lo reapruebe."
        : "A plugin is code that runs on this server. Approve only plugins you have reviewed. If a plugin changes on disk it is blocked until re-approved." }));
    }
    function act_(p, action) {
      api("POST", "/api/plugins/" + p.id + "/" + action).then(function (d) { setPlugins(d.plugins); draw(d.plugins); }, function (e) { toast(e.message); });
    }
    function canAdm(p) { return /^[a-z][a-z0-9_]*$/.test(p.id || ""); }
    function refresh(list) { if (list) { setPlugins(list); draw(list); } else api("GET", "/api/plugins").then(function (d) { setPlugins(d.plugins); draw(d.plugins); }); }
    api("GET", "/api/plugins").then(function (d) { setPlugins(d.plugins); draw(d.plugins); });
  }

  // ---- crear plugins con una IA: prompt para copiar + importar lo que devuelve (solo administrador)
  function copyToClipboard(text, ta) {
    function fallback() { ta.select(); try { return document.execCommand("copy"); } catch (e) { return false; } }
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return fallback(); });
    return Promise.resolve(fallback());
  }
  function pluginAiDialog(done) {
    var es = lang === "es";
    var prompt = h("textarea", { class: "code", rows: 9, readonly: "readonly", spellcheck: "false" });
    var paste = h("textarea", { class: "code", rows: 9, spellcheck: "false", "data-ref": "1",
      placeholder: es ? "=== plugin.json ===\n{...}\n=== task.py ===\ndef run(config, ctx): ..." : "=== plugin.json ===\n{...}\n=== task.py ===\ndef run(config, ctx): ..." });
    var msg = h("div", { class: "help", style: "margin-top:6px;min-height:18px" });
    var over = h("input", { type: "checkbox" });
    api("GET", "/api/plugins/prompt").then(function (d) { prompt.value = d.prompt; }, function (e) { prompt.value = e.message; });
    var body = h("div", null,
      h("div", { class: "field" },
        h("div", { class: "fl", text: es ? "1. Copie este prompt y péguelo en su IA (Claude, ChatGPT, Copilot…)" : "1. Copy this prompt into your AI assistant" }),
        prompt,
        h("div", { style: "margin-top:6px" }, h("button", { class: "btn sm", text: es ? "📋 Copiar prompt" : "📋 Copy prompt", onclick: function () {
          copyToClipboard(prompt.value, prompt).then(function (ok) { msg.style.color = ""; msg.textContent = ok ? (es ? "Copiado. Reemplace [DESCRIBE AQUÍ LA TAREA] por lo que necesita." : "Copied. Replace the [DESCRIBE…] placeholder.") : (es ? "No se pudo copiar: seleccione el texto y use Ctrl+C." : "Could not copy: select the text and press Ctrl+C."); });
        } }))),
      h("div", { class: "field" },
        h("div", { class: "fl", text: es ? "2. Pegue aquí la respuesta de la IA (los bloques «=== archivo ===»)" : "2. Paste the AI answer here" }),
        paste,
        h("label", { class: "muted", style: "display:block;margin-top:6px;font-size:12px" }, over, es ? " Reemplazar si ya existe un plugin con el mismo id" : " Replace if the id already exists")),
      msg,
      h("div", { class: "muted", style: "margin-top:8px;font-size:12px", text: es
        ? "Se valida antes de instalar y queda PENDIENTE: revise el código (Editar) antes de aprobarlo. Un plugin hecho por una IA es código que se ejecuta en este servidor."
        : "It is validated before install and stays PENDING: review the code before approving. AI-written plugins run as code on this server." }));
    dialog(es ? "Crear un plugin con IA" : "Create a plugin with AI", body, [{ label: t("close") }, { label: es ? "Instalar plugin" : "Install plugin", cls: "primary", keep: true, fn: function (close) {
      msg.style.color = ""; msg.textContent = "…";
      api("POST", "/api/plugins/import", { text: paste.value, overwrite: over.checked }).then(function (d) {
        toast((es ? "Plugin instalado (pendiente de aprobación): " : "Plugin installed (pending approval): ") + d.id);
        close(); done(d.plugins);
      }, function (e) { msg.style.color = "var(--err)"; msg.textContent = e.message; });
      return false;
    } }], true);
  }

  // ---- editar / renombrar / eliminar plugins (solo administrador)
  function pluginEditDialog(p, done) {
    var es = lang === "es", cur = null, isNew = false, dirty = false;
    var sel = h("select", { style: "width:auto;max-width:260px" });
    var ta = h("textarea", { class: "code", rows: 22, spellcheck: "false", "data-ref": "1" });
    var msg = h("div", { class: "help", style: "margin-top:6px;min-height:18px" });
    ta.addEventListener("input", function () { dirty = true; msg.textContent = ""; });
    ta.addEventListener("keydown", function (ev) {
      if (ev.key === "Tab") { ev.preventDefault(); var a = ta.selectionStart; ta.setRangeText("    ", a, ta.selectionEnd, "end"); dirty = true; }
    });
    function load(name) {
      api("GET", "/api/plugins/" + p.id + "/file?name=" + encodeURIComponent(name)).then(function (d) {
        cur = name; isNew = false; dirty = false; ta.value = d.content; msg.textContent = "";
      }, function (e) { msg.textContent = e.message; msg.style.color = "var(--err)"; });
    }
    function fillFiles(keep) {
      return api("GET", "/api/plugins/" + p.id + "/files").then(function (d) {
        clear(sel);
        d.files.forEach(function (f) { sel.appendChild(h("option", { value: f.name, text: f.name, selected: f.name === keep })); });
        sel.appendChild(h("option", { value: "__new__", text: es ? "+ Archivo nuevo…" : "+ New file…" }));
        return d;
      });
    }
    sel.addEventListener("change", function () {
      var v = sel.value;
      if (dirty && !window.confirm(es ? "Hay cambios sin guardar. ¿Descartarlos?" : "Discard unsaved changes?")) { sel.value = cur; return; }
      if (v === "__new__") {
        prompt_(es ? "Archivo nuevo" : "New file", es ? "Nombre (ej. ayuda.py)" : "Name (e.g. helper.py)", "", function (name) {
          cur = name; isNew = true; dirty = true; ta.value = ""; clear(sel).appendChild(h("option", { value: name, text: name + " (" + (es ? "nuevo" : "new") + ")" })); sel.value = name;
        });
        sel.value = cur; return;
      }
      load(v);
    });
    function save() {
      if (!cur) return false;
      msg.style.color = ""; msg.textContent = es ? "Validando y guardando…" : "Validating and saving…";
      api("PUT", "/api/plugins/" + p.id + "/file", { name: cur, content: ta.value }).then(function (d) {
        dirty = false; var was = isNew; isNew = false; msg.style.color = "var(--ok)";
        msg.textContent = es ? "✓ Guardado. " + (p.status === "enabled" ? "El plugin sigue habilitado con el contenido nuevo." : "Recuerde habilitarlo.")
                             : "✓ Saved. " + (p.status === "enabled" ? "Plugin stays enabled with the new content." : "Remember to enable it.");
        if (done) done(d.plugins);
        if (was) fillFiles(cur);
      }, function (e) { msg.style.color = "var(--err)"; msg.textContent = e.message; });
      return false;
    }
    var body = h("div", null,
      h("div", { class: "muted", style: "font-size:12px;margin-bottom:8px", text: es
        ? "Edita el código del plugin en el servidor. Se valida antes de guardar (JSON, sintaxis, manifiesto). Si estaba habilitado, queda aprobado con el contenido nuevo: usted es quien lo aprueba."
        : "Edits the plugin code on the server. It is validated before saving. If it was enabled it stays approved with the new content: you are the approver." }),
      h("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:8px" }, h("b", { text: p.icon + " " + p.name }), sel), ta, msg);
    dialog((es ? "Editar plugin · " : "Edit plugin · ") + p.id, body, [{ label: es ? "Guardar" : "Save", cls: "primary", keep: true, fn: save }, { label: t("close") }], true);
    fillFiles("plugin.json").then(function (d) { var first = d.files.some(function (f) { return f.name === "task.py"; }) ? "task.py" : "plugin.json"; sel.value = first; load(first); });
  }

  function pluginRenameDialog(p, done) {
    var es = lang === "es";
    var nm = h("input", { type: "text", value: p.name || "", maxlength: "80" }), id = h("input", { type: "text", value: p.id, class: "mono" });
    var body = h("div", null,
      h("div", { class: "field" }, h("div", { class: "fl", text: es ? "Nombre visible" : "Display name" }), nm),
      h("div", { class: "field" }, h("div", { class: "fl", text: "ID (avanzado)" }), id,
        h("div", { class: "help", text: es ? "Cambiar el ID renombra la carpeta y actualiza automáticamente todos los workflows que usan este plugin. Minúsculas, números y _."
                                         : "Changing the ID renames the folder and updates every workflow that uses this plugin. Lowercase, digits and _." })));
    dialog((es ? "Renombrar plugin · " : "Rename plugin · ") + p.id, body, [{ label: t("cancel") }, { label: t("save"), cls: "primary", keep: true, fn: function (close) {
      var b = {}; if (nm.value.trim() !== p.name) b.name = nm.value.trim(); if (id.value.trim() !== p.id) b.id = id.value.trim();
      if (!b.name && !b.id) { close(); return false; }
      api("POST", "/api/plugins/" + p.id + "/rename", b).then(function (d) {
        close(); if (d.migrated_workflows) toast((es ? "Workflows actualizados: " : "Workflows updated: ") + d.migrated_workflows); if (done) done(d.plugins);
      }, function (e) { toast(e.message); });
      return false;
    } }]);
  }

  function pluginDeleteDialog(p, done) {
    var es = lang === "es";
    api("GET", "/api/plugins/" + p.id + "/files").then(function (f) {
      var used = f.used_by || [];
      var body = h("div", null,
        h("div", { text: es ? "¿Eliminar el plugin «" + p.name + "» (" + p.id + ")?" : "Delete plugin “" + p.name + "” (" + p.id + ")?" }),
        h("div", { class: "muted", style: "margin-top:8px", text: es
          ? "Su carpeta se mueve a plugins/_eliminados/ (se puede recuperar a mano). Los workflows que lo usen mostrarán un error hasta que lo reemplace."
          : "Its folder is moved to plugins/_eliminados/ (recoverable by hand). Workflows that use it will show an error until you replace it." }),
        used.length ? h("div", { style: "margin-top:8px;color:var(--warn)", text: (es ? "Lo usan " + used.length + " workflow(s): " : "Used by " + used.length + " workflow(s): ") + used.slice(0, 8).join(", ") }) : null);
      dialog(es ? "Eliminar plugin" : "Delete plugin", body, [{ label: t("cancel") }, { label: es ? "Eliminar" : "Delete", cls: "danger", keep: true, fn: function (close) {
        api("DELETE", "/api/plugins/" + p.id).then(function (d) { close(); toast(es ? "Plugin eliminado" : "Plugin deleted"); if (done) done(d.plugins); }, function (e) { toast(e.message); });
        return false;
      } }]);
    }, function (e) { toast(e.message); });
  }

  function usersDialog() {
    var body = h("div", { text: "…" });
    dialog(t("users"), body, null, true);
    function draw(users) {
      clear(body);
      var tb = h("tbody");
      users.forEach(function (u) {
        var role = h("select", { style: "width:auto", onchange: function () { upd(u, { role: role.value }); } },
          ["admin", "editor", "viewer"].map(function (r) { return h("option", { value: r, text: r, selected: u.role === r }); }));
        tb.appendChild(h("tr", null, h("td", { text: u.username }), h("td", { text: u.display_name || "" }), h("td", null, role),
          h("td", null, h("label", { class: "chk" }, h("input", { type: "checkbox", checked: u.active, onchange: function (e) { upd(u, { active: e.target.checked }); } }))),
          h("td", { class: "muted", text: fmtDate(u.last_login) }),
          h("td", null, h("button", { class: "btn sm", text: t("reset_pw"), onclick: function () {
            prompt_(t("reset_pw") + " · " + u.username, t("new_pw"), "", function (pw) { upd(u, { password: pw, must_change_password: true }); }); } }))));
      });
      body.appendChild(h("table", null, h("thead", null, h("tr", null, h("th", { text: t("user") }), h("th", { text: t("name") }), h("th", { text: t("role") }), h("th", { text: t("active") }), h("th", { text: "Último acceso" }), h("th"))), tb));
      var nu = h("input", { type: "text", placeholder: t("user") }), np = h("input", { type: "password", placeholder: t("password") + " (" + t("pw_min") + ")" });
      var nd = h("input", { type: "text", placeholder: t("display_name") });
      var nr = h("select", null, ["editor", "viewer", "admin"].map(function (r) { return h("option", { value: r, text: r }); }));
      var mc = h("input", { type: "checkbox", checked: true });
      body.appendChild(h("div", { style: "margin-top:16px" }, h("b", { text: t("new_user") }),
        h("div", { style: "display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:6px" }, nu, nd, np, nr),
        h("label", { class: "chk", style: "margin-top:6px" }, mc, h("span", { text: t("must_change") })),
        h("button", { class: "btn primary", style: "margin-top:8px", text: t("create"), onclick: function () {
          api("POST", "/api/users", { username: nu.value.trim(), password: np.value, role: nr.value, display_name: nd.value.trim(), must_change_password: mc.checked })
            .then(load, function (e) { toast(e.message); }); } })));
    }
    function upd(u, patch) { api("PUT", "/api/users/" + u.id, patch).then(load, function (e) { toast(e.message); load(); }); }
    function load() { api("GET", "/api/users").then(function (d) { draw(d.users); }); }
    load();
  }

  function auditDialog() {
    var body = h("div", { text: "…" });
    dialog(t("audit"), body, null, true);
    api("GET", "/api/audit?limit=300").then(function (d) {
      clear(body);
      var tb = h("tbody");
      d.audit.forEach(function (a) {
        tb.appendChild(h("tr", null, h("td", { class: "muted", text: fmtDate(a.ts || a.created_at) }), h("td", { text: a.username || a.user || "" }),
          h("td", { class: "mono", text: a.action }), h("td", { text: a.detail || "" }), h("td", { class: "muted", text: a.ip || "" })));
      });
      body.appendChild(h("table", null, h("thead", null, h("tr", null, h("th", { text: "Fecha" }), h("th", { text: t("user") }), h("th", { text: "Acción" }), h("th", { text: "Detalle" }), h("th", { text: "IP" }))), tb));
    }, function (e) { body.textContent = e.message; });
  }

  function secretsDialog() {
    var body = h("div", { text: "…" });
    dialog(t("secrets"), body);
    function load() { api("GET", "/api/secrets").then(draw, function (e) { toast(e.message); }); }
    function draw(d) {
      clear(body);
      body.appendChild(h("div", { class: "muted", style: "margin-bottom:8px;font-size:12px", text: t("sec_hint") }));
      var tb = h("tbody");
      d.secrets.forEach(function (s) {
        tb.appendChild(h("tr", null, h("td", { class: "mono", text: s.name }), h("td", { text: s.scope === "global" ? t("global") : t("mine") }), h("td", { class: "muted", text: fmtDate(s.updated_at) }),
          h("td", null, (s.scope === "global" && S.user.role !== "admin") || S.user.role === "viewer" ? null :
            h("button", { class: "btn sm danger", text: "✕", onclick: function () { api("DELETE", "/api/secrets/" + encodeURIComponent(s.name) + "?scope=" + (s.scope === "global" ? "global" : "me")).then(load, function (e) { toast(e.message); }); } }))));
      });
      body.appendChild(h("table", null, h("thead", null, h("tr", null, h("th", { text: t("name") }), h("th", { text: t("scope") }), h("th", { text: "" }), h("th"))), tb));
      if (S.user.role === "viewer") return;
      var nm = h("input", { type: "text", placeholder: "nombre_de_la_clave" }), val = h("input", { type: "password", placeholder: t("value"), autocomplete: "off" });
      var sc = h("select", { style: "width:auto" }, h("option", { value: "me", text: t("mine") }), S.user.role === "admin" ? h("option", { value: "global", text: t("global") }) : null);
      body.appendChild(h("div", { style: "display:grid;grid-template-columns:1fr 1fr auto auto;gap:6px;margin-top:14px" }, nm, val, sc,
        h("button", { class: "btn primary", text: t("add_secret"), onclick: function () {
          api("PUT", "/api/secrets/" + encodeURIComponent(nm.value.trim()), { value: val.value, scope: sc.value }).then(load, function (e) { toast(e.message); }); } })));
    }
    load();
  }

  window.addEventListener("beforeunload", function () { if (S.saveState === "dirty") flushSave(); });
  start();
})();
