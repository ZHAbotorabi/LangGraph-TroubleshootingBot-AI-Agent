from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
import faiss
import json
from typing import TypedDict

# === Define LangGraph state schema ===
class GraphState(TypedDict):
    query: str
    node_id: str
    article: str
    script: str
    procedure: list

# === Load data and FAISS index ===
with open("data.json", "r", encoding="utf-8") as f:
    documents = json.load(f)

texts = [doc["text"] for doc in documents]
types = [doc["type"] for doc in documents]
ids = [doc["id"] for doc in documents]

model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(texts, convert_to_numpy=True)

index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(embeddings)

# === Connect to Neo4j ===
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "test2345"))

# === Cypher query to fetch path from Neo4j ===
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

# === Node 1: Semantic Search ===
def semantic_match(state):
    query = state["query"]
    query_embedding = model.encode([query], convert_to_numpy=True)
    D, I = index.search(query_embedding, k=5)
    result = {"query": query, "node_id": "", "article": "", "script": "", "procedure": []}
    for idx in I[0]:
        if types[idx] == "procedure" and not result["node_id"]:
            result["node_id"] = ids[idx]
        elif types[idx] == "article" and not result["article"]:
            result["article"] = texts[idx]
        elif types[idx] == "script" and not result["script"]:
            result["script"] = texts[idx]
    return result

# === Node 2: Fetch Procedure Path ===
def fetch_procedure(state):
    node_id = state.get("node_id")
    if node_id:
        state["procedure"] = get_procedure_path(node_id)
    return state

# === Node 3: Build Final Answer ===
def build_answer(state):
    return {
        "procedure": state.get("procedure"),
        "article": state.get("article"),
        "script": state.get("script")
    }

# === Build LangGraph ===
graph = StateGraph(GraphState)
graph.add_node("SemanticMatch", RunnableLambda(semantic_match))
graph.add_node("GetProcedure", RunnableLambda(fetch_procedure))
graph.add_node("BuildAnswer", RunnableLambda(build_answer))

graph.set_entry_point("SemanticMatch")
graph.add_edge("SemanticMatch", "GetProcedure")
graph.add_edge("GetProcedure", "BuildAnswer")
graph.set_finish_point("BuildAnswer")

#===
app = graph.compile()

# === Run Locally ===
if __name__ == "__main__":
    question = input("Ask a question: ")
    result = app.invoke({
        "query": question,
        "node_id": "",
        "article": "",
        "script": "",
        "procedure": []
    })
    print("\nAnswer:")
    print("Procedure:", result["procedure"])
    print("Article:", result["article"])
    print("Script:", result["script"])