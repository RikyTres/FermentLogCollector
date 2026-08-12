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
