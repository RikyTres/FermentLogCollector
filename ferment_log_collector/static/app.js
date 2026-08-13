function slugify(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function attachSlugAutocomplete(form) {
  const nameInput = form.querySelector('input[name="name"]');
  const slugInput = form.querySelector('input[name="slug"]');
  if (!nameInput || !slugInput) {
    return;
  }

  let lastAutoSlug = slugInput.value || slugify(nameInput.value);
  let slugEdited = slugInput.value !== "" && slugInput.value !== lastAutoSlug;

  nameInput.addEventListener("input", () => {
    if (slugEdited) {
      return;
    }
    lastAutoSlug = slugify(nameInput.value);
    slugInput.value = lastAutoSlug;
  });

  slugInput.addEventListener("input", () => {
    const generated = slugify(nameInput.value);
    slugEdited = slugInput.value !== "" && slugInput.value !== generated && slugInput.value !== lastAutoSlug;
    if (!slugEdited) {
      lastAutoSlug = slugInput.value;
    }
  });

  slugInput.addEventListener("blur", () => {
    slugInput.value = slugify(slugInput.value);
    lastAutoSlug = slugInput.value;
    slugEdited = slugInput.value !== "" && slugInput.value !== slugify(nameInput.value);
  });
}

document.querySelectorAll("form.device-form").forEach(attachSlugAutocomplete);

function attachAddDeviceToggle() {
  const openButton = document.querySelector("#add-device-open");
  const closeButton = document.querySelector("#add-device-close");
  const panel = document.querySelector("#add-device-panel");
  if (!openButton || !closeButton || !panel) {
    return;
  }

  function setExpanded(expanded) {
    panel.hidden = !expanded;
    openButton.hidden = expanded;
    openButton.setAttribute("aria-expanded", String(expanded));
  }

  setExpanded(!panel.hidden);

  openButton.addEventListener("click", () => {
    setExpanded(true);
    panel.querySelector('input[name="name"]')?.focus();
  });

  closeButton.addEventListener("click", () => {
    setExpanded(false);
    openButton.focus();
  });
}

attachAddDeviceToggle();

function attachLogViewer() {
  const viewer = document.querySelector("#log-viewer");
  const title = document.querySelector("#log-viewer-title");
  const summary = document.querySelector("#log-viewer-summary");
  const tailSelect = document.querySelector("#log-viewer-tail");
  const refreshButton = document.querySelector("#log-viewer-refresh");
  const downloadLink = document.querySelector("#log-viewer-download");
  const closeButton = document.querySelector("#log-viewer-close");
  const errorBox = document.querySelector("#log-viewer-error");
  const tableWrap = document.querySelector("#log-viewer-table-wrap");
  const table = document.querySelector("#log-viewer-table");
  const text = document.querySelector("#log-viewer-text");
  if (!viewer || !title || !summary || !tailSelect || !refreshButton || !downloadLink || !closeButton || !errorBox || !tableWrap || !table || !text) {
    return;
  }

  let currentUrl = "";

  function resetOutput() {
    errorBox.hidden = true;
    errorBox.textContent = "";
    tableWrap.hidden = true;
    table.replaceChildren();
    text.hidden = true;
    text.textContent = "";
  }

  function setLoading(loading) {
    refreshButton.disabled = loading;
    refreshButton.textContent = loading ? "Loading..." : "Refresh";
  }

  function renderCsv(payload) {
    const columns = payload.columns || [];
    const rows = payload.rows || [];
    const header = document.createElement("thead");
    const headerRow = document.createElement("tr");
    columns.forEach((column) => {
      const th = document.createElement("th");
      th.textContent = column;
      headerRow.append(th);
    });
    header.append(headerRow);

    const body = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((_, index) => {
        const td = document.createElement("td");
        td.textContent = row[index] || "";
        tr.append(td);
      });
      body.append(tr);
    });

    table.replaceChildren(header, body);
    tableWrap.hidden = false;
    summary.textContent = `Showing ${rows.length} of ${payload.total_rows || 0} data rows.`;
  }

  function renderText(payload) {
    const lines = payload.lines || [];
    text.textContent = lines.join("\n");
    text.hidden = false;
    summary.textContent = `Showing ${lines.length} of ${payload.total_lines || 0} lines.`;
  }

  async function loadPreview() {
    if (!currentUrl) {
      return;
    }

    resetOutput();
    setLoading(true);
    const separator = currentUrl.includes("?") ? "&" : "?";
    const previewUrl = `${currentUrl}${separator}tail=${encodeURIComponent(tailSelect.value)}`;

    try {
      const response = await fetch(previewUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        let detail = `Unable to load preview (${response.status}).`;
        try {
          const payload = await response.json();
          detail = payload.detail || detail;
        } catch {
          // Keep the status-based message when the response is not JSON.
        }
        throw new Error(detail);
      }

      const payload = await response.json();
      if (payload.kind === "text") {
        renderText(payload);
      } else {
        renderCsv(payload);
      }
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      setLoading(false);
    }
  }

  document.querySelectorAll("[data-log-viewer-open]").forEach((button) => {
    button.addEventListener("click", () => {
      currentUrl = button.dataset.logUrl || "";
      title.textContent = button.dataset.logTitle || "Log viewer";
      downloadLink.href = button.dataset.logDownload || "#";
      button.closest("details")?.removeAttribute("open");
      viewer.hidden = false;
      viewer.scrollIntoView({ block: "start", behavior: "smooth" });
      loadPreview();
    });
  });

  refreshButton.addEventListener("click", loadPreview);
  tailSelect.addEventListener("change", loadPreview);
  closeButton.addEventListener("click", () => {
    viewer.hidden = true;
  });
}

attachLogViewer();
