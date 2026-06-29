"""Concept dependency graph via reflect() + networkx/pyvis."""

from __future__ import annotations

import json
import os
import tempfile

import networkx as nx
from pyvis.network import Network

from config import get_subject
from scheduler.scheduler import list_concepts

GRAPH_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["id", "label"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "relationship": {"type": "string"},
                },
                "required": ["from", "to"],
            },
        },
    },
    "required": ["nodes", "edges"],
}


def fetch_prerequisite_graph(user_id: str, subject: str | None = None) -> dict:
    """Ask reflect() for suggested prerequisite edges between concepts."""
    concepts = list_concepts(user_id, subject)
    if not concepts:
        return {"nodes": [], "edges": []}

    names = [f"{c['name']} ({c['category']})" for c in concepts[:40]]
    query = (
        "Given these learnable concepts from my study notes, infer prerequisite "
        "relationships as directed edges (from prerequisite → dependent). "
        "Only include edges you are reasonably confident about from my notes. "
        "Return JSON matching the schema with nodes and edges. "
        f"Concepts: {json.dumps(names)}"
    )
    from core.scope import bank_id
    from config import get_hindsight_client

    client = get_hindsight_client()
    try:
        response = client.reflect(
            bank_id=bank_id(user_id, subject),
            query=query,
            budget="high",
            response_schema=GRAPH_SCHEMA,
        )
        return json.loads(response.text)
    except Exception:
        # Fallback: flat nodes, no edges
        return {
            "nodes": [{"id": c["name"], "label": c["name"], "category": c["category"]} for c in concepts],
            "edges": [],
        }


def render_graph_html(graph: dict, height: str = "500px") -> str:
    """Render pyvis HTML for Streamlit components.html."""
    net = Network(height=height, width="100%", directed=True, bgcolor="#ffffff", font_color="#333333")
    net.barnes_hut()

    for node in graph.get("nodes", []):
        nid = node.get("id") or node.get("label")
        net.add_node(
            nid,
            label=node.get("label", nid),
            title=node.get("category", ""),
            color="#6C9BD1",
        )

    for edge in graph.get("edges", []):
        src = edge.get("from") or edge.get("source")
        dst = edge.get("to") or edge.get("target")
        label = edge.get("relationship", "prerequisite")
        if src and dst:
            net.add_edge(src, dst, title=label, arrows="to")

    path = os.path.join(tempfile.gettempdir(), f"atlas_graph_{get_subject(subject)}.html")
    net.save_graph(path)
    with open(path, encoding="utf-8") as f:
        return f.read()


def graph_stats(graph: dict) -> dict:
    g = nx.DiGraph()
    for e in graph.get("edges", []):
        src = e.get("from") or e.get("source")
        dst = e.get("to") or e.get("target")
        if src and dst:
            g.add_edge(src, dst)
    return {
        "node_count": len(graph.get("nodes", [])),
        "edge_count": g.number_of_edges(),
        "is_dag": nx.is_directed_acyclic_graph(g) if g.number_of_edges() else True,
    }
