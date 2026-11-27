export function hiddenByStatus(nodes, filter) {
  const result = {};
  for (const node of nodes) {
    result[node.id] = filter !== "all" && node.status !== filter;
  }
  return result;
}

export function init(document) {
  const buttons = document.querySelectorAll("button[data-filter]");
  for (const button of buttons) {
    button.addEventListener("click", function () {
      const items = Array.from(document.querySelectorAll("li.node"));
      const nodes = items.map(function (item) {
        return { id: item.dataset.nodeId, status: item.dataset.status };
      });
      const hidden = hiddenByStatus(nodes, button.dataset.filter);
      for (const item of items) {
        item.hidden = hidden[item.dataset.nodeId];
      }
    });
  }
}
