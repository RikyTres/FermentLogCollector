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
