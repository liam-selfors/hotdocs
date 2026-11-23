const COLUMNS = new Map([["capability", 0], ["component", 1], ["var", 2]]);
const OTHER_COLUMN = 3;
const SVG_NS = "http://www.w3.org/2000/svg";

function columnOf(type) {
  return COLUMNS.has(type) ? COLUMNS.get(type) : OTHER_COLUMN;
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
  const positions = new Map();
  const laidNodes = nodes.map((node) => {
    const column = columnOf(node.type);
    const row = counts[column];
    counts[column] = row + 1;
    const x = 120 + 260 * column;
    const y = 30 + 40 * row;
    positions.set(node.id, { x: x, y: y });
    return { id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 };
  });
  const laidEdges = [];
  edges.forEach((edge, index) => {
    if (positions.has(edge.from) && positions.has(edge.to)) {
      const a = positions.get(edge.from);
      const b = positions.get(edge.to);
      laidEdges.push({
        index: index,
        from: edge.from,
        to: edge.to,
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
        color: colorOf(edge.kind),
      });
    }
  });
  const m = Math.max(1, ...counts);
  return { width: 1100, height: 60 + 40 * m, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hidden = new Map();
  nodes.forEach((node) => {
    hidden.set(node.id, !node.id.toLowerCase().includes(needle));
  });
  const shown = (id) => hidden.has(id) && !hidden.get(id);
  const hiddenEdges = edges.map((edge) => !(shown(edge.from) && shown(edge.to)));
  return { hiddenNodes: Object.fromEntries(hidden), hiddenEdges: hiddenEdges };
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
  const svg = document.querySelector("svg#dag");
  const layout = layoutGraph(nodes, edges);
  svg.setAttribute("width", layout.width);
  svg.setAttribute("height", layout.height);
  const lines = layout.edges.map((edge) => {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", edge.x1);
    line.setAttribute("y1", edge.y1);
    line.setAttribute("x2", edge.x2);
    line.setAttribute("y2", edge.y2);
    line.setAttribute("stroke", edge.color);
    svg.appendChild(line);
    return line;
  });
  const marks = layout.nodes.map((node, k) => {
    const g = document.createElementNS(SVG_NS, "g");
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", nodeItems[k].querySelector("a").getAttribute("href"));
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", 8);
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", node.labelX);
    text.setAttribute("y", node.labelY);
    text.textContent = node.id;
    link.appendChild(circle);
    link.appendChild(text);
    g.appendChild(link);
    svg.appendChild(g);
    return g;
  });
  document.querySelector("#search").addEventListener("input", (event) => {
    const result = filterGraph(nodes, edges, event.target.value);
    nodeItems.forEach((li, k) => li.classList.toggle("hidden", result.hiddenNodes[nodes[k].id]));
    marks.forEach((g, k) => g.classList.toggle("hidden", result.hiddenNodes[layout.nodes[k].id]));
    edgeItems.forEach((li, i) => li.classList.toggle("hidden", result.hiddenEdges[i]));
    lines.forEach((line, k) => line.classList.toggle("hidden", result.hiddenEdges[layout.edges[k].index]));
  });
}
