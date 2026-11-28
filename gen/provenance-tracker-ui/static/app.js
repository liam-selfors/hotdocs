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
      const elements = Array.from(document.querySelectorAll("li.node"));
      const nodes = elements.map((element) => ({
        id: element.getAttribute("data-node-id"),
        status: element.getAttribute("data-status"),
      }));
      const hidden = hiddenByStatus(nodes, button.getAttribute("data-filter"));
      for (const element of elements) {
        element.hidden = hidden[element.getAttribute("data-node-id")];
      }
    });
  }
}
