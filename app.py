
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "service": "구미호 연애운 사주",
        "status": "running"
    })

@app.route("/api/preview", methods=["POST"])
def preview():
    data = request.get_json(silent=True) or {}

    birth = data.get("birth")
    if not birth:
        return jsonify({
            "error": "생년월일을 입력해주세요."
        }), 400

    try:
        datetime.strptime(birth, "%Y-%m-%d")
    except ValueError:
        return jsonify({
            "error": "YYYY-MM-DD 형식으로 입력해주세요."
        }), 400

    return jsonify({
        "title": "구미호 연애운 미리보기",
        "birth": birth,
        "message": "당신의 연애운 분석을 준비하고 있어요.",
        "premium_available": False
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
