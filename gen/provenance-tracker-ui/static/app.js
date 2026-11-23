export function hiddenByStatus(nodes, filter) {
  const result = {};
  for (const node of nodes) {
    result[node.id] = filter !== "all" && node.status !== filter;
  }
  return result;
}

export function init(document) {
  const items = [...document.querySelectorAll("li.node")];
  for (const button of document.querySelectorAll("button[data-filter]")) {
    button.addEventListener("click", () => {
      const nodes = items.map((li) => ({
        id: li.getAttribute("data-node-id"),
        status: li.getAttribute("data-status"),
      }));
      const hidden = hiddenByStatus(nodes, button.getAttribute("data-filter"));
      for (const li of items) {
        li.hidden = hidden[li.getAttribute("data-node-id")];
      }
    });
  }
}
