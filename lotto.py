import os
import json
import time
import math
import random
import logging
import threading
import hashlib
import requests
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from flask import Flask, request
import telebot
from telebot import types

# ================================================================
# 1️⃣ CẤU HÌNH - ĐIỀN userId VÀ secretKey CỦA MÀY VÀO ĐÂY
# ================================================================
USER_ID = "11575993"
SECRET_KEY = "cc8f1ddcdd33163122073bd3cacaf80c825624b256090d60fda4dc2bf5fef0e5"
# ================================================================

# ==================== CẤU HÌNH RENDER ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8385677064:AAHS5ZqmV9QPka3I1t84lyysLzLsLTp3N6g")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "7564889663").split(",")]
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://lotto-ivyd.onrender.com/webhook")
PORT = int(os.environ.get("PORT", 5000))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ==================== ICONS ====================
ICONS = {
    "crown": "👑", "user": "👤", "key": "🔑", "check": "✅", "cross": "❌",
    "warning": "⚠️", "info": "ℹ️", "money": "💰", "chart": "📊", "fire": "🔥",
    "clock": "⏰", "robot": "🤖", "target": "🎯", "diamond": "💎", "star": "⭐"
}

# ==================== API LOTTO ====================
LOTTO_HOME_API = "https://api.winhash.net/lucky_game/home"
LOTTO_HISTORY_API = "https://api.winhash.net/lucky_game/hourly_issue_list"

def get_headers():
    return {
        'user-id': str(USER_ID),
        'user-secret-key': SECRET_KEY,
        'content-type': 'application/json'
    }

def get_home():
    try:
        resp = requests.get(LOTTO_HOME_API, headers=get_headers(), timeout=10)
        return resp.json()
    except:
        return {}

def get_history():
    try:
        ts = int(time.time())
        resp = requests.get(LOTTO_HISTORY_API, params={'ts': ts}, headers=get_headers(), timeout=10)
        data = resp.json()
        if data.get('code') == 0:
            return data.get('data', [])
        return []
    except:
        return []

# ==================== 8 THUẬT TOÁN THÀNH PHẦN ====================
def predict_random(history):
    return random.choice(["big", "small"])

def predict_hot_cold(history):
    if len(history) < 5:
        return "big"
    counts = Counter()
    for h in history[-20:]:
        for num in h.get('lucky_codes', []):
            counts[num] += 1
    hot = [num for num, _ in counts.most_common(3)]
    s = sum(hot[:3])
    if 3 <= s <= 9:
        return "small"
    elif 12 <= s <= 18:
        return "big"
    return "big"

def predict_trend(history):
    if len(history) < 10:
        return "big"
    trends = {i: 0 for i in range(1, 7)}
    for i in range(len(history) - 1):
        cur = history[i].get('lucky_codes', [])
        nxt = history[i+1].get('lucky_codes', [])
        if len(cur) == 3 and len(nxt) == 3:
            for pos in range(3):
                if nxt[pos] > cur[pos]:
                    trends[nxt[pos]] += 1
    pred = sorted(trends, key=trends.get, reverse=True)[:3]
    s = sum(pred)
    if 3 <= s <= 9:
        return "small"
    elif 12 <= s <= 18:
        return "big"
    return "big"

def predict_pattern_match(history):
    if len(history) < 5:
        return "big"
    last = history[-1].get('lucky_codes', [])
    if len(last) != 3:
        return "big"
    for i in range(len(history) - 2, -1, -1):
        prev = history[i].get('lucky_codes', [])
        if len(prev) == 3 and prev == last:
            if i + 1 < len(history):
                nxt = history[i+1].get('lucky_codes', [])
                if len(nxt) == 3:
                    s = sum(nxt)
                    if 3 <= s <= 9:
                        return "small"
                    elif 12 <= s <= 18:
                        return "big"
    return "big"

