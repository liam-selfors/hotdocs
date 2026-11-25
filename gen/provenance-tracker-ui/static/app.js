export function hiddenByStatus(nodes, filter) {
  const result = {};
  for (const node of nodes) {
    result[node.id] = filter !== "all" && node.status !== filter;
  }
  return result;
}

export function init(document) {
  for (const button of document.querySelectorAll("button[data-filter]")) {
    button.addEventListener("click", () => {
      const items = [...document.querySelectorAll("li.node")];
      const nodes = items.map((item) => ({
        id: item.dataset.nodeId,
        status: item.dataset.status,
      }));
      const hidden = hiddenByStatus(nodes, button.dataset.filter);
      for (const item of items) {
        item.hidden = hidden[item.dataset.nodeId];
      }
    });
  }
}
