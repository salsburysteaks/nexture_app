'''

This file will be leveraged to uitilize the financial calculation helper functions
It will be able to structure all results into json that can be passed to frontend
It will also be able to get results from our ollama server aiding with other guidance that ollama provides

'''

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/analyze", methods=["POST"])
def analyze():
    print("HIT PYTHON")
    print(request.json)
    data = request.get_json()
    primaryGoal = data.get("primaryGoal")
    salesChannel = data.get("salesChannel")
    print(primaryGoal)
    print(salesChannel)
    # Example computation
    #result = data["unitCost"] * data["demand"]

    return jsonify(data)

if __name__ == "__main__":
    app.run(port=5002)