def predict_last_3(history):
    if len(history) < 3:
        return "big"
    counts = Counter()
    for h in history[-3:]:
        for num in h.get('lucky_codes', []):
            counts[num] += 1
    pred = [num for num in range(1, 7) if counts[num] == 0][:3]
    while len(pred) < 3:
        pred.append(1)
    s = sum(pred[:3])
    if 3 <= s <= 9:
        return "small"
    elif 12 <= s <= 18:
        return "big"
    return "big"

def predict_markov(history):
    if len(history) < 10:
        return "big"
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(history) - 1):
        cur = tuple(history[i].get('lucky_codes', []))
        nxt = tuple(history[i+1].get('lucky_codes', []))
        if len(cur) == 3 and len(nxt) == 3:
            trans[cur][nxt] += 1
    last = tuple(history[-1].get('lucky_codes', []))
    if len(last) == 3 and last in trans and trans[last]:
        pred = max(trans[last], key=trans[last].get)
        s = sum(pred)
        if 3 <= s <= 9:
            return "small"
        elif 12 <= s <= 18:
            return "big"
    return "big"

def predict_bayesian(history):
    if len(history) < 5:
        return "big"
    last_sum = sum(history[-1].get('lucky_codes', []))
    prior = {i: 1/6 for i in range(1, 7)}
    likelihood = defaultdict(lambda: defaultdict(float))
    for i in range(len(history) - 1):
        cur = history[i].get('lucky_codes', [])
        nxt = history[i+1].get('lucky_codes', [])
        if len(cur) == 3 and len(nxt) == 3:
            cs = sum(cur)
            for num in nxt:
                likelihood[cs][num] += 1
    for s in likelihood:
        total = sum(likelihood[s].values())
        if total > 0:
            for num in likelihood[s]:
                likelihood[s][num] /= total
    posterior = {}
    for num in range(1, 7):
        posterior[num] = prior[num] * likelihood.get(last_sum, {}).get(num, 1/6)
    total_posterior = sum(posterior.values())
    if total_posterior > 0:
        for num in posterior:
            posterior[num] /= total_posterior
    pred = sorted(posterior, key=posterior.get, reverse=True)[:3]
    s = sum(pred)
    if 3 <= s <= 9:
        return "small"
    elif 12 <= s <= 18:
        return "big"
    return "big"

def predict_neural(history):
    if len(history) < 8:
        return "big"
    last = history[-1].get('lucky_codes', [])
    if len(last) != 3:
        return "big"
    features = []
    for num in last:
        for i in range(1, 7):
            features.append(1.0 if num == i else 0.0)
    s_last = sum(last)
    features.append(s_last / 18.0)
    if len(history) >= 3:
        prev_sum = sum(history[-2].get('lucky_codes', []))
        prev2_sum = sum(history[-3].get('lucky_codes', []))
        features.append((s_last - prev_sum) / 18.0)
        features.append((prev_sum - prev2_sum) / 18.0)
    else:
        features.append(0.0)
        features.append(0.0)
    hidden = []
    weights1 = [0.5, -0.3, 0.7, -0.2, 0.4, -0.6] * 3
    for i in range(6):
        hidden.append(1 / (1 + math.exp(-sum(features[j] * weights1[j % len(weights1)] for j in range(len(features))))))
    output = [0.0] * 6
    weights2 = [0.4, -0.2, 0.6, -0.1, 0.3, -0.5]
    for i in range(6):
        output[i] = sum(hidden[j] * weights2[(i + j) % len(weights2)] for j in range(len(hidden)))
    exp_output = [math.exp(o) for o in output]
    sum_exp = sum(exp_output)
    if sum_exp > 0:
        output = [o / sum_exp for o in exp_output]
    pred = sorted(range(1, 7), key=lambda x: output[x-1], reverse=True)[:3]
    s = sum(pred)
    if 3 <= s <= 9:
        return "small"
    elif 12 <= s <= 18:
        return "big"
    return "big"

