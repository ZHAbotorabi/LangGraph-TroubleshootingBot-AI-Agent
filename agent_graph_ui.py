from flask import Flask, request, render_template
from agent_graph import app as langgraph_app

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def main():
    result = {"procedure": [], "article": "", "script": ""}
    if request.method == "POST":
        query = request.form["query"]
        response = langgraph_app.invoke({
            "query": query,
            "node_id": "",
            "article": "",
            "script": "",
            "procedure": []
        })
        result = response
    return render_template("index.html", result=result)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
