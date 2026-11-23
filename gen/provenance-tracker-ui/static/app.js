// Filters provenance-tracker nodes by status. Every decision is in hiddenByStatus.

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
        return { id: item.getAttribute("data-node-id"), status: item.getAttribute("data-status") };
      });
      const hidden = hiddenByStatus(nodes, button.getAttribute("data-filter"));
      for (const item of items) {
        item.hidden = hidden[item.getAttribute("data-node-id")];
      }
    });
  }
}
