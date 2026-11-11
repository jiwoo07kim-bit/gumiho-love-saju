import base64
import json
import hmac
import urllib.parse
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder='static', static_url_path='')
app.json.ensure_ascii = False
DB_PATH = os.environ.get('DB_PATH', str(ROOT / 'orders.sqlite3'))
PRICE = int(os.environ.get('PREMIUM_PRICE', '4990'))
PAYAPP_USERID = os.environ.get('PAYAPP_USERID', '')
PAYAPP_LINKKEY = os.environ.get('PAYAPP_LINKKEY', '')
PAYAPP_LINKVAL = os.environ.get('PAYAPP_LINKVAL', '')
PAYAPP_PUBLIC_URL = os.environ.get('PAYAPP_PUBLIC_URL', '').rstrip('/')
SITE_URL = os.environ.get('SITE_URL', PAYAPP_PUBLIC_URL).rstrip('/')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')
ALLOWED_ORIGINS = {x.strip().rstrip('/') for x in os.environ.get('ALLOWED_ORIGINS', '').split(',') if x.strip()}
PAYMENT_ENABLED = bool(PAYAPP_USERID and PAYAPP_LINKKEY and PAYAPP_LINKVAL and PAYAPP_PUBLIC_URL.startswith('https://') and SITE_URL.startswith('https://') and OPENAI_API_KEY)
TOPICS = {'love': '나의 연애운', 'reunion': '그 사람과의 재회운', 'compatibility': '두 사람의 궁합'}
ANIMALS = ['원숭이', '닭', '개', '돼지', '쥐', '소', '호랑이', '토끼', '용', '뱀', '말', '양']
STEMS = ['갑', '을', '병', '정', '무', '기', '경', '신', '임', '계']
BRANCHES = ['자', '축', '인', '묘', '진', '사', '오', '미', '신', '유', '술', '해']
ELEMENTS = ['목', '목', '화', '화', '토', '토', '금', '금', '수', '수']


def db():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, amount INTEGER NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, payment_key TEXT, result TEXT, created_at TEXT NOT NULL)')
    columns = {r[1] for r in con.execute('PRAGMA table_info(orders)').fetchall()}
    if 'mul_no' not in columns:
        con.execute('ALTER TABLE orders ADD COLUMN mul_no TEXT')
    if 'access_token' not in columns:
        con.execute('ALTER TABLE orders ADD COLUMN access_token TEXT')
    con.commit()
    return con


def error(message, status=400):
    return jsonify(error=message), status


def parse_payload(data):
    if not isinstance(data, dict):
        raise ValueError('입력 형식이 올바르지 않습니다.')
    topic = data.get('topic')
    if topic not in TOPICS:
        raise ValueError('분석 종류를 선택해 주세요.')
    try:
        birth = date.fromisoformat(str(data.get('birth', '')))
    except ValueError:
        raise ValueError('생년월일을 정확하게 입력해 주세요.')
    if birth > date.today() or birth.year < 1900:
        raise ValueError('생년월일 범위를 확인해 주세요.')
    hour = data.get('hour', '')
    if hour is None:
        hour = ''
    if str(hour) and (not re.fullmatch(r'\d{1,2}', str(hour)) or not 0 <= int(hour) <= 23):
        raise ValueError('출생 시간을 확인해 주세요.')
    other = None
    if topic == 'compatibility':
        try:
            other = date.fromisoformat(str(data.get('other_birth', '')))
        except ValueError:
            raise ValueError('상대방 생년월일을 입력해 주세요.')
        if other > date.today() or other.year < 1900:
            raise ValueError('상대방 생년월일 범위를 확인해 주세요.')
    return {'topic': topic, 'birth': birth.isoformat(), 'hour': str(hour), 'other_birth': other.isoformat() if other else ''}


def year_sign(yr):
    return STEMS[(yr - 4) % 10] + BRANCHES[(yr - 4) % 12]


