// DAG view for the docs site: pure layout and filtering, plus browser wiring.

const SVG_NS = "http://www.w3.org/2000/svg";

const COLUMNS = new Map([
  ["capability", 0],
  ["component", 1],
  ["var", 2],
]);

const COLORS = new Map([
  ["depends_on", "#1565c0"],
  ["realizes", "#2e7d32"],
]);

export function layoutGraph(nodes, edges) {
  const counts = [0, 0, 0, 0];
  const positions = new Map();
  const laidNodes = nodes.map((node) => {
    const column = COLUMNS.has(node.type) ? COLUMNS.get(node.type) : 3;
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
      const start = positions.get(edge.from);
      const end = positions.get(edge.to);
      laidEdges.push({
        index: index,
        from: edge.from,
        to: edge.to,
        x1: start.x,
        y1: start.y,
        x2: end.x,
        y2: end.y,
        color: COLORS.has(edge.kind) ? COLORS.get(edge.kind) : "#ef6c00",
      });
    }
  });
  const tallest = Math.max(1, ...counts);
  return { width: 1100, height: 60 + 40 * tallest, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hidden = new Map(nodes.map((node) => [node.id, !node.id.toLowerCase().includes(needle)]));
  const hiddenEdges = edges.map(
    (edge) => hidden.get(edge.from) !== false || hidden.get(edge.to) !== false
  );
  return { hiddenNodes: Object.fromEntries(hidden), hiddenEdges: hiddenEdges };
}

export function init(document) {
  const svg = document.querySelector("svg#dag");
  const search = document.querySelector("#search");
  const nodeItems = Array.from(document.querySelectorAll("#nodes .node"));
  const edgeItems = Array.from(document.querySelectorAll("#edges .edge"));
  const nodes = nodeItems.map((item) => ({ id: item.dataset.id, type: item.dataset.type }));
  const edges = edgeItems.map((item) => ({
    from: item.dataset.from,
    to: item.dataset.to,
    kind: item.dataset.kind,
  }));
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

  const marks = layout.nodes.map((node, position) => {
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", nodeItems[position].querySelector("a").getAttribute("href"));
    const group = document.createElementNS(SVG_NS, "g");
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", 8);
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", node.labelX);
    text.setAttribute("y", node.labelY);
    text.setAttribute("fill", "currentColor");
    text.textContent = node.id;
    group.appendChild(circle);
    group.appendChild(text);
    link.appendChild(group);
    svg.appendChild(link);
    return group;
  });

  const setHidden = (element, hidden) => {
    element.classList.toggle("hidden", hidden);
    element.toggleAttribute("hidden", hidden);
  };

  search.addEventListener("input", () => {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach((item, position) => setHidden(item, result.hiddenNodes[nodes[position].id]));
    marks.forEach((mark, position) => setHidden(mark, result.hiddenNodes[nodes[position].id]));
    edgeItems.forEach((item, position) => setHidden(item, result.hiddenEdges[position]));
    layout.edges.forEach((edge, position) => setHidden(lines[position], result.hiddenEdges[edge.index]));
  });
}
