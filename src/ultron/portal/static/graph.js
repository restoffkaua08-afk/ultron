/* ULTRON — grafo de dependências via Cytoscape. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    const container = document.getElementById("graph-container");
    if (!container || typeof cytoscape === "undefined") return;
    const raw = container.dataset.graphData;
    let data;
    try { data = JSON.parse(raw); } catch (e) { return; }

    const KIND_COLORS = {
      agent: "#9cc1ff",
      skill: "#8fdfb5",
      workflow: "#ffbf80",
      pack: "#c8a4ff",
      "?": "#8b8d90",
    };

    cytoscape({
      container: container,
      elements: [
        ...data.nodes.map(function (n) {
          return {
            data: {
              id: n.id, label: n.label, kind: n.kind, publisher: n.publisher,
            },
          };
        }),
        ...data.edges.map(function (e, i) {
          return { data: { id: "e" + i, source: e.source, target: e.target, label: e.label } };
        }),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": function (n) { return KIND_COLORS[n.data("kind")] || "#8b8d90"; },
            "label": "data(label)",
            "color": "#dcddde",
            "font-size": "11px",
            "font-family": "Inter, system-ui, sans-serif",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "border-width": 2,
            "border-color": "#3a3a3a",
            "width": "mapData(label.length, 4, 30, 30, 70)",
            "height": "mapData(label.length, 4, 30, 30, 70)",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#7f6df2",
            "border-width": 4,
          },
        },
        {
          selector: "edge",
          style: {
            "width": 1.5,
            "line-color": "#4a4a4a",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#4a4a4a",
            "arrow-scale": 0.8,
          },
        },
        {
          selector: "edge:selected",
          style: { "line-color": "#7f6df2", "target-arrow-color": "#7f6df2" },
        },
      ],
      layout: {
        name: "cose",
        animate: true,
        nodeRepulsion: 8000,
        idealEdgeLength: 100,
        gravity: 0.5,
        padding: 20,
      },
    });
  });
})();
