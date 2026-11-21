const SVG_NS = "http://www.w3.org/2000/svg";

function columnOf(type) {
  if (type === "capability") return 0;
  if (type === "component") return 1;
  if (type === "var") return 2;
  return 3;
}

function edgeColor(kind) {
  if (kind === "depends_on") return "#1565c0";
  if (kind === "realizes") return "#2e7d32";
  return "#ef6c00";
}

export function layoutGraph(nodes, edges) {
  const counts = [0, 0, 0, 0];
  const positions = new Map();
  const laidNodes = nodes.map(function (node) {
    const column = columnOf(node.type);
    const row = counts[column];
    counts[column] = row + 1;
    const x = 120 + 260 * column;
    const y = 30 + 40 * row;
    positions.set(node.id, { x: x, y: y });
    return { id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 };
  });
  const laidEdges = [];
  edges.forEach(function (edge, index) {
    const a = positions.get(edge.from);
    const b = positions.get(edge.to);
    if (a !== undefined && b !== undefined) {
      laidEdges.push({
        index: index,
        from: edge.from,
        to: edge.to,
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
        color: edgeColor(edge.kind),
      });
    }
  });
  const m = Math.max(1, ...counts);
  return { width: 1100, height: 60 + 40 * m, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = Object.create(null);
  nodes.forEach(function (node) {
    hiddenNodes[node.id] = !node.id.toLowerCase().includes(needle);
  });
  const hiddenEdges = edges.map(function (edge) {
    return !(hiddenNodes[edge.from] === false && hiddenNodes[edge.to] === false);
  });
  return { hiddenNodes: hiddenNodes, hiddenEdges: hiddenEdges };
}

export function init(document) {
  const nodeItems = Array.from(document.querySelectorAll("#nodes .node"));
  const edgeItems = Array.from(document.querySelectorAll("#edges .edge"));
  const nodes = nodeItems.map(function (li) {
    return { id: li.dataset.id, type: li.dataset.type };
  });
  const edges = edgeItems.map(function (li) {
    return { from: li.dataset.from, to: li.dataset.to, kind: li.dataset.kind };
  });
  const layout = layoutGraph(nodes, edges);
  const svg = document.getElementById("dag");
  svg.setAttribute("width", layout.width);
  svg.setAttribute("height", layout.height);
  const lines = layout.edges.map(function (edge) {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", edge.x1);
    line.setAttribute("y1", edge.y1);
    line.setAttribute("x2", edge.x2);
    line.setAttribute("y2", edge.y2);
    line.setAttribute("stroke", edge.color);
    svg.appendChild(line);
    return line;
  });
  const marks = layout.nodes.map(function (node, i) {
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", nodeItems[i].querySelector("a").getAttribute("href"));
    const g = document.createElementNS(SVG_NS, "g");
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", 8);
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", node.labelX);
    text.setAttribute("y", node.labelY);
    text.textContent = node.id;
    g.appendChild(circle);
    g.appendChild(text);
    link.appendChild(g);
    svg.appendChild(link);
    return g;
  });
  const search = document.getElementById("search");
  search.addEventListener("input", function () {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach(function (li, i) {
      li.classList.toggle("hidden", result.hiddenNodes[nodes[i].id]);
    });
    marks.forEach(function (g, i) {
      g.classList.toggle("hidden", result.hiddenNodes[layout.nodes[i].id]);
    });
    edgeItems.forEach(function (li, i) {
      li.classList.toggle("hidden", result.hiddenEdges[i]);
    });
    lines.forEach(function (line, i) {
      line.classList.toggle("hidden", result.hiddenEdges[layout.edges[i].index]);
    });
  });
}
