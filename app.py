from flask import Flask, request, render_template
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
import faiss
import numpy as np
import json

app = Flask(__name__)

# === Load Data ===
with open("data.json", "r", encoding="utf-8") as f:
    documents = json.load(f)

texts = [doc["text"] for doc in documents]
types = [doc["type"] for doc in documents]
ids = [doc["id"] for doc in documents]

# === Embedding Model ===
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(texts, convert_to_numpy=True)

# === FAISS Index ===
index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(embeddings)

# === Neo4j Driver ===
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "test2345"))

# === Query Neo4j to get procedure ===
def get_procedure_path(start_id):
    query = """
    MATCH path = (n:Step {nodeId: $start})-[:NEXT*]->(m)
    RETURN nodes(path) AS steps
    """
    with driver.session() as session:
        result = session.run(query, start=start_id)
        steps = result.single()
        if steps:
            return [node["title"] for node in steps["steps"]]
        return []

# === Flask Route ===
@app.route("/", methods=["GET", "POST"])
def main():
    result = {"article": "", "script": "", "procedure": []}
    if request.method == "POST":
        query = request.form["query"]
        query_embedding = model.encode([query], convert_to_numpy=True)
        D, I = index.search(query_embedding, k=5)

        node_id = None
        for idx in I[0]:
            if types[idx] == "article" and not result["article"]:
                result["article"] = texts[idx]
            elif types[idx] == "script" and not result["script"]:
                result["script"] = texts[idx]
            elif types[idx] == "procedure" and not result["procedure"]:
                node_id = ids[idx]

        if node_id:
            procedure_steps = get_procedure_path(node_id)
            result["procedure"] = procedure_steps

    return render_template("index.html", result=result)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
