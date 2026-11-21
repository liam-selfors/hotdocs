export function hiddenByStatus(nodes, filter) {
  const result = {};
  nodes.forEach((node) => {
    result[node.id] = filter !== "all" && node.status !== filter;
  });
  return result;
}

export function init(document) {
  document.querySelectorAll("button[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      const items = document.querySelectorAll("li.node");
      const nodes = [];
      items.forEach((item) => {
        nodes.push({
          id: item.getAttribute("data-node-id"),
          status: item.getAttribute("data-status"),
        });
      });
      const hidden = hiddenByStatus(nodes, button.getAttribute("data-filter"));
      items.forEach((item) => {
        item.hidden = hidden[item.getAttribute("data-node-id")];
      });
    });
  });
}
