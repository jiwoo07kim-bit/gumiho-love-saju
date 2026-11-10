from flask import Flask, request, jsonify
from korean_lunar_calendar import KoreanLunarCalendar
from datetime import datetime

app = Flask(__name__)

STEMS = "갑을병정무기경신임계"
BRANCHES = "자축인묘진사오미신유술해"
ELEMENTS = ["목", "목", "화", "화", "토", "토", "금", "금", "수", "수"]
BRANCH_ELEMENTS = ["수", "토", "목", "목", "토", "화", "화", "토", "금", "금", "토", "수"]

@app.route("/")
def home():
    return jsonify({"service": "구미호 연애운 사주", "status": "running"})

@app.route("/api/preview", methods=["POST"])
def preview():
    data = request.get_json(silent=True) or {}
    birth = data.get("birth")
    if not isinstance(birth, str):
        return jsonify({"error": "생년월일을 입력해주세요."}), 400

    try:
        dt = datetime.strptime(birth, "%Y-%m-%d")
        calendar = KoreanLunarCalendar()
        if not calendar.setSolarDate(dt.year, dt.month, dt.day):
            return jsonify({"error": "지원하지 않는 날짜입니다."}), 400
        ganji = calendar.getChineseGapJaString().split()
        if len(ganji) < 3:
            raise ValueError("간지 계산 실패")
        pillars = ganji[:3]
        counts = {e: 0 for e in ["목", "화", "토", "금", "수"]}
        for pillar in pillars:
            stem_index = STEMS.index(pillar[0])
            branch_index = BRANCHES.index(pillar[1])
            counts[ELEMENTS[stem_index]] += 1
            counts[BRANCH_ELEMENTS[branch_index]] += 1
        dominant = max(counts, key=counts.get)
    except (ValueError, TypeError, IndexError):
        return jsonify({"error": "생년월일 또는 간지 계산을 확인해주세요."}), 400

    return jsonify({
        "title": "구미호 연애운 미리보기",
        "birth": birth,
        "pillars": pillars,
        "elements": counts,
        "dominant_element": dominant,
        "message": f"오행 중 {dominant} 기운이 두드러집니다. 연애 성향은 전체 사주와 절기를 함께 검토해야 합니다.",
        "calculation_note": "현재 간지는 라이브러리 기준의 예비 결과이며, 절기·시간대 검증 전입니다.",
        "premium_available": False
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