# ==================== THUẬT TOÁN ENSEMBLE VIP ====================
def predict_lotto_ensemble(history):
    if len(history) < 5:
        return {
            "prediction": "LỚN",
            "confidence": 50,
            "prob_lon": 50,
            "prob_nho": 50,
            "reason": "Chưa đủ dữ liệu (cần 5 phiên)"
        }
    
    votes = []
    algos = [
        predict_random, predict_hot_cold, predict_trend,
        predict_pattern_match, predict_last_3, predict_markov,
        predict_bayesian, predict_neural
    ]
    
    for algo in algos:
        try:
            result = algo(history)
            if result in ["big", "small"]:
                votes.append(result)
        except:
            continue
    
    if not votes:
        return {
            "prediction": "LỚN",
            "confidence": 50,
            "prob_lon": 50,
            "prob_nho": 50,
            "reason": "Không có dự đoán hợp lệ"
        }
    
    vote_count = Counter(votes)
    bet_action = vote_count.most_common(1)[0][0]
    total_votes = len(votes)
    consensus = vote_count.most_common(1)[0][1] / total_votes
    
    prediction_vn = "LỚN" if bet_action == "big" else "NHỎ"
    confidence = int(55 + consensus * 40)
    confidence = min(95, max(55, confidence))
    
    prob_lon = sum(1 for v in votes if v == "big") / len(votes) * 100
    prob_nho = sum(1 for v in votes if v == "small") / len(votes) * 100
    
    reason = f"Tổng hợp {len(votes)}/{len(algos)} thuật toán:\n"
    reason += f"  • LỚN: {vote_count.get('big', 0)} phiếu\n"
    reason += f"  • NHỎ: {vote_count.get('small', 0)} phiếu\n"
    reason += f"  • Consensus: {consensus*100:.0f}%"
    
    return {
        "prediction": prediction_vn,
        "confidence": confidence,
        "prob_lon": round(prob_lon, 1),
        "prob_nho": round(prob_nho, 1),
        "reason": reason,
        "total_analyzed": len(history),
        "votes": dict(vote_count),
        "consensus": round(consensus * 100, 1)
    }

# ==================== QUẢN LÝ KEY ====================
KEYS_FILE = "lotto_keys.json"
user_keys = {}

def load_keys():
    global user_keys
    try:
        with open(KEYS_FILE, 'r') as f:
            user_keys = json.load(f)
    except:
        user_keys = {}

def save_keys():
    try:
        with open(KEYS_FILE, 'w') as f:
            json.dump(user_keys, f, indent=2)
    except:
        pass

load_keys()

def generate_key(days: int) -> str:
    raw = f"{USER_ID}:{datetime.now().isoformat()}:{random.randint(100000, 999999)}"
    key = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    expiry = (datetime.now() + timedelta(days=days)).isoformat()
    user_keys[key] = {
        "created": datetime.now().isoformat(),
        "expiry": expiry,
        "days": days,
        "used_by": []
    }
    save_keys()
    return key

def verify_key(key: str, user_id: int) -> bool:
    if key not in user_keys:
        return False
    data = user_keys[key]
    expiry = datetime.fromisoformat(data["expiry"])
    if datetime.now() > expiry:
        return False
    if str(user_id) not in data["used_by"]:
        data["used_by"].append(str(user_id))
        save_keys()
    return True

def get_key_info(key: str) -> dict:
    if key not in user_keys:
        return None
    data = user_keys[key]
    expiry = datetime.fromisoformat(data["expiry"])
    remaining = (expiry - datetime.now()).days
    return {
        "key": key,
        "created": data["created"],
        "expiry": data["expiry"],
        "days": data["days"],
        "remaining": remaining,
        "used_by": data["used_by"]
    }

# ==================== TRẠNG THÁI AUTO ====================
STATE_FILE = "lotto_state.json"
auto_bet_running = False
auto_bet_thread = None
last_issue = None
prediction_history = []
stats = {"win": 0, "lose": 0, "total": 0}

