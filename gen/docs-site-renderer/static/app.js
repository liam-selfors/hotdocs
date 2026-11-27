const SVG_NS = "http://www.w3.org/2000/svg";

function columnOf(type) {
  if (type === "capability") {
    return 0;
  }
  if (type === "component") {
    return 1;
  }
  if (type === "var") {
    return 2;
  }
  return 3;
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
  const laidNodes = [];
  for (const node of nodes) {
    const column = columnOf(node.type);
    const row = counts[column];
    counts[column] = row + 1;
    const x = 120 + 260 * column;
    const y = 30 + 40 * row;
    laidNodes.push({ id: node.id, x: x, y: y, labelX: x + 12, labelY: y + 4 });
    positions.set(node.id, { x: x, y: y });
  }
  const laidEdges = [];
  edges.forEach((edge, index) => {
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
        color: colorOf(edge.kind),
      });
    }
  });
  let tallest = 0;
  for (const count of counts) {
    if (count > tallest) {
      tallest = count;
    }
  }
  if (tallest === 0) {
    tallest = 1;
  }
  return { width: 1100, height: 60 + 40 * tallest, nodes: laidNodes, edges: laidEdges };
}

export function filterGraph(nodes, edges, query) {
  const needle = query.toLowerCase();
  const hiddenNodes = {};
  const shown = new Map();
  for (const node of nodes) {
    const hidden = !node.id.toLowerCase().includes(needle);
    hiddenNodes[node.id] = hidden;
    shown.set(node.id, !hidden);
  }
  const hiddenEdges = edges.map(
    (edge) => shown.get(edge.from) !== true || shown.get(edge.to) !== true
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
  const hrefs = new Map();
  const itemsById = new Map();
  nodeItems.forEach((li) => {
    hrefs.set(li.dataset.id, li.querySelector("a").getAttribute("href"));
    itemsById.set(li.dataset.id, li);
  });

  const layout = layoutGraph(nodes, edges);
  const svg = document.querySelector("svg#dag");
  svg.setAttribute("width", String(layout.width));
  svg.setAttribute("height", String(layout.height));

  const lines = [];
  for (const e of layout.edges) {
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", String(e.x1));
    line.setAttribute("y1", String(e.y1));
    line.setAttribute("x2", String(e.x2));
    line.setAttribute("y2", String(e.y2));
    line.setAttribute("stroke", e.color);
    svg.appendChild(line);
    lines.push({ el: line, index: e.index });
  }

  const marks = [];
  for (const n of layout.nodes) {
    const g = document.createElementNS(SVG_NS, "g");
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", String(n.x));
    circle.setAttribute("cy", String(n.y));
    circle.setAttribute("r", "8");
    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", String(n.labelX));
    text.setAttribute("y", String(n.labelY));
    text.textContent = n.id;
    g.appendChild(circle);
    g.appendChild(text);
    g.setAttribute("data-id", n.id);
    g.style.cursor = "pointer";
    const href = hrefs.get(n.id);
    g.addEventListener("click", () => {
      document.location.href = href;
    });
    svg.appendChild(g);
    marks.push({ el: g, id: n.id });
  }

  const search = document.querySelector("#search");
  search.addEventListener("input", () => {
    const result = filterGraph(nodes, edges, search.value);
    nodeItems.forEach((li) => {
      li.classList.toggle("hidden", result.hiddenNodes[li.dataset.id]);
    });
    edgeItems.forEach((li, i) => {
      li.classList.toggle("hidden", result.hiddenEdges[i]);
    });
    marks.forEach((mark) => {
      mark.el.classList.toggle("hidden", result.hiddenNodes[mark.id]);
    });
    lines.forEach((line) => {
      line.el.classList.toggle("hidden", result.hiddenEdges[line.index]);
    });
  });
}
