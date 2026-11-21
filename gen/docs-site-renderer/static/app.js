const COLUMNS = new Map([
  ["capability", 0],
  ["component", 1],
  ["var", 2],
]);

const SVG_NS = "http://www.w3.org/2000/svg";

function columnOf(type) {
  return COLUMNS.has(type) ? COLUMNS.get(type) : 3;
}

function colorOf(kind) {
  if (kind === "depends_on") {
    return "#1565c0";
  }
  if (kind === "realizes") {
    return "#2e7d32";
  }
  return "#ef6c00";
}

export function layoutGraph(nodes, edges) {
  const counts = [0, 0, 0, 0];
  const byId = new Map();
  const laid = [];
  for (const node of nodes) {
    const column = columnOf(node.type);
    const row = counts[column];
    counts[column] = row + 1;
    const x = 120 + 260 * column;
    const y = 30 + 40 * row;
    const placed = { id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 };
    byId.set(node.id, placed);
    laid.push(placed);
  }
  const drawn = [];
  edges.forEach(function (edge, index) {
    if (byId.has(edge.from) && byId.has(edge.to)) {
      const start = byId.get(edge.from);
      const end = byId.get(edge.to);
      drawn.push({
        index: index,
        from: edge.from,
        to: edge.to,
        x1: start.x,
        y1: start.y,
        x2: end.x,
        y2: end.y,
        color: colorOf(edge.kind),
      });
    }
  });
  const tallest = Math.max(1, ...counts);
  return { width: 1100, height: 60 + 40 * tallest, nodes: laid, edges: drawn };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = Object.create(null);
  for (const node of nodes) {
    hiddenNodes[node.id] = !node.id.toLowerCase().includes(needle);
  }
  function shown(id) {
    return Object.hasOwn(hiddenNodes, id) && !hiddenNodes[id];
  }
  const hiddenEdges = edges.map(function (edge) {
    return !(shown(edge.from) && shown(edge.to));
  });
  return { hiddenNodes: hiddenNodes, hiddenEdges: hiddenEdges };
}

export function init(document) {
  const nodeItems = Array.from(document.querySelectorAll("#nodes .node"));
  const edgeItems = Array.from(document.querySelectorAll("#edges .edge"));
  const nodes = nodeItems.map((li) => ({ id: li.dataset.id, type: li.dataset.type }));
  const edges = edgeItems.map((li) => ({
    from: li.dataset.from,
    to: li.dataset.to,
    kind: li.dataset.kind,
  }));
  const layout = layoutGraph(nodes, edges);
  const svg = document.querySelector("svg#dag");
  svg.setAttribute("width", String(layout.width));
  svg.setAttribute("height", String(layout.height));
  const lines = layout.edges.map((placed) => {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", String(placed.x1));
    line.setAttribute("y1", String(placed.y1));
    line.setAttribute("x2", String(placed.x2));
    line.setAttribute("y2", String(placed.y2));
    line.setAttribute("stroke", placed.color);
    svg.appendChild(line);
    return line;
  });
  const marks = layout.nodes.map((placed, index) => {
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", nodeItems[index].querySelector("a").getAttribute("href"));
    const group = document.createElementNS(SVG_NS, "g");
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", String(placed.x));
    circle.setAttribute("cy", String(placed.y));
    circle.setAttribute("r", "8");
    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("x", String(placed.labelX));
    label.setAttribute("y", String(placed.labelY));
    label.textContent = placed.id;
    group.appendChild(circle);
    group.appendChild(label);
    link.appendChild(group);
    svg.appendChild(link);
    return group;
  });
  const search = document.querySelector("#search");
  search.addEventListener("input", () => {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach((li, index) => {
      li.classList.toggle("hidden", result.hiddenNodes[nodes[index].id]);
    });
    edgeItems.forEach((li, index) => {
      li.classList.toggle("hidden", result.hiddenEdges[index]);
    });
    marks.forEach((mark, index) => {
      mark.classList.toggle("hidden", result.hiddenNodes[layout.nodes[index].id]);
    });
    lines.forEach((line, index) => {
      line.classList.toggle("hidden", result.hiddenEdges[layout.edges[index].index]);
    });
  });
}
