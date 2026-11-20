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
        nodes.push({ id: item.getAttribute("data-node-id"), status: item.getAttribute("data-status") });
      });
      const hidden = hiddenByStatus(nodes, button.getAttribute("data-filter"));
      items.forEach(function (item) {
        item.hidden = hidden[item.getAttribute("data-node-id")];
      });
    });
  });
}