def preview_for(data):
    yr = int(data['birth'][:4]); stem_index = (yr - 4) % 10
    animal = ANIMALS[yr % 12]
    element = ELEMENTS[stem_index]
    other = data['other_birth']
    extra = f" 상대방의 출생 연도는 {year_sign(int(other[:4]))}년으로 표시됩니다." if other else ''
    messages = {
        'love': '마음을 표현하는 속도와 상대방의 반응을 함께 살펴보세요. 원하는 관계의 모습을 구체적으로 적어 보면 선택에 도움이 됩니다.',
        'reunion': '재회의 가능성을 단정하기보다, 헤어진 이유와 현재 서로의 의사를 먼저 살펴보세요. 연락의 경계와 타이밍을 존중하는 것이 중요합니다.',
        'compatibility': '두 사람의 궁합을 운명으로 확정하기보다 대화 방식, 갈등 해결, 기대치를 비교해 보세요.'
    }
    return {
        'title': TOPICS[data['topic']],
        'saju': {'pillars': {'year': year_sign(yr), 'month': '미산출', 'day': '미산출', 'hour': ''}, 'day_master': '미산출', 'elements': {element: '연간 기준 참고'}},
        'preview': f"{yr}년생의 연간(年干)은 {STEMS[stem_index]}, 띠는 {animal}로 간략 표시됩니다.{extra}\n\n{messages[data['topic']]}",
        'notice': '이 결과는 양력 출생연도만 사용한 간이 상징 해석입니다. 입춘·절기·음력 변환을 적용한 정확한 사주팔자/일간/오행 분포가 아니며, 오락 및 자기성찰용입니다.'
    }


