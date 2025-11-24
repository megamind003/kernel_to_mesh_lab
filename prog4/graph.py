import networkx as nx
import pickle
import os
from config import BASE_DIR

GRAPH_FILE = os.path.join(BASE_DIR, "knowledge_graph.gpickle")

class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_email_interaction(self, sender, receiver, timestamp, subject):
        """Adds an edge representing an email interaction."""
        if not sender or not receiver:
            return
        
        self.graph.add_node(sender, type="person")
        self.graph.add_node(receiver, type="person")
        
        # Add edge with metadata
        self.graph.add_edge(sender, receiver, timestamp=timestamp, subject=subject, relation="emailed")

    def save(self):
        """Saves the graph to disk."""
        with open(GRAPH_FILE, "wb") as f:
            pickle.dump(self.graph, f)
        print(f"Graph saved to {GRAPH_FILE} with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")

    def load(self):
        """Loads the graph from disk."""
        if os.path.exists(GRAPH_FILE):
            with open(GRAPH_FILE, "rb") as f:
                self.graph = pickle.load(f)
            print(f"Graph loaded from {GRAPH_FILE}")
        else:
            print("No existing graph found. Starting fresh.")

    def get_neighbors(self, node):
        """Returns neighbors of a node."""
        if node in self.graph:
            return list(self.graph.neighbors(node))
        return []