def load_state():
    global auto_bet_running, last_issue, prediction_history, stats
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            auto_bet_running = data.get('auto_bet_running', False)
            last_issue = data.get('last_issue', None)
            prediction_history = data.get('prediction_history', [])
            stats = data.get('stats', {"win": 0, "lose": 0, "total": 0})
    except:
        pass

def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'auto_bet_running': auto_bet_running,
                'last_issue': last_issue,
                'prediction_history': prediction_history[-50:],
                'stats': stats
            }, f, indent=2)
    except:
        pass

load_state()

# ==================== AUTO BET LOOP ====================
def auto_bet_loop(chat_id):
    global auto_bet_running, last_issue, prediction_history, stats
    
    while auto_bet_running:
        try:
            home = get_home()
            if not home or home.get('code') != 0:
                time.sleep(3)
                continue
            
            data = home.get('data', {})
            current_issue = data.get('last_issue_id')
            current_result = data.get('last_issue_result')
            lucky_codes = data.get('last_issue_lucky_code', [])
            
            if current_issue and current_issue != last_issue:
                last_issue = current_issue
                
                history_data = get_history()
                history = []
                for h in history_data[-30:]:
                    codes = h.get('lucky_codes', [])
                    if len(codes) == 3:
                        total = sum(codes)
                        if 3 <= total <= 9 or 12 <= total <= 18:
                            result = "LỚN" if 12 <= total <= 18 else "NHỎ"
                            history.append({
                                'issue_id': h.get('issue_id'),
                                'result': result,
                                'total': total,
                                'lucky_codes': codes
                            })
                
                pred = predict_lotto_ensemble(history)
                prediction = pred['prediction']
                
                prediction_history.append({
                    'issue': current_issue,
                    'prediction': prediction,
                    'confidence': pred['confidence'],
                    'actual': None,
                    'result': None,
                    'time': datetime.now().strftime('%H:%M:%S')
                })
                
                bot.send_message(chat_id, f"""
🔮 *DỰ ĐOÁN PHIÊN #{current_issue}*
━━━━━━━━━━━━━━━━━━━
🎯 *Dự đoán:* **{prediction}**
📊 *Độ tin cậy:* {pred['confidence']}%
📈 *LỚN:* {pred['prob_lon']}% | *NHỎ:* {pred['prob_nho']}%

🧠 {pred['reason']}
━━━━━━━━━━━━━━━━━━━
⏳ Chờ kết quả...
""", parse_mode='Markdown')
                
                save_state()
            
            if current_result and prediction_history:
                last_pred = prediction_history[-1]
                if last_pred.get('actual') is None and last_pred.get('issue') != current_issue:
                    actual = "LỚN" if current_result == "TAI" else "NHỎ"
                    last_pred['actual'] = actual
                    last_pred['result'] = "✅ ĐÚNG" if last_pred['prediction'] == actual else "❌ SAI"
                    
                    if last_pred['prediction'] == actual:
                        stats['win'] += 1
                    else:
                        stats['lose'] += 1
                    stats['total'] += 1
                    
                    icon = "✅" if last_pred['prediction'] == actual else "❌"
                    bot.send_message(chat_id, f"""
{icon} *KẾT QUẢ PHIÊN #{last_pred['issue']}*
━━━━━━━━━━━━━━━━━━━
🎯 Dự đoán: *{last_pred['prediction']}*
📊 Thực tế: *{actual}*
🔢 Bộ số: {' '.join(map(str, lucky_codes)) if lucky_codes else '---'}

📈 *Thống kê:*
• Đúng: {stats['win']}
• Sai: {stats['lose']}
• Tỷ lệ: {stats['win']/stats['total']*100:.1f}% ({stats['total']} phiên)
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown')
                    
                    save_state()
            
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Auto bet error: {e}")
            time.sleep(5)

def start_auto_bet(chat_id):
    global auto_bet_running, auto_bet_thread
    if auto_bet_running:
        return False
    auto_bet_running = True
    auto_bet_thread = threading.Thread(target=auto_bet_loop, args=(chat_id,), daemon=True)
    auto_bet_thread.start()
    save_state()
    return True

def stop_auto_bet():
    global auto_bet_running
    auto_bet_running = False
    save_state()
    return True

# ==================== MENU ====================
def main_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔮 Dự đoán 1 lần", callback_data='predict'),
        types.InlineKeyboardButton("📜 Lịch sử", callback_data='history'),
        types.InlineKeyboardButton("📊 Thống kê", callback_data='stats'),
    )
    auto_status = "⏹ Dừng" if auto_bet_running else "▶️ Bắt đầu"
    keyboard.add(
        types.InlineKeyboardButton(f"🤖 Auto {auto_status}", callback_data='auto_toggle'),
    )
    keyboard.add(
        types.InlineKeyboardButton("🗑️ Xóa lịch sử", callback_data='clear_history'),
    )
    return keyboard

def admin_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("👑 Tạo Key 1 ngày", callback_data='create_key_1'),
        types.InlineKeyboardButton("👑 Tạo Key 7 ngày", callback_data='create_key_7'),
        types.InlineKeyboardButton("👑 Tạo Key 30 ngày", callback_data='create_key_30'),
        types.InlineKeyboardButton("📋 Danh sách Key", callback_data='list_keys'),
        types.InlineKeyboardButton("🔍 Kiểm tra Key", callback_data='check_key'),
    )
    return keyboard

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
def send_start(message):
    user_id = message.chat.id
    
    if user_id in ADMIN_IDS:
        bot.reply_to(message, f"""
{ICONS['crown']} *LOTTO PREDICT BOT - ADMIN* {ICONS['crown']}
━━━━━━━━━━━━━━━━━━━
{ICONS['robot']} ENSEMBLE VIP - 8 thuật toán
{ICONS['user']} Tài khoản: `{USER_ID}`

📊 *Thống kê:*
✅ Đúng: {stats['win']}
❌ Sai: {stats['lose']}
🎯 Tỷ lệ: {stats['win']/(stats['total'] or 1)*100:.1f}%
━━━━━━━━━━━━━━━━━━━
📌 Bấm nút bên dưới!
""", reply_markup=main_menu(), parse_mode='Markdown')
        return
    
    # User thường - yêu cầu nhập key
    bot.reply_to(message, f"""
{ICONS['lock']} *LOTTO PREDICT BOT* {ICONS['lock']}
━━━━━━━━━━━━━━━━━━━
{ICONS['robot']} Bot dự đoán LỚN/NHỎ
{ICONS['target']} Thuật toán ENSEMBLE VIP

📌 *Nhập Key để kích hoạt:*
`/key <MÃ_KEY>`

🔑 Mua Key: liên hệ admin
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown')

@bot.message_handler(commands=['key'])
def activate_key(message):
    user_id = message.chat.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Nhập: /key <MÃ_KEY>")
        return
    
    key = parts[1].strip().upper()
    if verify_key(key, user_id):
        bot.reply_to(message, f"""
✅ *KÍCH HOẠT THÀNH CÔNG!*
━━━━━━━━━━━━━━━━━━━
🔑 Key: `{key}`
⏳ Hạn: {get_key_info(key)['remaining']} ngày
━━━━━━━━━━━━━━━━━━━
📌 Bấm /start để bắt đầu dùng!
""", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Key không hợp lệ hoặc đã hết hạn!")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return
    
    bot.reply_to(message, f"""
👑 *ADMIN PANEL* 👑
━━━━━━━━━━━━━━━━━━━
📊 *Key đã tạo:* {len(user_keys)}
👥 *Người dùng:* {sum(len(data['used_by']) for data in user_keys.values())}
━━━━━━━━━━━━━━━━━━━
""", reply_markup=admin_menu(), parse_mode='Markdown')

# ==================== CALLBACK ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    
    data = call.data
    bot.answer_callback_query(call.id)
    
    if data == 'predict':
        show_predict(call.message)
    elif data == 'history':
        show_history(call.message)
    elif data == 'stats':
        show_stats(call.message)
    elif data == 'auto_toggle':
        toggle_auto(call.message)
    elif data == 'clear_history':
        clear_history(call.message)
    elif data == 'create_key_1':
        create_key(call.message, 1)
    elif data == 'create_key_7':
        create_key(call.message, 7)
    elif data == 'create_key_30':
        create_key(call.message, 30)
    elif data == 'list_keys':
        list_keys(call.message)
    elif data == 'check_key':
        msg = bot.send_message(call.message.chat.id, "📌 Nhập Key cần kiểm tra:")
        bot.register_next_step_handler(msg, check_key_input)

# ==================== ADMIN FUNCTIONS ====================
def create_key(message, days):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Không có quyền!")
        return
    
    key = generate_key(days)
    info = get_key_info(key)
    bot.reply_to(message, f"""
✅ *KEY ĐÃ TẠO*
━━━━━━━━━━━━━━━━━━━
🔑 Key: `{key}`
📅 Hạn: {days} ngày
⏳ Hết hạn: {info['expiry'][:10]}
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=admin_menu())

def list_keys(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Không có quyền!")
        return
    
    if not user_keys:
        bot.reply_to(message, "📭 Chưa có Key nào!", reply_markup=admin_menu())
        return
    
    text = f"📋 *DANH SÁCH KEY*\n━━━━━━━━━━━━━━━━━━━\n"
    for k, v in user_keys.items():
        expiry = datetime.fromisoformat(v["expiry"])
        remaining = (expiry - datetime.now()).days
        status = "🟢" if remaining > 0 else "🔴"
        text += f"{status} `{k}` | {v['days']} ngày | còn {remaining} ngày | {len(v['used_by'])} user\n"
    
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=admin_menu())

def check_key_input(message):
    key = message.text.strip().upper()
    info = get_key_info(key)
    if info:
        remaining = info['remaining']
        status = "🟢 Còn hiệu lực" if remaining > 0 else "🔴 Hết hạn"
        bot.reply_to(message, f"""
🔍 *THÔNG TIN KEY*
━━━━━━━━━━━━━━━━━━━
🔑 Key: `{key}`
📅 Hạn: {info['days']} ngày
⏳ Còn: {remaining} ngày
👥 Đã dùng: {len(info['used_by'])} user
📊 Trạng thái: {status}
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ Key không tồn tại!", reply_markup=admin_menu())

# ==================== USER FUNCTIONS ====================
def show_predict(message):
    msg = bot.reply_to(message, "⏳ Đang phân tích với ENSEMBLE VIP...")
    
    try:
        history_data = get_history()
        if not history_data:
            bot.edit_message_text("⚠️ Không lấy được lịch sử!", chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=main_menu())
            return
        
        history = []
        for h in history_data[-30:]:
            codes = h.get('lucky_codes', [])
            if len(codes) == 3:
                total = sum(codes)
                if 3 <= total <= 9 or 12 <= total <= 18:
                    result = "LỚN" if 12 <= total <= 18 else "NHỎ"
                    history.append({
                        'issue_id': h.get('issue_id'),
                        'result': result,
                        'total': total,
                        'lucky_codes': codes
                    })
        
        pred = predict_lotto_ensemble(history)
        
        home = get_home()
        current_issue = home.get('data', {}).get('last_issue_id', '---')
        current_result = home.get('data', {}).get('last_issue_result', '---')
        lucky_codes = home.get('data', {}).get('last_issue_lucky_code', [])
        
        result_text = f"""
🔮 *KẾT QUẢ DỰ ĐOÁN*
━━━━━━━━━━━━━━━━━━━
🎯 *Dự đoán:* **{pred['prediction']}**
📊 *Độ tin cậy:* {pred['confidence']}%
📈 *LỚN:* {pred['prob_lon']}% | *NHỎ:* {pred['prob_nho']}%

🧠 *Phân tích:*
{pred['reason']}

🆔 *Phiên hiện tại:* {current_issue}
🎲 *Kết quả gần nhất:* {current_result}
🔢 *Bộ số:* {' '.join(map(str, lucky_codes)) if lucky_codes else '---'}
━━━━━━━━━━━━━━━━━━━
📌 Dự đoán mang tính tham khảo!
"""
        bot.edit_message_text(result_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='Markdown', reply_markup=main_menu())
        
    except Exception as e:
        bot.edit_message_text(f"❌ Lỗi: {e}", chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=main_menu())

def show_history(message):
    if not prediction_history:
        bot.reply_to(message, "📭 Chưa có lịch sử dự đoán!", reply_markup=main_menu())
        return
    
    recent = prediction_history[-15:][::-1]
    text = f"📜 *LỊCH SỬ DỰ ĐOÁN (15 phiên gần nhất)*\n━━━━━━━━━━━━━━━━━━━\n"
    for h in recent:
        issue = h.get('issue', '---')
        pred = h.get('prediction', '---')
        actual = h.get('actual', '⏳')
        result = h.get('result', '⏳')
        conf = h.get('confidence', 0)
        time_str = h.get('time', '')
        icon = "✅" if "ĐÚNG" in str(result) else "❌" if "SAI" in str(result) else "⏳"
        text += f"{icon} #{issue}: {pred} → {actual} ({conf}%) {time_str}\n"
    
    text += f"\n📊 *Tổng:* Đúng {stats['win']} | Sai {stats['lose']} | Tỷ lệ {stats['win']/(stats['total'] or 1)*100:.1f}%"
    
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=main_menu())

def show_stats(message):
    total = stats['total']
    win = stats['win']
    lose = stats['lose']
    rate = win/(total or 1)*100
    
    text = f"""
📊 *THỐNG KÊ DỰ ĐOÁN*
━━━━━━━━━━━━━━━━━━━
📌 Tổng phiên: {total}
✅ Đúng: {win}
❌ Sai: {lose}
🎯 Tỷ lệ: {rate:.1f}%
━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=main_menu())

def toggle_auto(message):
    chat_id = message.chat.id
    
    if auto_bet_running:
        stop_auto_bet()
        bot.reply_to(message, f"⏹ *Đã dừng Auto Predict*", parse_mode='Markdown', reply_markup=main_menu())
    else:
        start_auto_bet(chat_id)
        bot.reply_to(message, f"▶️ *Đã bắt đầu Auto Predict!*\n⏳ Sẽ tự động dự đoán mỗi phiên mới.", parse_mode='Markdown', reply_markup=main_menu())

def clear_history(message):
    global prediction_history, stats
    prediction_history = []
    stats = {"win": 0, "lose": 0, "total": 0}
    save_state()
    bot.reply_to(message, "🗑️ Đã xóa toàn bộ lịch sử!", reply_markup=main_menu())

# ==================== WEBHOOK ROUTES (FIX) ====================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # Cho phép GET để debug
    if request.method == 'GET':
        return "✅ Webhook is working! Send POST from Telegram.", 200
    
    # Xử lý POST từ Telegram
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        try:
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return '', 200
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return f"❌ Error: {e}", 500
    return '❌ Invalid request', 403

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        return f"✅ Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route('/', methods=['GET'])
def index():
    return "🤖 Lotto Predict Bot is running!", 200

# ==================== MAIN ====================
if __name__ == '__main__':
    print(f"🚀 Lotto Predict Bot đang chạy trên port {PORT}")
    print(f"👤 Clone ID: {USER_ID}")
    print(f"🔗 Webhook URL: {WEBHOOK_URL}")
    app.run(host='0.0.0.0', port=PORT)
