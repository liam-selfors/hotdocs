// DAG view for the docs site: pure layout and search, plus browser wiring.

const COLUMNS = { capability: 0, component: 1, var: 2 };
const OTHER_COLUMN = 3;
const COLORS = { depends_on: "#1565c0", realizes: "#2e7d32" };
const OTHER_COLOR = "#ef6c00";
const SVG_NS = "http://www.w3.org/2000/svg";

export function layoutGraph(nodes, edges) {
  const counts = [0, 0, 0, 0];
  const positions = new Map();
  const laidNodes = [];
  for (const node of nodes) {
    const column = Object.hasOwn(COLUMNS, node.type) ? COLUMNS[node.type] : OTHER_COLUMN;
    const row = counts[column];
    counts[column] = row + 1;
    const x = 120 + 260 * column;
    const y = 30 + 40 * row;
    positions.set(node.id, { x: x, y: y });
    laidNodes.push({ id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 });
  }
  const laidEdges = [];
  edges.forEach(function (edge, index) {
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
        color: Object.hasOwn(COLORS, edge.kind) ? COLORS[edge.kind] : OTHER_COLOR,
      });
    }
  });
  const tallest = Math.max(1, counts[0], counts[1], counts[2], counts[3]);
  return { width: 1100, height: 60 + 40 * tallest, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = Object.create(null);
  for (const node of nodes) {
    hiddenNodes[node.id] = !node.id.toLowerCase().includes(needle);
  }
  const shown = function (id) {
    return Object.hasOwn(hiddenNodes, id) && !hiddenNodes[id];
  };
  const hiddenEdges = edges.map(function (edge) {
    return !(shown(edge.from) && shown(edge.to));
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
  const svg = document.querySelector("svg#dag");
  svg.setAttribute("width", String(layout.width));
  svg.setAttribute("height", String(layout.height));
  const lines = layout.edges.map(function (laid) {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", String(laid.x1));
    line.setAttribute("y1", String(laid.y1));
    line.setAttribute("x2", String(laid.x2));
    line.setAttribute("y2", String(laid.y2));
    line.setAttribute("stroke", laid.color);
    svg.appendChild(line);
    return { index: laid.index, mark: line };
  });
  const marks = layout.nodes.map(function (laid, i) {
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", nodeItems[i].querySelector("a").getAttribute("href"));
    const group = document.createElementNS(SVG_NS, "g");
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", String(laid.x));
    circle.setAttribute("cy", String(laid.y));
    circle.setAttribute("r", "8");
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", String(laid.labelX));
    text.setAttribute("y", String(laid.labelY));
    text.textContent = laid.id;
    group.appendChild(circle);
    group.appendChild(text);
    link.appendChild(group);
    svg.appendChild(link);
    return group;
  });
  const search = document.querySelector("#search");
  search.addEventListener("input", function () {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach(function (li, i) {
      const hidden = result.hiddenNodes[nodes[i].id];
      li.classList.toggle("hidden", hidden);
      marks[i].classList.toggle("hidden", hidden);
    });
    edgeItems.forEach(function (li, i) {
      li.classList.toggle("hidden", result.hiddenEdges[i]);
    });
    lines.forEach(function (drawn) {
      drawn.mark.classList.toggle("hidden", result.hiddenEdges[drawn.index]);
    });
  });
}
