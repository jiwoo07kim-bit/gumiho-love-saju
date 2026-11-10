import os, re, uuid, sqlite3, json, base64
from datetime import datetime, timezone
from pathlib import Path
import requests
from flask import Flask, request, jsonify, send_from_directory
from korean_lunar_calendar import KoreanLunarCalendar

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)
STEMS = '갑을병정무기경신임계'
BRANCHES = '자축인묘진사오미신유술해'
ELEMENTS = ['목','목','화','화','토','토','금','금','수','수']
BRANCH_ELEMENTS = ['수','토','목','목','토','화','화','토','금','금','토','수']
TOPICS = {'love':'나의 연애운','reunion':'그 사람과의 재회운','compatibility':'두 사람의 궁합'}
DB = os.getenv('DB_PATH', '/tmp/gumiho_orders.sqlite3')

def db():
    conn = sqlite3.connect(DB)
    conn.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, amount INTEGER NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, result TEXT)')
    conn.commit()
    return conn

def pillars(birth, hour=None):
    day = datetime.strptime(birth, '%Y-%m-%d')
    if not 1900 <= day.year <= 2050: raise ValueError('1900~2050년 생년월일만 지원합니다.')
    cal = KoreanLunarCalendar()
    if not cal.setSolarDate(day.year, day.month, day.day): raise ValueError('날짜를 확인해주세요.')
    parts = cal.getChineseGapJa().split()
    if len(parts) < 3: raise ValueError('만세력 변환에 실패했습니다.')
    pairs = [re.sub(r'[^갑을병정무기경신임계자축인묘진사오미신유술해]', '', p)[:2] for p in parts[:3]]
    if any(len(p)!=2 for p in pairs): raise ValueError('간지 변환에 실패했습니다.')
    if hour not in (None, ''):
        h = int(hour)
        if h < 0 or h > 23: raise ValueError('출생 시간을 확인해주세요.')
        branch = ((h+1)//2)%12
        stem = ((STEMS.index(pairs[2][0])%5)*2 + branch)%10
        pairs.append(STEMS[stem]+BRANCHES[branch])
    counts = {k:0 for k in ['목','화','토','금','수']}
    for p in pairs:
        counts[ELEMENTS[STEMS.index(p[0])]] += 1
        counts[BRANCH_ELEMENTS[BRANCHES.index(p[1])]] += 1
    return {'pillars':dict(zip(['year','month','day','hour'], pairs + ([None] if len(pairs)==3 else []))), 'day_master':pairs[2][0], 'elements':counts, 'time_known':len(pairs)==4}

def parse_payload(data):
    birth = str(data.get('birth',''))
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',birth): raise ValueError('생년월일을 YYYY-MM-DD 형식으로 입력해주세요.')
    topic = data.get('topic','love')
    if topic not in TOPICS: raise ValueError('분석 종류가 올바르지 않습니다.')
    hour = data.get('hour')
    if hour not in (None,''): hour = int(hour)
    other = data.get('other_birth','')
    if topic=='compatibility' and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(other)):
        raise ValueError('상대방 생년월일을 입력해주세요.')
    return {'birth':birth,'hour':hour,'topic':topic,'other_birth':other}

def preview(data):
    payload = parse_payload(data)
    base = pillars(payload['birth'], payload['hour'])
    element = ELEMENTS[STEMS.index(base['day_master'])]
    messages = {'목':'관계에서 함께 성장하고 대화하는 경험을 중요하게 여기는 상징입니다.', '화':'감정 표현과 설렘의 에너지를 중시하는 상징입니다.', '토':'안정감과 신뢰를 쌓아가는 관계를 중시하는 상징입니다.', '금':'분명한 기준과 서로의 약속을 중시하는 상징입니다.', '수':'섬세한 교감과 깊은 이해를 중시하는 상징입니다.'}
    result = {'title':TOPICS[payload['topic']], 'birth':payload['birth'], 'saju':base, 'preview':f"일간은 {base['day_master']}({element})입니다. 전통 명리학의 상징적 해석에서 {messages[element]}", 'notice':'전통 명리학을 활용한 오락·자기성찰 콘텐츠이며 실제 미래를 예측하거나 관계의 결과를 보장하지 않습니다. 월주는 라이브러리 기준으로 계산되며 절기 경계·출생지·자시 기준은 전문 만세력과 대조가 필요합니다.'}
    if payload['topic']=='compatibility': result['other'] = pillars(payload['other_birth'])
    return result

@app.get('/')
def home(): return send_from_directory(ROOT,'index.html')

@app.get('/health')
def health(): return jsonify(status='running',service='구미호 연애운 사주')

