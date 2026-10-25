// Pokédex page: keep the list highlight in sync with HTMX navigation.
// Without this, opening another entry (from the list or the family section)
// would swap the right pane but leave the previous species highlighted.
document.addEventListener("htmx:beforeRequest", (event) => {
  const link = event.detail.elt.closest("[data-species-link]");
  if (!link) return;
  const number = link.getAttribute("href").match(/(\d+)\/$/)[1];

  document
    .querySelectorAll("#species-list [aria-current]")
    .forEach((el) => el.removeAttribute("aria-current"));
  const listLink = document.querySelector(`#species-list a[href$="/${number}/"]`);
  if (listLink) listLink.setAttribute("aria-current", "page");

  // Remember the selection so that filtering the list keeps the highlight
  document.querySelector('#dex-filters input[name="selected"]').value = number;
});
