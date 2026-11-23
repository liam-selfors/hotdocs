// DAG view for the docs site: pure layout and filter functions plus init.

export function layoutGraph(nodes, edges) {
  const counts = [0, 0, 0, 0];
  const positions = new Map();
  const outNodes = [];
  for (const node of nodes) {
    let column = 3;
    if (node.type === "capability") {
      column = 0;
    } else if (node.type === "component") {
      column = 1;
    } else if (node.type === "var") {
      column = 2;
    }
    const row = counts[column];
    counts[column] = row + 1;
    const x = 120 + 260 * column;
    const y = 30 + 40 * row;
    outNodes.push({ id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 });
    positions.set(node.id, { x: x, y: y });
  }
  const outEdges = [];
  edges.forEach(function (edge, index) {
    if (positions.has(edge.from) && positions.has(edge.to)) {
      const start = positions.get(edge.from);
      const end = positions.get(edge.to);
      let color = "#ef6c00";
      if (edge.kind === "depends_on") {
        color = "#1565c0";
      } else if (edge.kind === "realizes") {
        color = "#2e7d32";
      }
      outEdges.push({
        index: index,
        from: edge.from,
        to: edge.to,
        x1: start.x,
        y1: start.y,
        x2: end.x,
        y2: end.y,
        color: color,
      });
    }
  });
  const tallest = Math.max(1, counts[0], counts[1], counts[2], counts[3]);
  return { width: 1100, height: 60 + 40 * tallest, nodes: outNodes, edges: outEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = {};
  for (const node of nodes) {
    hiddenNodes[node.id] = !node.id.toLowerCase().includes(needle);
  }
  const hiddenEdges = edges.map(function (edge) {
    const visible = hiddenNodes[edge.from] === false && hiddenNodes[edge.to] === false;
    return !visible;
  });
  return { hiddenNodes: hiddenNodes, hiddenEdges: hiddenEdges };
}

export function init(document) {
  const ns = "http://www.w3.org/2000/svg";
  const nodeItems = Array.from(document.querySelectorAll("#nodes .node"));
  const edgeItems = Array.from(document.querySelectorAll("#edges .edge"));
  const nodes = nodeItems.map(function (li) {
    return { id: li.dataset.id, type: li.dataset.type };
  });
  const edges = edgeItems.map(function (li) {
    return { from: li.dataset.from, to: li.dataset.to, kind: li.dataset.kind };
  });
  const layout = layoutGraph(nodes, edges);
  const svg = document.querySelector("svg#dag");
  svg.setAttribute("width", String(layout.width));
  svg.setAttribute("height", String(layout.height));

  const lines = [];
  for (const edge of layout.edges) {
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", String(edge.x1));
    line.setAttribute("y1", String(edge.y1));
    line.setAttribute("x2", String(edge.x2));
    line.setAttribute("y2", String(edge.y2));
    line.setAttribute("stroke", edge.color);
    svg.appendChild(line);
    lines.push({ index: edge.index, el: line });
  }

  const marks = [];
  layout.nodes.forEach(function (node, i) {
    const link = document.createElementNS(ns, "a");
    link.setAttribute("href", nodeItems[i].querySelector("a").getAttribute("href"));
    const group = document.createElementNS(ns, "g");
    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("cx", String(node.x));
    circle.setAttribute("cy", String(node.y));
    circle.setAttribute("r", "8");
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", String(node.labelX));
    label.setAttribute("y", String(node.labelY));
    label.textContent = node.id;
    group.appendChild(circle);
    group.appendChild(label);
    link.appendChild(group);
    svg.appendChild(link);
    marks.push({ id: node.id, el: link });
  });

  const search = document.querySelector("#search");
  search.addEventListener("input", function () {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach(function (li, i) {
      li.classList.toggle("hidden", result.hiddenNodes[nodes[i].id]);
    });
    edgeItems.forEach(function (li, i) {
      li.classList.toggle("hidden", result.hiddenEdges[i]);
    });
    marks.forEach(function (mark) {
      mark.el.classList.toggle("hidden", result.hiddenNodes[mark.id]);
    });
    lines.forEach(function (line) {
      line.el.classList.toggle("hidden", result.hiddenEdges[line.index]);
    });
  });
}
