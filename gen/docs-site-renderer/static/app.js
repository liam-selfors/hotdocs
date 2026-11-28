// DAG view: pure layout and filtering, plus browser wiring in init.

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
    const start = positions.get(edge.from);
    const end = positions.get(edge.to);
    if (start === undefined || end === undefined) {
      return;
    }
    let edgeClass = "edge-other";
    if (edge.kind === "depends_on") {
      edgeClass = "edge-depends-on";
    } else if (edge.kind === "realizes") {
      edgeClass = "edge-realizes";
    }
    laidEdges.push({
      index: index,
      from: edge.from,
      to: edge.to,
      x1: start.x,
      y1: start.y,
      x2: end.x,
      y2: end.y,
      class: edgeClass,
    });
  });
  const tallest = Math.max(1, ...counts);
  return { width: 1100, height: 60 + 40 * tallest, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = Object.create(null);
  for (const node of nodes) {
    hiddenNodes[node.id] = !node.id.toLowerCase().includes(needle);
  }
  const shown = (id) => hiddenNodes[id] === false;
  const hiddenEdges = edges.map((edge) => !(shown(edge.from) && shown(edge.to)));
  return { hiddenNodes: hiddenNodes, hiddenEdges: hiddenEdges };
}

export function init(document) {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const DISPLAY = ["inline", "none"];
  const nodeItems = Array.from(document.querySelectorAll("#nodes .node"));
  const edgeItems = Array.from(document.querySelectorAll("#edges .edge"));
  const nodes = nodeItems.map((item) => ({
    id: item.getAttribute("data-id"),
    type: item.getAttribute("data-type"),
  }));
  const edges = edgeItems.map((item) => ({
    from: item.getAttribute("data-from"),
    to: item.getAttribute("data-to"),
    kind: item.getAttribute("data-kind"),
  }));
  const layout = layoutGraph(nodes, edges);
  const svg = document.querySelector("svg#dag");
  svg.setAttribute("width", String(layout.width));
  svg.setAttribute("height", String(layout.height));
  const lines = layout.edges.map((laid) => {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", String(laid.x1));
    line.setAttribute("y1", String(laid.y1));
    line.setAttribute("x2", String(laid.x2));
    line.setAttribute("y2", String(laid.y2));
    line.setAttribute("class", laid.class);
    svg.appendChild(line);
    return line;
  });
  const marks = layout.nodes.map((laid, position) => {
    const link = document.createElementNS(SVG_NS, "a");
    link.setAttribute("href", nodeItems[position].querySelector("a").getAttribute("href"));
    const group = document.createElementNS(SVG_NS, "g");
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", String(laid.x));
    circle.setAttribute("cy", String(laid.y));
    circle.setAttribute("r", "8");
    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("x", String(laid.labelX));
    label.setAttribute("y", String(laid.labelY));
    label.textContent = laid.id;
    group.appendChild(circle);
    group.appendChild(label);
    link.appendChild(group);
    svg.appendChild(link);
    return group;
  });
  const showItem = (element, hidden) => {
    element.classList.toggle("hidden", hidden);
    element.toggleAttribute("hidden", hidden);
  };
  const showMark = (element, hidden) => {
    element.classList.toggle("hidden", hidden);
    element.setAttribute("display", DISPLAY[Number(hidden)]);
  };
  const search = document.querySelector("#search");
  const applyFilter = () => {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach((item, position) => showItem(item, result.hiddenNodes[nodes[position].id]));
    marks.forEach((mark, position) => showMark(mark, result.hiddenNodes[layout.nodes[position].id]));
    edgeItems.forEach((item, position) => showItem(item, result.hiddenEdges[position]));
    lines.forEach((line, position) => showMark(line, result.hiddenEdges[layout.edges[position].index]));
  };
  search.addEventListener("input", applyFilter);
  applyFilter();
}
