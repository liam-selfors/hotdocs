const COLUMNS = new Map([["capability", 0], ["component", 1], ["var", 2]]);
const COLORS = new Map([["depends_on", "#1565c0"], ["realizes", "#2e7d32"]]);
const SVG_NS = "http://www.w3.org/2000/svg";

function columnOf(type) {
  if (COLUMNS.has(type)) {
    return COLUMNS.get(type);
  }
  return 3;
}

function colorOf(kind) {
  if (COLORS.has(kind)) {
    return COLORS.get(kind);
  }
  return "#ef6c00";
}

export function layoutGraph(nodes, edges) {
  const counts = [0, 0, 0, 0];
  const byId = new Map();
  const laidNodes = nodes.map((node) => {
    const column = columnOf(node.type);
    const row = counts[column];
    counts[column] = row + 1;
    const x = 120 + 260 * column;
    const y = 30 + 40 * row;
    const placed = { id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 };
    byId.set(node.id, placed);
    return placed;
  });
  const laidEdges = [];
  edges.forEach((edge, index) => {
    if (byId.has(edge.from) && byId.has(edge.to)) {
      const from = byId.get(edge.from);
      const to = byId.get(edge.to);
      laidEdges.push({
        index: index,
        from: edge.from,
        to: edge.to,
        x1: from.x,
        y1: from.y,
        x2: to.x,
        y2: to.y,
        color: colorOf(edge.kind),
      });
    }
  });
  const tallest = Math.max(1, ...counts);
  return { width: 1100, height: 60 + 40 * tallest, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = {};
  const visible = new Set();
  nodes.forEach((node) => {
    const shown = node.id.toLowerCase().includes(needle);
    hiddenNodes[node.id] = !shown;
    if (shown) {
      visible.add(node.id);
    }
  });
  const hiddenEdges = edges.map((edge) => !(visible.has(edge.from) && visible.has(edge.to)));
  return { hiddenNodes: hiddenNodes, hiddenEdges: hiddenEdges };
}

export function init(document) {
  const nodeItems = Array.from(document.querySelectorAll("#nodes .node"));
  const edgeItems = Array.from(document.querySelectorAll("#edges .edge"));
  const nodes = nodeItems.map((li) => ({ id: li.dataset.id, type: li.dataset.type }));
  const edges = edgeItems.map((li) => ({ from: li.dataset.from, to: li.dataset.to, kind: li.dataset.kind }));
  const layout = layoutGraph(nodes, edges);
  const svg = document.querySelector("svg#dag");
  svg.setAttribute("width", String(layout.width));
  svg.setAttribute("height", String(layout.height));
  const lines = layout.edges.map((edge) => {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", String(edge.x1));
    line.setAttribute("y1", String(edge.y1));
    line.setAttribute("x2", String(edge.x2));
    line.setAttribute("y2", String(edge.y2));
    line.setAttribute("stroke", edge.color);
    svg.appendChild(line);
    return line;
  });
  const groups = layout.nodes.map((node, i) => {
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", nodeItems[i].querySelector("a").getAttribute("href"));
    const group = document.createElementNS(SVG_NS, "g");
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", String(node.x));
    circle.setAttribute("cy", String(node.y));
    circle.setAttribute("r", "8");
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", String(node.labelX));
    text.setAttribute("y", String(node.labelY));
    text.textContent = node.id;
    group.appendChild(circle);
    group.appendChild(text);
    link.appendChild(group);
    svg.appendChild(link);
    return group;
  });
  document.querySelector("#search").addEventListener("input", (event) => {
    const result = filterGraph(nodes, edges, event.target.value);
    nodeItems.forEach((li, i) => li.classList.toggle("hidden", result.hiddenNodes[nodes[i].id]));
    edgeItems.forEach((li, i) => li.classList.toggle("hidden", result.hiddenEdges[i]));
    groups.forEach((group, i) => group.classList.toggle("hidden", result.hiddenNodes[layout.nodes[i].id]));
    lines.forEach((line, i) => line.classList.toggle("hidden", result.hiddenEdges[layout.edges[i].index]));
  });
}
