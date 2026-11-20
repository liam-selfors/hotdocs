// DAG view for the docs site: pure layout and filtering, plus browser wiring.

const SVG_NS = "http://www.w3.org/2000/svg";

export function layoutGraph(nodes, edges) {
  const counts = [0, 0, 0, 0];
  const positions = new Map();
  const laidNodes = [];
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
    positions.set(node.id, { x: x, y: y });
    laidNodes.push({ id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 });
  }
  const laidEdges = [];
  edges.forEach((edge, index) => {
    const a = positions.get(edge.from);
    const b = positions.get(edge.to);
    if (a === undefined || b === undefined) {
      return;
    }
    let color = "#ef6c00";
    if (edge.kind === "depends_on") {
      color = "#1565c0";
    } else if (edge.kind === "realizes") {
      color = "#2e7d32";
    }
    laidEdges.push({
      index: index,
      from: edge.from,
      to: edge.to,
      x1: a.x,
      y1: a.y,
      x2: b.x,
      y2: b.y,
      color: color,
    });
  });
  const m = Math.max(1, ...counts);
  return { width: 1100, height: 60 + 40 * m, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = Object.create(null);
  for (const node of nodes) {
    hiddenNodes[node.id] = !node.id.toLowerCase().includes(needle);
  }
  const hiddenEdges = edges.map(
    (edge) => !(hiddenNodes[edge.from] === false && hiddenNodes[edge.to] === false)
  );
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
    return { index: edge.index, line: line };
  });

  const marks = layout.nodes.map((node, i) => {
    const href = nodeItems[i].querySelector("a").getAttribute("href");
    const g = document.createElementNS(SVG_NS, "g");
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", href);
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

  const search = document.querySelector("#search");
  search.addEventListener("input", () => {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach((li, i) => {
      li.classList.toggle("hidden", result.hiddenNodes[nodes[i].id]);
      marks[i].classList.toggle("hidden", result.hiddenNodes[nodes[i].id]);
    });
    edgeItems.forEach((li, i) => {
      li.classList.toggle("hidden", result.hiddenEdges[i]);
    });
    lines.forEach((pair) => {
      pair.line.classList.toggle("hidden", result.hiddenEdges[pair.index]);
    });
  });
}