def external_json(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        app.logger.error('외부 서비스 오류 %s: %s', exc.code, exc.read(400).decode(errors='replace'))
        raise RuntimeError('외부 서비스 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.')
    except Exception as exc:
        app.logger.error('외부 서비스 연결 오류: %s', exc)
        raise RuntimeError('외부 서비스 연결에 실패했습니다.')


def payapp_request(fields):
    encoded = urllib.parse.urlencode(fields).encode('utf-8')
    req = urllib.request.Request(
        'https://api.payapp.kr/oapi/apiLoad.html',
        data=encoded,
        headers={'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            result = dict(urllib.parse.parse_qsl(response.read().decode('utf-8')))
    except (urllib.error.URLError, UnicodeError) as exc:
        app.logger.error('PayApp request error: %s', exc)
        raise RuntimeError('결제 서비스에 연결하지 못했습니다.')
    if result.get('state') != '1' or not result.get('mul_no') or not result.get('payurl', '').startswith('https://'):
        app.logger.error('PayApp rejected payment request: %s', result.get('errno', 'unknown'))
        raise RuntimeError('결제 요청에 실패했습니다. 관리자에게 문의해 주세요.')
    return result


def safe_equal(a, b):
    return hmac.compare_digest(str(a).encode(), str(b).encode())


def authorized_order(data):
    order_id, token = data.get('orderId'), data.get('token')
    if not isinstance(order_id, str) or not isinstance(token, str):
        return None
    with db() as con:
        order = con.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    if not order or not order['access_token'] or not safe_equal(token, order['access_token']):
        return None
    return order


def generate_premium(payload):
    prompt = ('한국어로 구미호 연애운 프리미엄 자기성찰 리포트를 작성하세요. 900~1300자, 제목과 5개 소제목. '
              '관계에서 점검할 질문과 실천 조언을 구체적으로 쓰되, 미래를 단정하거나 상대의 감정을 읽는 척하지 마세요. '
              '실제 사주팔자 계산이 없으므로 일주, 월주, 용신, 대운, 궁합 점수를 만들어내지 마세요. '
              '오락적 상징 해석임을 끝에 분명히 밝히세요. 개인정보를 되풀이하지 마세요.\n입력: ' + json.dumps(payload, ensure_ascii=False))
    result = external_json('https://api.openai.com/v1/chat/completions', {'model': OPENAI_MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.7}, {'Authorization': 'Bearer ' + OPENAI_API_KEY})
    return result['choices'][0]['message']['content'].strip()


@app.after_request
def cors(resp):
    origin = request.headers.get('Origin', '').rstrip('/')
    if origin in ALLOWED_ORIGINS:
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Vary'] = 'Origin'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@app.route('/api/<path:path>', methods=['OPTIONS'])
def options(path):
    return '', 204


@app.get('/')
def home():
    return send_from_directory('static', 'index.html')


@app.get('/api/health')
def health():
    return jsonify(ok=True)


@app.get('/api/config')
def config():
    return jsonify(payment_enabled=PAYMENT_ENABLED, price=PRICE, provider='payapp')


@app.post('/api/preview')
def preview():
    try:
        return jsonify(preview_for(parse_payload(request.get_json(silent=True))))
    except ValueError as exc:
        return error(str(exc))


@app.post('/api/orders')
def create_order():
    if not PAYMENT_ENABLED:
        return error('결제 기능이 아직 설정되지 않았습니다.', 503)
    data = request.get_json(silent=True) or {}
    try:
        payload = parse_payload(data)
    except ValueError as exc:
        return error(str(exc))
    phone = re.sub(r'[^0-9]', '', str(data.get('phone', '')))
    if not re.fullmatch(r'01[0-9]{8,9}', phone):
        return error('결제에 사용할 휴대전화 번호를 입력해 주세요.')
    order_id = 'gumiho_' + secrets.token_urlsafe(20).replace('-', 'A').replace('_', 'B')
    token = secrets.token_urlsafe(32)
    with db() as con:
        con.execute('INSERT INTO orders (id,amount,payload,status,created_at,access_token) VALUES (?,?,?,?,?,?)',
                    (order_id, PRICE, json.dumps(payload), 'created', datetime.now(timezone.utc).isoformat(), token))
    fields = {
        'cmd': 'payrequest', 'userid': PAYAPP_USERID,
        'goodname': '구미호 AI 프리미엄 연애운', 'price': str(PRICE),
        'recvphone': phone, 'smsuse': 'n', 'reqaddr': '0',
        'feedbackurl': PAYAPP_PUBLIC_URL + '/api/payapp/feedback',
        'returnurl': SITE_URL + '/?payment=return',
        'var1': order_id, 'checkretry': 'y'
    }
    try:
        result = payapp_request(fields)
    except RuntimeError as exc:
        with db() as con:
            con.execute("UPDATE orders SET status='error' WHERE id=? AND status='created'", (order_id,))
        return error(str(exc), 502)
    with db() as con:
        con.execute('UPDATE orders SET mul_no=? WHERE id=?', (str(result['mul_no']), order_id))
    return jsonify(orderId=order_id, token=token, payurl=result['payurl'], amount=PRICE)


@app.post('/api/payapp/feedback')
def payapp_feedback():
    data = request.form
    if not PAYMENT_ENABLED:
        return 'FAIL', 503
    if not (safe_equal(data.get('userid', ''), PAYAPP_USERID)
            and safe_equal(data.get('linkkey', ''), PAYAPP_LINKKEY)
            and safe_equal(data.get('linkval', ''), PAYAPP_LINKVAL)):
        return 'FAIL', 403
    order_id = data.get('var1', '')
    with db() as con:
        order = con.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        if not order or str(order['mul_no']) != str(data.get('mul_no', '')) or str(order['amount']) != str(data.get('price', '')):
            return 'FAIL', 400
        state = data.get('pay_state')
        if state == '4':
            if order['status'] in ('created', 'paid'):
                con.execute("UPDATE orders SET status='paid' WHERE id=? AND status='created'", (order_id,))
        elif state in ('8', '32', '9', '64', '70', '71'):
            con.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
        elif state in ('1', '10'):
            pass
        else:
            return 'FAIL', 400
    return 'SUCCESS', 200


@app.post('/api/orders/status')
def order_status():
    order = authorized_order(request.get_json(silent=True) or {})
    if not order:
        return error('주문 인증에 실패했습니다.', 403)
    return jsonify(status=order['status'])


@app.post('/api/premium')
def premium():
    data = request.get_json(silent=True) or {}
    order = authorized_order(data)
    if not order or order['status'] != 'paid':
        return error('결제 완료된 주문만 분석할 수 있습니다.', 403)
    order_id = order['id']
    if order['result']:
        return jsonify(result=order['result'])
    if not OPENAI_API_KEY:
        return error('AI 설정이 필요합니다. 관리자에게 문의해 주세요.', 503)
    try:
        report = generate_premium(json.loads(order['payload']))
    except (RuntimeError, KeyError, IndexError, ValueError) as exc:
        app.logger.error('AI 분석 오류: %s', exc)
        return error('AI 분석 생성이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.', 502)
    with db() as con:
        con.execute('UPDATE orders SET result=? WHERE id=? AND result IS NULL', (report, order_id))
        saved = con.execute('SELECT result FROM orders WHERE id=?', (order_id,)).fetchone()
    return jsonify(result=saved['result'])


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=int(os.environ.get('PORT', 5000)))
