// Client-side search over the index the server pre-builds at startup.
(function () {
  const input = document.getElementById("search");
  const results = document.getElementById("search-results");
  let index = [];

  fetch("/static/cache/search-index.json")
    .then((r) => r.json())
    .then((data) => { index = data; })
    .catch(() => {});

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    results.replaceChildren();
    if (!q) { results.hidden = true; return; }
    for (const doc of index) {
      if (!(doc.title + " " + doc.summary).toLowerCase().includes(q)) continue;
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "/docs/" + doc.slug;
      a.textContent = doc.title;
      li.append(a);
      results.append(li);
    }
    results.hidden = results.children.length === 0;
  });
})();
