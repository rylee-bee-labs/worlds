/* Worlds — "First light", the first-run setup wizard (dependency-free).
   Plain ES2017+, progressive enhancement over the static HTML:
   every step is a real <section> with a heading; navigation moves
   focus to the heading and announces through the live region.
   Nothing moves unless the person asks: the progress dots are static. */
(function () {
  "use strict";

  var STEPS = [
    { id: "step-welcome", label: "First light" },
    { id: "step-preparing", label: "Getting things ready" },
    { id: "step-auth", label: "Sign-in" },
    { id: "step-comfort", label: "Comfort" },
    { id: "step-companion", label: "Companion" },
    { id: "step-finish", label: "Welcome aboard" }
  ];
  var COMFORT = 3, COMPANION = 4, FINISH = 5;
  var THEME_KEY = "pw-station-theme";
  var THEME_LABELS = { starfield: "Starfield", doorways: "Doorways", plain: "Plain" };
  var current = 0;
  var provisioned = false;
  var provisioning = false;
  var crewLoaded = false;
  var savedCompanion = null;

  function $(id) { return document.getElementById(id); }

  function showStep(index) {
    current = index;
    STEPS.forEach(function (step, i) {
      var el = $(step.id);
      if (el) { el.hidden = i !== index; }
    });
    document.body.setAttribute("data-step", STEPS[index].id);
    var dots = $("dots").children;
    for (var d = 0; d < dots.length; d++) {
      dots[d].className = d < index ? "done" : d === index ? "here" : "";
    }
    var stepInfo = STEPS[index];
    $("progress").textContent =
      "Step " + (index + 1) + " of " + STEPS.length + ": " + stepInfo.label;
    $("live").textContent = stepInfo.label + ", step " + (index + 1) +
      " of " + STEPS.length;
    var heading = document.querySelector("#" + stepInfo.id + " h2");
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus();
    }
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        return { status: resp.status, data: data };
      });
    });
  }

  function joinWarnings(data) {
    var w = (data && data.warnings) || [];
    var detail = (data && data.detail) || "";
    if (detail && w.indexOf(detail) === -1) { w = [detail].concat(w); }
    return w;
  }

  /* ── Step 2: invisible provisioning ── */

  function runProvision() {
    if (provisioning || provisioned) { return; }
    provisioning = true;
    $("prepare-error").hidden = true;
    $("prepare-status").hidden = false;
    postJSON("/api/setup-wizard/provision", {}).then(function (r) {
      provisioning = false;
      if (r.status === 404) {
        // Setup finished elsewhere (or FORCE_SETUP was turned off):
        // honest redirect instead of a dead end.
        window.location.href = "/";
        return;
      }
      if (r.status === 200 && r.data && r.data.ok) {
        provisioned = true;
        $("prepare-status").hidden = true;
        showStep(2);
        return;
      }
      var lines = joinWarnings(r.data);
      $("prepare-status").hidden = true;
      $("prepare-error").hidden = false;
      $("prepare-error-detail").textContent = lines.length
        ? lines.join(" ")
        : "The app could not finish preparing itself. Press Retry; if it " +
          "keeps failing, check that the server's data folder is " +
          "writable, then reload this page.";
    }).catch(function () {
      provisioning = false;
      $("prepare-status").hidden = true;
      $("prepare-error").hidden = false;
      $("prepare-error-detail").textContent =
        "This page could not talk to the server (network problem or the " +
        "server restarted). Press Retry, or reload the page.";
    });
  }

  /* ── Step 3: auth choice ── */

  function selectedAuth() {
    var radios = document.getElementsByName("auth-choice");
    for (var i = 0; i < radios.length; i++) {
      if (radios[i].checked) { return radios[i].value; }
    }
    return "local";
  }

  function syncAuthFields() {
    $("oidc-fields").hidden = selectedAuth() !== "oidc";
    if ($("oidc-fields").hidden) {
      $("oidc-test-result").hidden = true;
    }
  }

  function showAuthWarnings(warnings) {
    var box = $("auth-warnings");
    var list = $("auth-warnings-list");
    list.textContent = "";
    if (!warnings || !warnings.length) {
      box.hidden = true;
      return;
    }
    warnings.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    box.hidden = false;
  }

  /* Blocking findings pause the flow for an explicit "Continue
     anyway" (owner decision 2026-09-22); informational notes never
     pause — showAuthWarnings above handles those. */
  function showAuthBlocking(blocking) {
    var box = $("auth-blocking");
    var list = $("auth-blocking-list");
    list.textContent = "";
    if (!blocking || !blocking.length) {
      box.hidden = true;
      return;
    }
    blocking.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    box.hidden = false;
    box.querySelector("h3, .alert-heading").setAttribute("tabindex", "-1");
    box.querySelector("h3, .alert-heading").focus();
    $("live").textContent = "Needs your attention before you continue: " +
      blocking.join(" ");
  }

  function runTestConnection() {
    var issuer = $("oidc-issuer").value;
    var box = $("oidc-test-result");
    var button = $("btn-test-oidc");
    box.hidden = false;
    box.className = "test-result testing";
    box.textContent = "";
    var p = document.createElement("p");
    p.className = "verdict";
    p.textContent = "Testing… contacting the sign-in server.";
    box.appendChild(p);
    button.disabled = true;
    postJSON("/api/setup-wizard/test-oidc", { issuer_url: issuer })
      .then(function (r) {
        button.disabled = false;
        var data = (r.data && r.data.data) || {};
        var status = data.status || "unreachable";
        box.className = "test-result " + status;
        box.textContent = "";
        var verdict = document.createElement("p");
        verdict.className = "verdict";
        var labels = {
          reachable: "✓ Success",
          unreachable: "✗ Could not reach it",
          bad_config: "✗ That does not look right"
        };
        verdict.textContent = labels[status] || "✗ Test failed";
        var detail = document.createElement("p");
        detail.textContent = data.detail ||
          "The test did not return a result. Check the address and try again.";
        box.appendChild(verdict);
        box.appendChild(detail);
        $("live").textContent = verdict.textContent + ". " + detail.textContent;
      })
      .catch(function () {
        button.disabled = false;
        box.className = "test-result unreachable";
        box.textContent = "";
        var verdict = document.createElement("p");
        verdict.className = "verdict";
        verdict.textContent = "✗ Test could not run";
        var detail = document.createElement("p");
        detail.textContent =
          "This page could not talk to the Worlds server. " +
          "Reload the page and try again.";
        box.appendChild(verdict);
        box.appendChild(detail);
      });
  }

  function submitAuthChoice() {
    var body = { choice: selectedAuth() };
    if (body.choice === "oidc") {
      body.issuer_url = $("oidc-issuer").value;
      body.client_id = $("oidc-client-id").value;
      body.client_secret_env = $("oidc-secret-env").value;
    }
    $("btn-auth-next").disabled = true;
    postJSON("/api/setup-wizard/auth-choice", body).then(function (r) {
      $("btn-auth-next").disabled = false;
      if (r.status === 200 && r.data && r.data.ok) {
        showAuthBlocking(r.data.blocking);
        showAuthWarnings(r.data.warnings);
        if (r.data.warnings && r.data.warnings.length) {
          // Informational notes, kept moving: none of them block
          // setup (e.g. the secret env var can be set later).
          $("live").textContent = "Saved. Notes: " + r.data.warnings.join(" ");
        }
        // Pause only when blocking: the person must explicitly
        // continue; notes alone never stop the flow.
        if (r.data.blocking && r.data.blocking.length) { return; }
        showStep(3);
        return;
      }
      if (r.status === 404) { window.location.href = "/"; return; }
      var lines = joinWarnings(r.data);
      showAuthWarnings(lines.length ? lines : [
        "Your choice could not be saved. Check the fields and try again."
      ]);
    }).catch(function () {
      $("btn-auth-next").disabled = false;
      showAuthWarnings([
        "This page could not talk to the server. Try again in a moment."
      ]);
    });
  }

  /* ── Step 4: comfort ── */

  function radioValue(name, fallback) {
    var radios = document.getElementsByName(name);
    for (var i = 0; i < radios.length; i++) {
      if (radios[i].checked) { return radios[i].value; }
    }
    return fallback;
  }

  function selectedTheme() { return radioValue("theme-choice", "starfield"); }

  /* The colour choice previews on this page at once and is kept on this
     device (the same localStorage key the app reads), never on the
     server. Storage can be blocked; the page still works. */
  function previewTheme() {
    document.documentElement.setAttribute("data-theme", selectedTheme());
  }

  function saveTheme() {
    try { window.localStorage.setItem(THEME_KEY, selectedTheme()); } catch (e) { /* private window */ }
  }

  function inlineError(boxId, detailId, text) {
    $(detailId).textContent = text;
    $(boxId).hidden = false;
    $("live").textContent = text;
  }

  function submitComfort() {
    $("btn-comfort-next").disabled = true;
    $("comfort-error").hidden = true;
    saveTheme();
    postJSON("/api/setup-wizard/comfort", {
      larger_text: $("comfort-larger-text").checked,
      gentle_animations: $("comfort-gentle-motion").checked,
      crew_on: $("comfort-crew").checked
    }).then(function (r) {
      $("btn-comfort-next").disabled = false;
      if (r.status === 200 && r.data && r.data.ok) {
        updateSummary();
        // With the crew off, Worlds speaks plainly: there is no
        // companion to pick, so that step steps aside.
        if ($("comfort-crew").checked) {
          loadCrew();
          showStep(COMPANION);
        } else {
          showStep(FINISH);
        }
        return;
      }
      if (r.status === 404) { window.location.href = "/"; return; }
      var lines = joinWarnings(r.data);
      inlineError("comfort-error", "comfort-error-detail", lines.join(" ") ||
        "Your comfort settings could not be saved. Try again.");
    }).catch(function () {
      $("btn-comfort-next").disabled = false;
      inlineError("comfort-error", "comfort-error-detail",
        "This page could not talk to the server. Try again in a moment.");
    });
  }

  /* ── Step 5: companion ── */

  function addCompanionChoice(entry) {
    var id = "companion-" + entry.id;
    if ($(id)) { return; }
    var label = document.createElement("label");
    label.className = "companion";
    label.setAttribute("for", id);
    var input = document.createElement("input");
    input.type = "radio";
    input.id = id;
    input.name = "companion-choice";
    input.value = entry.id;
    if (savedCompanion === entry.id) { input.checked = true; }
    var img = document.createElement("img");
    img.alt = "";
    img.setAttribute("aria-hidden", "true");
    if (entry.portrait_asset) { img.src = entry.portrait_asset; }
    var name = document.createElement("span");
    name.className = "companion-name";
    name.textContent = entry.name;
    var desc = document.createElement("span");
    desc.className = "companion-desc";
    desc.textContent = entry.blurb || "";
    label.appendChild(input);
    label.appendChild(img);
    label.appendChild(name);
    label.appendChild(desc);
    $("companion-grid").appendChild(label);
  }

  function loadCrew() {
    if (crewLoaded) { return; }
    fetch("/api/setup-wizard/crew").then(function (r) {
      if (r.status === 404) { window.location.href = "/"; return null; }
      return r.json();
    }).then(function (body) {
      if (!body) { return; }
      var crew = (body && body.data) || [];
      crew.forEach(addCompanionChoice);
      crewLoaded = true;
      $("companion-note").hidden = true;
    }).catch(function () {
      // Honest, and never a dead end: the Assistant is always there.
      $("companion-note").textContent =
        "The crew couldn’t be loaded just now, so only the Assistant is " +
        "shown. You can pick a companion later in Settings.";
      $("companion-note").hidden = false;
    });
  }

  function selectedCompanion() { return radioValue("companion-choice", ""); }

  function companionLabel() {
    var id = selectedCompanion();
    if (!id) { return "Assistant"; }
    var input = $("companion-" + id);
    var name = input && input.parentNode.querySelector(".companion-name");
    return name ? name.textContent : id;
  }

  function submitCompanion() {
    $("btn-companion-next").disabled = true;
    $("companion-error").hidden = true;
    var id = selectedCompanion();
    postJSON("/api/setup-wizard/companion", { companion_id: id || null })
      .then(function (r) {
        $("btn-companion-next").disabled = false;
        if (r.status === 200 && r.data && r.data.ok) {
          savedCompanion = id || null;
          updateSummary();
          showStep(FINISH);
          return;
        }
        if (r.status === 404) { window.location.href = "/"; return; }
        var lines = joinWarnings(r.data);
        inlineError("companion-error", "companion-error-detail", lines.join(" ") ||
          "Your companion could not be saved. Try again.");
      }).catch(function () {
        $("btn-companion-next").disabled = false;
        inlineError("companion-error", "companion-error-detail",
          "This page could not talk to the server. Try again in a moment.");
      });
  }

  function updateSummary() {
    $("summary-auth").textContent = selectedAuth() === "oidc"
      ? "My own SSO (" + ($("oidc-issuer").value || "sign-in server") + ")"
      : "Just me on this device";
    $("summary-theme").textContent = THEME_LABELS[selectedTheme()] || "Starfield";
    $("summary-text").textContent =
      $("comfort-larger-text").checked ? "Larger" : "Normal";
    $("summary-motion").textContent =
      $("comfort-gentle-motion").checked
        ? "Gentle animation"
        : "Calm (no animation)";
    var crewOn = $("comfort-crew").checked;
    $("summary-crew").textContent = crewOn ? "On" : "Off (Worlds speaks plainly)";
    $("summary-companion").textContent = crewOn ? companionLabel() : "None (the crew is off)";
  }

  /* ── Step 6: finish ── */

  function runFinish() {
    $("finish-actions").hidden = true;
    $("finish-error").hidden = true;
    $("finish-status").hidden = false;
    postJSON("/api/setup-wizard/finish", {}).then(function (r) {
      if (r.status === 200 && r.data && r.data.ok) {
        $("finish-status").textContent =
          "✓ Setup complete. Opening your World…";
        var target = (r.data.data && r.data.data.redirect) || "/";
        window.location.href = target;
        return;
      }
      $("finish-status").hidden = true;
      $("finish-actions").hidden = false;
      $("finish-error").hidden = false;
      var lines = joinWarnings(r.data);
      $("finish-error-detail").textContent = lines.join(" ") ||
        "The server could not complete setup. Press 'Try again'; if it " +
        "keeps failing, restart the container and reopen this page.";
    }).catch(function () {
      $("finish-status").hidden = true;
      $("finish-actions").hidden = false;
      $("finish-error").hidden = false;
      $("finish-error-detail").textContent =
        "This page could not talk to the server. Press 'Try again'.";
    });
  }

  /* ── wiring ── */

  function init() {
    $("btn-start").addEventListener("click", function () {
      showStep(1);
      runProvision();
    });
    $("btn-retry-prepare").addEventListener("click", runProvision);

    var radios = document.getElementsByName("auth-choice");
    for (var i = 0; i < radios.length; i++) {
      radios[i].addEventListener("change", syncAuthFields);
    }
    syncAuthFields();
    $("btn-test-oidc").addEventListener("click", runTestConnection);
    $("btn-auth-back").addEventListener("click", function () { showStep(0); });
    $("btn-auth-back-from-block").addEventListener("click", function () {
      $("auth-blocking").hidden = true;
      showStep(0);
    });
    $("btn-auth-continue").addEventListener("click", function () {
      // The choice was already saved (ok:true) — this only clears the
      // pause, exactly the explicit "Continue anyway" the owner chose.
      $("auth-blocking").hidden = true;
      showStep(3);
    });
    $("btn-auth-next").addEventListener("click", submitAuthChoice);

    $("btn-comfort-back").addEventListener("click", function () { showStep(2); });
    $("btn-comfort-next").addEventListener("click", submitComfort);
    var themes = document.getElementsByName("theme-choice");
    for (var t = 0; t < themes.length; t++) {
      themes[t].addEventListener("change", previewTheme);
    }

    $("btn-companion-back").addEventListener("click", function () { showStep(COMFORT); });
    $("btn-companion-next").addEventListener("click", submitCompanion);

    $("btn-finish-back").addEventListener("click", function () {
      showStep($("comfort-crew").checked ? COMPANION : COMFORT);
    });
    $("btn-finish").addEventListener("click", runFinish);
    $("btn-retry-finish").addEventListener("click", runFinish);

    // A colour chosen earlier on this device previews straight away.
    try {
      var stored = window.localStorage.getItem(THEME_KEY);
      if (stored && $("theme-" + stored)) { $("theme-" + stored).checked = true; }
    } catch (e) { /* storage blocked: the default stands */ }
    previewTheme();
    document.body.setAttribute("data-step", STEPS[0].id);
    $("dots").children[0].className = "here";

    // Restore progress after a refresh: ask the server what already
    // happened and resume at the right step.
    fetch("/api/setup-wizard/state").then(function (r) {
      if (r.status === 404) { window.location.href = "/"; return null; }
      return r.json();
    }).then(function (body) {
      if (!body || !body.data) { return; }
      var choices = body.data.choices || {};
      if (choices.auth_choice === "oidc" && choices.oidc) {
        $("auth-oidc").checked = true;
        $("oidc-issuer").value = choices.oidc.issuer || "";
        $("oidc-client-id").value = choices.oidc.client_id || "";
        $("oidc-secret-env").value = choices.oidc.client_secret_env || "";
        syncAuthFields();
      } else if (choices.auth_choice === "local") {
        $("auth-local").checked = true;
      }
      if (choices.comfort) {
        $("comfort-larger-text").checked = !!choices.comfort.larger_text;
        $("comfort-gentle-motion").checked = !!choices.comfort.gentle_animations;
        if (typeof choices.comfort.crew_on === "boolean") {
          $("comfort-crew").checked = choices.comfort.crew_on;
        }
      }
      if (typeof choices.companion_id === "string") {
        savedCompanion = choices.companion_id;
      }
    }).catch(function () { /* stay on step 1; honest default */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
