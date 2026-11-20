// Status filter for the provenance tracker page.

export function hiddenByStatus(nodes, filter) {
  const result = {};
  for (const node of nodes) {
    result[node.id] = filter !== "all" && node.status !== filter;
  }
  return result;
}

export function init(document) {
  const buttons = document.querySelectorAll("button[data-filter]");
  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      const items = document.querySelectorAll("li.node");
      const nodes = [];
      items.forEach(function (item) {
        nodes.push({ id: item.dataset.nodeId, status: item.dataset.status });
      });
      const hidden = hiddenByStatus(nodes, button.dataset.filter);
      items.forEach(function (item) {
        item.hidden = hidden[item.dataset.nodeId];
      });
    });
  });
}