@app.post('/api/preview')
def api_preview():
    try: return jsonify(preview(request.get_json(silent=True) or {}))
    except (ValueError,TypeError,IndexError) as e: return jsonify(error=str(e)),400

@app.get('/api/config')
def config():
    return jsonify(payment_enabled=bool(os.getenv('TOSS_CLIENT_KEY') and os.getenv('TOSS_SECRET_KEY') and os.getenv('OPENAI_API_KEY')), client_key=os.getenv('TOSS_CLIENT_KEY',''), price=int(os.getenv('PREMIUM_PRICE','4900')))

@app.post('/api/orders')
def create_order():
    if not all(os.getenv(k) for k in ('TOSS_CLIENT_KEY','TOSS_SECRET_KEY','OPENAI_API_KEY')): return jsonify(error='유료 기능 준비 중입니다.'),503
    try:
        payload=parse_payload(request.get_json(silent=True) or {})
        preview(payload)
        order_id='gumiho_'+uuid.uuid4().hex
        amount=int(os.getenv('PREMIUM_PRICE','4900'))
        with db() as conn: conn.execute('INSERT INTO orders VALUES (?,?,?,?,?)',(order_id,amount,'pending',json.dumps(payload),None))
        return jsonify(orderId=order_id,amount=amount,orderName='구미호 프리미엄 연애운 분석')
    except (ValueError,TypeError) as e: return jsonify(error=str(e)),400

@app.post('/api/payments/confirm')
def confirm_payment():
    secret=os.getenv('TOSS_SECRET_KEY')
    if not secret: return jsonify(error='결제가 설정되지 않았습니다.'),503
    data=request.get_json(silent=True) or {}
    oid=data.get('orderId',''); key=data.get('paymentKey',''); amount=data.get('amount')
    with db() as conn:
        row=conn.execute('SELECT amount,status FROM orders WHERE id=?',(oid,)).fetchone()
        if not row or row[1]!='pending' or type(amount)!=int or amount!=row[0]: return jsonify(error='주문 정보를 확인해주세요.'),400
        token=base64.b64encode((secret+':').encode()).decode()
        try:
            r=requests.post('https://api.tosspayments.com/v1/payments/confirm',json={'paymentKey':key,'orderId':oid,'amount':amount},headers={'Authorization':'Basic '+token},timeout=20)
            body=r.json()
        except (requests.RequestException,ValueError): return jsonify(error='결제사 연결 오류'),502
        if r.status_code!=200 or body.get('status')!='DONE': return jsonify(error='결제 승인 실패',detail=body.get('message','')),400
        conn.execute("UPDATE orders SET status='paid' WHERE id=?",(oid,))
    return jsonify(ok=True,orderId=oid)

@app.post('/api/premium')
def premium():
    data=request.get_json(silent=True) or {}
    oid=data.get('orderId','')
    with db() as conn:
        row=conn.execute('SELECT status,payload,result FROM orders WHERE id=?',(oid,)).fetchone()
        if not row or row[0]!='paid': return jsonify(error='결제 확인이 필요합니다.'),403
        if row[2]: return jsonify(result=json.loads(row[2]))
        payload=json.loads(row[1])
    if not os.getenv('OPENAI_API_KEY'): return jsonify(error='AI 기능이 설정되지 않았습니다.'),503
    facts=preview(payload)
    prompt='다음 만세력 계산 결과를 바탕으로 전통 명리학의 상징적 해석을 한국어로 작성해 주세요. 미래의 사건이나 상대방 감정을 단정하지 말고, 재회·결혼을 보장하지 마세요. 섹션: 타고난 연애 성향, 관계의 강점, 주의할 패턴, 실천 조언. 900~1300자. 데이터: '+json.dumps(facts,ensure_ascii=False)
    try:
        r=requests.post('https://api.openai.com/v1/chat/completions',headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']},json={'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'messages':[{'role':'system','content':'당신은 전통 명리학을 문화적 상징 체계로 설명하는 한국어 콘텐츠 작가입니다.'},{'role':'user','content':prompt}],'temperature':0.7},timeout=55)
        r.raise_for_status()
        answer=r.json()['choices'][0]['message']['content']
    except (requests.RequestException,KeyError,IndexError,ValueError): return jsonify(error='AI 분석을 잠시 생성할 수 없습니다. 다시 시도해주세요.'),502
    with db() as conn: conn.execute('UPDATE orders SET result=? WHERE id=? AND status=?',(json.dumps(answer,ensure_ascii=False),oid,'paid'))
    return jsonify(result=answer)

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
