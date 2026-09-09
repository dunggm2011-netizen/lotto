import os
import sys
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
# 1️⃣ CẤU HÌNH CHÍNH - ĐIỀN userId VÀ secretKey CLONE CỦA MÀY
# ================================================================
USER_ID = "11575993"
SECRET_KEY = "cc8f1ddcdd33163122073bd3cacaf80c825624b256090d60fda4dc2bf5fef0e5"

# Cấu hình bot Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8385677064:AAHS5ZqmV9QPka3I1t84lyysLzLsLTp3N6g")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "7564889663").split(",")]
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://lotto-18v2.onrender.com/webhook")
PORT = int(os.environ.get("PORT", 5000))

# Cấu hình hệ thống
MAX_HISTORY = 50
MIN_SAMPLES = 5
AI_LEARN_RATE = 0.1

# ================================================================
# 2️⃣ LOGGING
# ================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================================================================
# 3️⃣ FLASK APP & TELEBOT
# ================================================================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ================================================================
# 4️⃣ ICONS
# ================================================================
ICONS = {
    "crown": "👑",
    "user": "👤",
    "key": "🔑",
    "lock": "🔒",
    "unlock": "🔓",
    "check": "✅",
    "cross": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "money": "💰",
    "chart": "📊",
    "fire": "🔥",
    "clock": "⏰",
    "robot": "🤖",
    "target": "🎯",
    "diamond": "💎",
    "star": "⭐",
    "rocket": "🚀",
    "shield": "🛡️",
    "lightning": "⚡",
    "trophy": "🏆",
    "brain": "🧠",
    "chart_up": "📈",
    "chart_down": "📉",
    "red_circle": "🔴",
    "blue_circle": "🔵",
    "green_circle": "🟢",
    "yellow_circle": "🟡",
    "white_circle": "⚪",
    "black_circle": "⚫",
    "orange_circle": "🟠",
    "purple_circle": "🟣",
    "brown_circle": "🟤",
    "gift": "🎁",
    "bell": "🔔",
    "settings": "⚙️",
    "phone": "📞",
    "vip": "💎",
    "crown_gold": "👑",
    "gem": "💠",
    "sparkle": "✨",
}

# ================================================================
# 5️⃣ API LOTTO
# ================================================================
LOTTO_HOME_API = "https://api.winhash.net/lucky_game/home"
LOTTO_HISTORY_API = "https://api.winhash.net/lucky_game/hourly_issue_list"
LOTTO_WALLET_API = "https://wallet.3games.io/api/wallet/user_asset"

def get_headers():
    return {
        'user-id': str(USER_ID),
        'user-secret-key': SECRET_KEY,
        'content-type': 'application/json',
        'accept': 'application/json',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

def get_home():
    """Lấy thông tin phiên hiện tại"""
    try:
        resp = requests.get(LOTTO_HOME_API, headers=get_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {}
    except Exception as e:
        logger.error(f"get_home error: {e}")
        return {}

def get_history():
    """Lấy lịch sử các phiên gần đây"""
    try:
        ts = int(time.time())
        resp = requests.get(LOTTO_HISTORY_API, params={'ts': ts}, headers=get_headers(), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                return data.get('data', [])
        return []
    except Exception as e:
        logger.error(f"get_history error: {e}")
        return []

def get_balance():
    """Lấy số dư BUILD"""
    try:
        resp = requests.post(LOTTO_WALLET_API, json={"user_id": int(USER_ID), "source": "home"}, headers=get_headers(), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('user_asset', {}).get('BUILD', 0)
        return 0
    except Exception as e:
        logger.error(f"get_balance error: {e}")
        return 0

def parse_history(history_data):
    """Parse dữ liệu lịch sử từ API"""
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
    return history

# ================================================================
# 6️⃣ AI TỰ HỌC (REINFORCEMENT LEARNING)
# ================================================================
LEARNING_FILE = "learning_data.json"

learning_data = {
    "algo_weights": {},
    "history": [],
    "performance": {},
    "total_predictions": 0,
    "total_correct": 0,
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat()
}

def load_learning_data():
    global learning_data
    try:
        if os.path.exists(LEARNING_FILE):
            with open(LEARNING_FILE, 'r', encoding='utf-8') as f:
                learning_data = json.load(f)
            logger.info(f"Loaded learning data: {len(learning_data['history'])} records")
        else:
            logger.info("No learning data found, creating new")
            learning_data = {
                "algo_weights": {},
                "history": [],
                "performance": {},
                "total_predictions": 0,
                "total_correct": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            save_learning_data()
    except Exception as e:
        logger.error(f"load_learning_data error: {e}")
        learning_data = {
            "algo_weights": {},
            "history": [],
            "performance": {},
            "total_predictions": 0,
            "total_correct": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

def save_learning_data():
    try:
        learning_data["updated_at"] = datetime.now().isoformat()
        with open(LEARNING_FILE, 'w', encoding='utf-8') as f:
            json.dump(learning_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save_learning_data error: {e}")

load_learning_data()

# Tên các thuật toán
ALGO_NAMES = [
    "Sequence Analysis",
    "Trend Analysis", 
    "Frequency Analysis",
    "Markov Chain",
    "Reversal Pattern",
    "Hot/Cold Numbers",
    "Neural Network",
    "Random Forest"
]

ALGO_KEYS = ["sequence", "trend", "frequency", "markov", "reversal", "hotcold", "neural", "randomforest"]

def init_algo_weights():
    for name in ALGO_KEYS:
        if name not in learning_data["algo_weights"]:
            learning_data["algo_weights"][name] = 1.0
        if name not in learning_data["performance"]:
            learning_data["performance"][name] = {
                "win": 0,
                "lose": 0,
                "total": 0,
                "win_rate": 0.5,
                "last_10": []
            }
    save_learning_data()

init_algo_weights()

def update_learning(prediction, actual, algo_used):
    """Cập nhật AI học từ kết quả thực tế"""
    is_correct = (prediction == actual)
    
    # Lưu lịch sử
    learning_data["history"].append({
        "prediction": prediction,
        "actual": actual,
        "algo": algo_used,
        "correct": is_correct,
        "timestamp": datetime.now().isoformat()
    })
    
    # Giới hạn lịch sử
    if len(learning_data["history"]) > 500:
        learning_data["history"] = learning_data["history"][-500:]
    
    # Cập nhật tổng
    learning_data["total_predictions"] += 1
    if is_correct:
        learning_data["total_correct"] += 1
    
    # Cập nhật hiệu suất từng thuật toán
    if algo_used in learning_data["performance"]:
        perf = learning_data["performance"][algo_used]
        perf["total"] += 1
        if is_correct:
            perf["win"] += 1
        else:
            perf["lose"] += 1
        perf["win_rate"] = perf["win"] / perf["total"] if perf["total"] > 0 else 0
        
        # Lưu 10 kết quả gần nhất
        perf["last_10"].append(1 if is_correct else 0)
        if len(perf["last_10"]) > 10:
            perf["last_10"] = perf["last_10"][-10:]
    
    # Cập nhật trọng số
    update_algo_weights()
    save_learning_data()

def update_algo_weights():
    """Cập nhật trọng số dựa trên hiệu suất gần đây"""
    recent = learning_data["history"][-20:] if len(learning_data["history"]) >= 20 else learning_data["history"]
    
    # Đếm đúng/sai gần đây cho từng thuật toán
    recent_perf = {}
    for h in recent:
        algo = h.get("algo")
        if algo:
            if algo not in recent_perf:
                recent_perf[algo] = {"win": 0, "lose": 0}
            if h.get("correct"):
                recent_perf[algo]["win"] += 1
            else:
                recent_perf[algo]["lose"] += 1
    
    # Cập nhật trọng số
    for name in ALGO_KEYS:
        if name in recent_perf:
            total = recent_perf[name]["win"] + recent_perf[name]["lose"]
            if total > 0:
                rate = recent_perf[name]["win"] / total
                # Trọng số = (tỷ lệ đúng * 2) + 0.3
                new_weight = max(0.3, min(2.0, (rate * 2) + 0.3))
                learning_data["algo_weights"][name] = new_weight
        else:
            # Giữ nguyên hoặc reset nếu chưa có dữ liệu
            if name not in learning_data["algo_weights"]:
                learning_data["algo_weights"][name] = 1.0

def get_algo_weight(name):
    return learning_data["algo_weights"].get(name, 1.0)

def get_algo_performance(name):
    return learning_data["performance"].get(name, {"win": 0, "lose": 0, "total": 0, "win_rate": 0.5})

def get_best_algos(top_n=3):
    """Lấy top N thuật toán tốt nhất"""
    sorted_algos = sorted(
        [(name, weight) for name, weight in learning_data["algo_weights"].items()],
        key=lambda x: x[1],
        reverse=True
    )
    result = []
    for i, (name, weight) in enumerate(sorted_algos[:top_n]):
        perf = get_algo_performance(name)
        display_name = ALGO_NAMES[ALGO_KEYS.index(name)] if name in ALGO_KEYS else name
        result.append({
            "name": display_name,
            "key": name,
            "weight": weight,
            "win_rate": perf["win_rate"] * 100,
            "total": perf["total"]
        })
    return result

def get_learning_stats():
    """Lấy thống kê học tập tổng hợp"""
    total = learning_data["total_predictions"]
    correct = learning_data["total_correct"]
    rate = correct / total * 100 if total > 0 else 0
    
    stats = {
        "total": total,
        "correct": correct,
        "wrong": total - correct,
        "rate": rate,
        "history_count": len(learning_data["history"])
    }
    return stats

# ================================================================
# 7️⃣ 8 THUẬT TOÁN DỰ ĐOÁN
# ================================================================

def predict_sequence(history):
    """Thuật toán 1: Phân tích chuỗi (Sequence Analysis)"""
    if len(history) < 5:
        return None
    
    recent = [1 if h['result'] == "LỚN" else 0 for h in history[-5:]]
    
    # Tìm pattern lặp
    for i in range(2, len(recent)):
        if recent[-i:] == recent[-i*2:-i]:
            if len(recent) >= i*2 + 1:
                return "LỚN" if recent[-i*2-1] == 1 else "NHỎ"
    
    # Xu hướng 3 phiên gần nhất
    if len(recent) >= 3:
        big_count = sum(recent[-3:])
        if big_count >= 2:
            return "NHỎ"  # Đảo cầu
        elif big_count <= 1:
            return "LỚN"
    
    return None

def predict_trend(history):
    """Thuật toán 2: Phân tích xu hướng (Trend Analysis)"""
    if len(history) < 5:
        return None
    
    results = [h['result'] for h in history[-15:]]
    if not results:
        return None
    
    big_count = sum(1 for r in results if r == "LỚN")
    total = len(results)
    big_rate = big_count / total
    
    # Nếu đang quá lệch, dự đoán đảo chiều
    if big_rate >= 0.7:
        return "NHỎ"
    elif big_rate <= 0.3:
        return "LỚN"
    
    # Theo xu hướng gần nhất
    if len(results) >= 5:
        recent_big = sum(1 for r in results[-5:] if r == "LỚN")
        if recent_big >= 3:
            return "NHỎ" if big_rate > 0.5 else "LỚN"
        elif recent_big <= 2:
            return "LỚN" if big_rate < 0.5 else "NHỎ"
    
    # Nếu cân bằng, theo phiên cuối
    return "LỚN" if results[-1] == "LỚN" else "NHỎ"

def predict_frequency(history):
    """Thuật toán 3: Phân tích tần suất (Frequency Analysis)"""
    if len(history) < 8:
        return None
    
    big_count = sum(1 for h in history if h['result'] == "LỚN")
    small_count = len(history) - big_count
    
    # Nếu chênh lệch > 2, dự đoán theo hướng ngược lại
    if big_count > small_count + 3:
        return "NHỎ"
    elif small_count > big_count + 3:
        return "LỚN"
    
    # Nếu gần cân bằng, theo xu hướng gần nhất
    recent = history[-5:]
    recent_big = sum(1 for h in recent if h['result'] == "LỚN")
    return "LỚN" if recent_big >= 3 else "NHỎ"

def predict_markov(history):
    """Thuật toán 4: Chuỗi Markov (Markov Chain)"""
    if len(history) < 10:
        return None
    
    # Xây dựng ma trận chuyển tiếp 2 bước
    trans = {}
    for i in range(len(history) - 2):
        current = history[i]['result']
        next_res = history[i+1]['result']
        after = history[i+2]['result'] if i+2 < len(history) else None
        
        key = (current, next_res)
        if key not in trans:
            trans[key] = {"LỚN": 0, "NHỎ": 0}
        if after:
            trans[key][after] += 1
    
    # Lấy 2 kết quả gần nhất
    if len(history) >= 2:
        last = history[-1]['result']
        prev = history[-2]['result']
        key = (prev, last)
        
        if key in trans:
            big = trans[key]["LỚN"]
            small = trans[key]["NHỎ"]
            if big > small:
                return "LỚN"
            elif small > big:
                return "NHỎ"
    
    # Fallback: theo xu hướng
    return None

def predict_reversal(history):
    """Thuật toán 5: Phân tích đảo cầu (Reversal Pattern)"""
    if len(history) < 4:
        return None
    
    recent = [h['result'] for h in history[-6:]]
    if len(recent) < 4:
        return None
    
    # Kiểm tra pattern đảo cầu: LỚN NHỎ LỚN NHỎ hoặc NHỎ LỚN NHỎ LỚN
    if len(recent) >= 4:
        if recent[-4] != recent[-3] and recent[-3] != recent[-2] and recent[-2] != recent[-1]:
            return "LỚN" if recent[-1] == "NHỎ" else "NHỎ"
    
    # 3 phiên liên tiếp giống nhau
    if len(recent) >= 3:
        if recent[-1] == recent[-2] == recent[-3]:
            return "NHỎ" if recent[-1] == "LỚN" else "LỚN"
    
    return None

def predict_hotcold(history):
    """Thuật toán 6: Số nóng/lạnh (Hot/Cold Numbers)"""
    if len(history) < 10:
        return None
    
    # Lấy tất cả số từ 10 phiên gần nhất
    all_numbers = []
    for h in history[-15:]:
        all_numbers.extend(h.get('lucky_codes', []))
    
    if len(all_numbers) < 9:
        return None
    
    # Đếm tần suất từng số
    counts = Counter(all_numbers)
    
    # Tính tổng số nóng (xuất hiện nhiều) và số lạnh
    hot_sum = 0
    cold_sum = 0
    hot_count = 0
    cold_count = 0
    
    for num, count in counts.items():
        if count >= 3:
            hot_sum += num * count
            hot_count += count
        else:
            cold_sum += num * count
            cold_count += count
    
    if hot_count == 0 or cold_count == 0:
        return None
    
    avg_hot = hot_sum / hot_count
    avg_cold = cold_sum / cold_count
    
    return "LỚN" if avg_hot > avg_cold else "NHỎ"

def predict_neural(history):
    """Thuật toán 7: Mạng nơ-ron đơn giản (Neural Network)"""
    if len(history) < 10:
        return None
    
    # Lấy 10 kết quả gần nhất
    recent = [1 if h['result'] == "LỚN" else 0 for h in history[-10:]]
    
    # Trọng số theo thời gian (phiên càng gần càng quan trọng)
    weights = [0.25, 0.20, 0.16, 0.13, 0.10, 0.07, 0.05, 0.03, 0.01, 0.00]
    
    weighted_sum = 0
    for i, val in enumerate(recent):
        if i < len(weights):
            weighted_sum += val * weights[i]
    
    # Ngưỡng quyết định: 0.45
    if weighted_sum >= 0.48:
        return "LỚN"
    elif weighted_sum <= 0.38:
        return "NHỎ"
    
    # Nếu không rõ ràng, theo xu hướng
    return None

def predict_randomforest(history):
    """Thuật toán 8: Rừng ngẫu nhiên (Random Forest)"""
    if len(history) < 10:
        return None
    
    predictions = []
    
    # Lấy 7 mẫu ngẫu nhiên từ lịch sử
    for _ in range(7):
        if len(history) >= 3:
            start = random.randint(0, len(history) - 3)
            sample = history[start:start+3]
            big_count = sum(1 for h in sample if h['result'] == "LỚN")
            # Dự đoán dựa trên mẫu
            if big_count >= 2:
                predictions.append("NHỎ")  # Đảo cầu
            else:
                predictions.append("LỚN")
    
    if not predictions:
        return None
    
    # Bỏ phiếu
    big_votes = sum(1 for p in predictions if p == "LỚN")
    small_votes = len(predictions) - big_votes
    
    return "LỚN" if big_votes >= small_votes else "NHỎ"

# ================================================================
# 8️⃣ THUẬT TOÁN ENSEMBLE PRO
# ================================================================

def predict_ensemble_pro(history):
    """ENSEMBLE PRO - Tổng hợp 8 thuật toán với AI tự học"""
    if len(history) < MIN_SAMPLES:
        return {
            "prediction": "LỚN",
            "confidence": 50,
            "prob_lon": 50,
            "prob_nho": 50,
            "reason": f"📊 Chưa đủ dữ liệu (cần {MIN_SAMPLES} phiên)",
            "algo_used": []
        }
    
    # Danh sách thuật toán
    algos = [
        ("sequence", predict_sequence),
        ("trend", predict_trend),
        ("frequency", predict_frequency),
        ("markov", predict_markov),
        ("reversal", predict_reversal),
        ("hotcold", predict_hotcold),
        ("neural", predict_neural),
        ("randomforest", predict_randomforest)
    ]
    
    votes = []
    weights = []
    algo_used = []
    algo_details = []
    
    for name, func in algos:
        try:
            pred = func(history)
            if pred in ["LỚN", "NHỎ"]:
                weight = get_algo_weight(name)
                votes.append(pred)
                weights.append(weight)
                algo_used.append(name)
                algo_details.append({
                    "name": name,
                    "prediction": pred,
                    "weight": weight
                })
        except Exception as e:
            logger.warning(f"Algo {name} error: {e}")
            continue
    
    if not votes:
        return {
            "prediction": "LỚN",
            "confidence": 50,
            "prob_lon": 50,
            "prob_nho": 50,
            "reason": "⚠️ Không có dự đoán hợp lệ",
            "algo_used": []
        }
    
    # Tính tổng trọng số
    total_weight = sum(weights)
    weighted_votes = {"LỚN": 0, "NHỎ": 0}
    
    for v, w in zip(votes, weights):
        weighted_votes[v] += w
    
    prob_big = weighted_votes["LỚN"] / total_weight * 100
    prob_small = weighted_votes["NHỎ"] / total_weight * 100
    
    # Quyết định dự đoán
    prediction = "LỚN" if prob_big >= prob_small else "NHỎ"
    
    # Độ tin cậy dựa trên sự chênh lệch
    diff = abs(prob_big - prob_small)
    confidence = int(55 + diff * 0.45)
    confidence = min(95, max(55, confidence))
    
    # Lấy top 3 thuật toán tốt nhất
    best_algos = get_best_algos(3)
    best_text = ""
    for item in best_algos:
        best_text += f"  • {item['name']}: {item['weight']:.2f} ({item['win_rate']:.1f}%)\n"
    
    # Xây dựng lý do
    reason = f"📊 *ENSEMBLE PRO* - {len(votes)}/8 thuật toán:\n"
    reason += f"  {ICONS['red_circle']} LỚN: {weighted_votes['LỚN']:.1f} điểm ({prob_big:.1f}%)\n"
    reason += f"  {ICONS['blue_circle']} NHỎ: {weighted_votes['NHỎ']:.1f} điểm ({prob_small:.1f}%)\n"
    reason += f"  {ICONS['target']} Độ tin cậy: {confidence}%\n"
    reason += f"\n🧠 *Top AI đang học:*\n{best_text}"
    
    return {
        "prediction": prediction,
        "confidence": confidence,
        "prob_lon": round(prob_big, 1),
        "prob_nho": round(prob_small, 1),
        "reason": reason,
        "total_analyzed": len(history),
        "weighted_votes": weighted_votes,
        "algo_used": algo_used,
        "algo_details": algo_details,
        "total_weight": total_weight
    }

# ================================================================
# 9️⃣ QUẢN LÝ KEY (LICENSE)
# ================================================================

KEYS_FILE = "lotto_keys.json"
user_keys = {}

def load_keys():
    global user_keys
    try:
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                user_keys = json.load(f)
        else:
            user_keys = {}
            save_keys()
    except Exception as e:
        logger.error(f"load_keys error: {e}")
        user_keys = {}

def save_keys():
    try:
        with open(KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_keys, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save_keys error: {e}")

load_keys()

def generate_key(days: int) -> str:
    """Tạo key mới với thời hạn theo ngày"""
    raw = f"{USER_ID}:{datetime.now().isoformat()}:{random.randint(100000, 999999)}"
    key = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    
    expiry = (datetime.now() + timedelta(days=days)).isoformat()
    
    user_keys[key] = {
        "created": datetime.now().isoformat(),
        "expiry": expiry,
        "days": days,
        "used_by": [],
        "active": True
    }
    save_keys()
    return key

def verify_key(key: str, user_id: int) -> bool:
    """Kiểm tra key hợp lệ"""
    if key not in user_keys:
        return False
    
    data = user_keys[key]
    if not data.get("active", True):
        return False
    
    expiry = datetime.fromisoformat(data["expiry"])
    if datetime.now() > expiry:
        return False
    
    # Ghi nhận user đã dùng key
    if str(user_id) not in data["used_by"]:
        data["used_by"].append(str(user_id))
        save_keys()
    
    return True

def get_key_info(key: str) -> dict:
    """Lấy thông tin chi tiết của key"""
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
        "used_by": data["used_by"],
        "active": data.get("active", True),
        "used_count": len(data["used_by"])
    }

def deactivate_key(key: str) -> bool:
    """Vô hiệu hóa key"""
    if key in user_keys:
        user_keys[key]["active"] = False
        save_keys()
        return True
    return False

# ================================================================
# 🔟 TRẠNG THÁI AUTO BET
# ================================================================

STATE_FILE = "lotto_state.json"

auto_bet_running = False
auto_bet_thread = None
last_issue = None
prediction_history = []
stats = {"win": 0, "lose": 0, "total": 0, "streak": 0, "max_streak": 0}

def load_state():
    global auto_bet_running, last_issue, prediction_history, stats
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                auto_bet_running = data.get('auto_bet_running', False)
                last_issue = data.get('last_issue', None)
                prediction_history = data.get('prediction_history', [])
                stats = data.get('stats', {"win": 0, "lose": 0, "total": 0, "streak": 0, "max_streak": 0})
    except Exception as e:
        logger.error(f"load_state error: {e}")

def save_state():
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'auto_bet_running': auto_bet_running,
                'last_issue': last_issue,
                'prediction_history': prediction_history[-MAX_HISTORY:],
                'stats': stats
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save_state error: {e}")

load_state()

# ================================================================
# 1️⃣1️⃣ AUTO BET LOOP
# ================================================================

def auto_bet_loop(chat_id):
    global auto_bet_running, last_issue, prediction_history, stats
    
    logger.info(f"Auto bet loop started for chat {chat_id}")
    
    while auto_bet_running:
        try:
            # Lấy dữ liệu hiện tại
            home = get_home()
            if not home or home.get('code') != 0:
                time.sleep(3)
                continue
            
            data = home.get('data', {})
            current_issue = data.get('last_issue_id')
            current_result = data.get('last_issue_result')
            lucky_codes = data.get('last_issue_lucky_code', [])
            balance = data.get('balance', 0)
            
            # ===== KIỂM TRA KẾT QUẢ PHIÊN CŨ =====
            if prediction_history:
                last_pred = prediction_history[-1]
                # Chỉ xử lý khi phiên hiện tại đã qua phiên dự đoán
                if last_pred.get('actual') is None and current_issue is not None and current_issue > last_pred['issue']:
                    actual = "LỚN" if current_result == "TAI" else "NHỎ"
                    last_pred['actual'] = actual
                    is_correct = (last_pred['prediction'] == actual)
                    last_pred['result'] = "✅ ĐÚNG" if is_correct else "❌ SAI"
                    
                    # Cập nhật thống kê
                    if is_correct:
                        stats['win'] += 1
                        stats['streak'] = stats['streak'] + 1 if stats['streak'] >= 0 else 1
                    else:
                        stats['lose'] += 1
                        stats['streak'] = stats['streak'] - 1 if stats['streak'] <= 0 else -1
                    
                    if abs(stats['streak']) > stats['max_streak']:
                        stats['max_streak'] = abs(stats['streak'])
                    
                    stats['total'] += 1
                    
                    # Cập nhật AI tự học
                    algo_used = last_pred.get('algo_used', [])
                    if algo_used and isinstance(algo_used, list):
                        for algo in algo_used:
                            update_learning(last_pred['prediction'], actual, algo)
                    elif algo_used:
                        update_learning(last_pred['prediction'], actual, algo_used)
                    
                    # Xây dựng thông báo kết quả
                    icon = "✅" if is_correct else "❌"
                    color = "#39ff14" if is_correct else "#ff0055"
                    
                    streak_text = ""
                    if stats['streak'] > 0:
                        streak_text = f"🔥 *Đang thắng {stats['streak']} phiên liên tiếp!*"
                    elif stats['streak'] < 0:
                        streak_text = f"💀 *Đang thua {abs(stats['streak'])} phiên liên tiếp!*"
                    
                    # Lấy top AI
                    best = get_best_algos(2)
                    best_text = ""
                    for item in best:
                        best_text += f"  • {item['name']}: {item['weight']:.2f} ({item['win_rate']:.1f}%)\n"
                    
                    balance_text = f"💰 Số dư: {balance:,.2f} BUILD" if balance else ""
                    
                    result_msg = f"""
{icon} *KẾT QUẢ PHIÊN #{last_pred['issue']}*
━━━━━━━━━━━━━━━━━━━
🎯 Dự đoán: *{last_pred['prediction']}*
📊 Thực tế: *{actual}*
🔢 Bộ số: {' '.join(map(str, lucky_codes)) if lucky_codes else '---'}

📈 *Thống kê:*
• ✅ Đúng: {stats['win']}
• ❌ Sai: {stats['lose']}
• 🎯 Tỷ lệ: {stats['win']/stats['total']*100:.1f}% ({stats['total']} phiên)
{streak_text}

🧠 *AI tự học:*
{best_text}
{balance_text}
━━━━━━━━━━━━━━━━━━━
"""
                    bot.send_message(chat_id, result_msg, parse_mode='Markdown')
                    save_state()
            
            # ===== DỰ ĐOÁN PHIÊN TIẾP THEO =====
            if current_issue is not None and current_issue != last_issue:
                last_issue = current_issue
                next_issue = current_issue + 1
                
                # Lấy lịch sử và parse
                history_data = get_history()
                history = parse_history(history_data)
                
                # Dự đoán
                pred = predict_ensemble_pro(history)
                prediction = pred['prediction']
                
                # Lưu lịch sử dự đoán
                prediction_history.append({
                    'issue': next_issue,
                    'prediction': prediction,
                    'confidence': pred['confidence'],
                    'actual': None,
                    'result': None,
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'algo_used': pred.get('algo_used', [])
                })
                
                if len(prediction_history) > MAX_HISTORY:
                    prediction_history = prediction_history[-MAX_HISTORY:]
                
                # Gửi thông báo dự đoán
                balance = get_balance()
                balance_text = f"💰 Số dư: {balance:,.2f} BUILD" if balance else ""
                
                predict_msg = f"""
🔮 *DỰ ĐOÁN PHIÊN #{next_issue}* (Sắp tới)
━━━━━━━━━━━━━━━━━━━
🎯 *Dự đoán:* **{prediction}**
📊 *Độ tin cậy:* {pred['confidence']}%
📈 *LỚN:* {pred['prob_lon']}% | *NHỎ:* {pred['prob_nho']}%

{pred['reason']}
{balance_text}
━━━━━━━━━━━━━━━━━━━
⏳ Đang chờ kết quả...
"""
                bot.send_message(chat_id, predict_msg, parse_mode='Markdown')
                save_state()
            
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Auto bet loop error: {e}")
            time.sleep(5)
    
    logger.info(f"Auto bet loop stopped for chat {chat_id}")

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

# ================================================================
# 1️⃣2️⃣ MENU & GIAO DIỆN
# ================================================================

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
        types.InlineKeyboardButton("🧠 AI Stats", callback_data='ai_stats'),
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
        types.InlineKeyboardButton("📊 AI Stats", callback_data='ai_stats'),
        types.InlineKeyboardButton("🔄 Reset AI", callback_data='reset_ai'),
    )
    return keyboard

# ================================================================
# 1️⃣3️⃣ BOT COMMANDS
# ================================================================

@bot.message_handler(commands=['start'])
def send_start(message):
    user_id = message.chat.id
    
    # Kiểm tra admin
    if user_id in ADMIN_IDS:
        best = get_best_algos(2)
        best_text = ""
        for item in best:
            best_text += f"  • {item['name']}: {item['weight']:.2f} ({item['win_rate']:.1f}%)\n"
        
        balance = get_balance()
        balance_text = f"💰 Số dư: {balance:,.2f} BUILD" if balance else ""
        
        bot.reply_to(message, f"""
{ICONS['crown']} *LOTTO PREDICT BOT - ADMIN* {ICONS['crown']}
━━━━━━━━━━━━━━━━━━━
🤖 ENSEMBLE PRO + AI TỰ HỌC
👤 Tài khoản: `{USER_ID}`

📊 *Thống kê:*
✅ Đúng: {stats['win']}
❌ Sai: {stats['lose']}
🎯 Tỷ lệ: {stats['win']/(stats['total'] or 1)*100:.1f}%
🔥 Streak: {stats['streak']}

🧠 *AI đang học:*
{best_text}
{balance_text}
━━━━━━━━━━━━━━━━━━━
📌 Bấm nút bên dưới để bắt đầu!
""", reply_markup=main_menu(), parse_mode='Markdown')
        return
    
    # User thường - yêu cầu nhập key
    bot.reply_to(message, f"""
{ICONS['lock']} *LOTTO PREDICT BOT* {ICONS['lock']}
━━━━━━━━━━━━━━━━━━━
🤖 ENSEMBLE PRO + AI TỰ HỌC
🎯 Dự đoán LỚN/NHỎ với độ chính xác cao

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
        bot.reply_to(message, "❌ Nhập: `/key <MÃ_KEY>`", parse_mode='Markdown')
        return
    
    key = parts[1].strip().upper()
    
    if verify_key(key, user_id):
        info = get_key_info(key)
        bot.reply_to(message, f"""
{ICONS['check']} *KÍCH HOẠT THÀNH CÔNG!* {ICONS['check']}
━━━━━━━━━━━━━━━━━━━
🔑 Key: `{key}`
⏳ Hạn: {info['remaining']} ngày
📅 Hết hạn: {info['expiry'][:10]}
👥 Đã dùng: {info['used_count']} user
━━━━━━━━━━━━━━━━━━━
📌 Bấm `/start` để bắt đầu dùng!
""", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"""
{ICONS['cross']} *KEY KHÔNG HỢP LỆ* {ICONS['cross']}
━━━━━━━━━━━━━━━━━━━
🔑 Key `{key}` không tồn tại hoặc đã hết hạn!

📌 Vui lòng kiểm tra lại hoặc liên hệ admin để mua key mới.
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown')

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, f"""
{ICONS['cross']} *KHÔNG CÓ QUYỀN* {ICONS['cross']}
━━━━━━━━━━━━━━━━━━━
⚠️ Bạn không có quyền truy cập Admin Panel!
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown')
        return
    
    learning_stats = get_learning_stats()
    
    bot.reply_to(message, f"""
{ICONS['crown']} *ADMIN PANEL* {ICONS['crown']}
━━━━━━━━━━━━━━━━━━━
📊 *Key đã tạo:* {len(user_keys)}
👥 *Người dùng:* {sum(len(data['used_by']) for data in user_keys.values())}
🧠 *Số phiên học:* {learning_stats['total']}
🎯 *Tỷ lệ AI:* {learning_stats['rate']:.1f}%
━━━━━━━━━━━━━━━━━━━
📌 Chọn chức năng bên dưới!
""", reply_markup=admin_menu(), parse_mode='Markdown')

# ================================================================
# 1️⃣4️⃣ CALLBACK HANDLER
# ================================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    data = call.data
    bot.answer_callback_query(call.id)
    
    # Xử lý các callback
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
    elif data == 'ai_stats':
        show_ai_stats(call.message)
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
    elif data == 'reset_ai':
        reset_ai(call.message)

# ================================================================
# 1️⃣5️⃣ ADMIN FUNCTIONS
# ================================================================

def create_key(message, days):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Không có quyền!")
        return
    
    key = generate_key(days)
    info = get_key_info(key)
    
    bot.reply_to(message, f"""
{ICONS['check']} *KEY ĐÃ TẠO* {ICONS['check']}
━━━━━━━━━━━━━━━━━━━
🔑 Key: `{key}`
📅 Hạn: {days} ngày
⏳ Hết hạn: {info['expiry'][:10]}
━━━━━━━━━━━━━━━━━━━
📌 Gửi key này cho user!
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
        status = "🟢" if remaining > 0 and v.get("active", True) else "🔴"
        text += f"{status} `{k}` | {v['days']} ngày | còn {remaining} ngày | {len(v['used_by'])} user\n"
    
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=admin_menu())

def check_key_input(message):
    key = message.text.strip().upper()
    info = get_key_info(key)
    
    if info:
        remaining = info['remaining']
        status = "🟢 Còn hiệu lực" if remaining > 0 and info['active'] else "🔴 Hết hạn"
        bot.reply_to(message, f"""
🔍 *THÔNG TIN KEY*
━━━━━━━━━━━━━━━━━━━
🔑 Key: `{key}`
📅 Hạn: {info['days']} ngày
⏳ Còn: {remaining} ngày
👥 Đã dùng: {info['used_count']} user
📊 Trạng thái: {status}
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=admin_menu())
    else:
        bot.reply_to(message, "❌ Key không tồn tại!", reply_markup=admin_menu())

def reset_ai(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Không có quyền!")
        return
    
    # Reset learning data
    global learning_data
    learning_data = {
        "algo_weights": {},
        "history": [],
        "performance": {},
        "total_predictions": 0,
        "total_correct": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    init_algo_weights()
    save_learning_data()
    
    bot.reply_to(message, f"""
{ICONS['check']} *ĐÃ RESET AI* {ICONS['check']}
━━━━━━━━━━━━━━━━━━━
🧠 AI đã được reset về trạng thái ban đầu!
📊 Tất cả dữ liệu học đã được xóa.
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=admin_menu())

# ================================================================
# 1️⃣6️⃣ USER FUNCTIONS
# ================================================================

def show_predict(message):
    msg = bot.reply_to(message, f"""
{ICONS['clock']} *Đang phân tích với ENSEMBLE PRO...*
━━━━━━━━━━━━━━━━━━━
⏳ Đang tải dữ liệu và phân tích...
""", parse_mode='Markdown')
    
    try:
        history_data = get_history()
        if not history_data:
            bot.edit_message_text(f"""
{ICONS['warning']} *KHÔNG LẤY ĐƯỢC DỮ LIỆU* {ICONS['warning']}
━━━━━━━━━━━━━━━━━━━
⚠️ Không thể lấy lịch sử từ server!
📌 Kiểm tra lại kết nối hoặc tài khoản.
━━━━━━━━━━━━━━━━━━━
""", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='Markdown', reply_markup=main_menu())
            return
        
        history = parse_history(history_data)
        pred = predict_ensemble_pro(history)
        
        home = get_home()
        current_issue = home.get('data', {}).get('last_issue_id', '---')
        current_result = home.get('data', {}).get('last_issue_result', '---')
        lucky_codes = home.get('data', {}).get('last_issue_lucky_code', [])
        next_issue = current_issue + 1 if current_issue != '---' else '---'
        
        balance = get_balance()
        balance_text = f"💰 Số dư: {balance:,.2f} BUILD" if balance else ""
        
        result_text = f"""
🔮 *DỰ ĐOÁN PHIÊN #{next_issue}* (Sắp tới)
━━━━━━━━━━━━━━━━━━━
🎯 *Dự đoán:* **{pred['prediction']}**
📊 *Độ tin cậy:* {pred['confidence']}%
📈 *LỚN:* {pred['prob_lon']}% | *NHỎ:* {pred['prob_nho']}%

{pred['reason']}
{balance_text}
━━━━━━━━━━━━━━━━━━━
⏳ Đang chờ kết quả...
"""
        bot.edit_message_text(result_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='Markdown', reply_markup=main_menu())
        
    except Exception as e:
        bot.edit_message_text(f"""
{ICONS['cross']} *LỖI* {ICONS['cross']}
━━━━━━━━━━━━━━━━━━━
❌ {str(e)[:100]}
━━━━━━━━━━━━━━━━━━━
""", chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='Markdown', reply_markup=main_menu())

def show_history(message):
    if not prediction_history:
        bot.reply_to(message, f"""
📭 *CHƯA CÓ LỊCH SỬ*
━━━━━━━━━━━━━━━━━━━
⏳ Chưa có dự đoán nào được thực hiện!
📌 Bắt đầu auto hoặc dự đoán thủ công để có dữ liệu.
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=main_menu())
        return
    
    recent = prediction_history[-15:][::-1]
    text = f"📜 *LỊCH SỬ DỰ ĐOÁN* (15 phiên gần nhất)\n━━━━━━━━━━━━━━━━━━━\n"
    
    for h in recent:
        issue = h.get('issue', '---')
        pred = h.get('prediction', '---')
        actual = h.get('actual', '⏳')
        result = h.get('result', '⏳')
        conf = h.get('confidence', 0)
        time_str = h.get('time', '')
        icon = "✅" if "ĐÚNG" in str(result) else "❌" if "SAI" in str(result) else "⏳"
        text += f"{icon} #{issue}: {pred} → {actual} ({conf}%) {time_str}\n"
    
    text += f"\n📊 *Tổng:* ✅ {stats['win']} | ❌ {stats['lose']} | 🎯 {stats['win']/(stats['total'] or 1)*100:.1f}%"
    
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=main_menu())

def show_stats(message):
    total = stats['total']
    win = stats['win']
    lose = stats['lose']
    rate = win/(total or 1)*100
    streak = stats.get('streak', 0)
    max_streak = stats.get('max_streak', 0)
    
    streak_text = f"🔥 {streak}" if streak > 0 else f"💀 {abs(streak)}" if streak < 0 else "➖ 0"
    
    text = f"""
📊 *THỐNG KÊ DỰ ĐOÁN* 📊
━━━━━━━━━━━━━━━━━━━
📌 Tổng phiên: {total}
✅ Đúng: {win}
❌ Sai: {lose}
🎯 Tỷ lệ: {rate:.1f}%
📈 Streak: {streak_text}
🏆 Max Streak: {max_streak}
━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=main_menu())

def show_ai_stats(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Chỉ admin mới xem được!", reply_markup=main_menu())
        return
    
    learning_stats = get_learning_stats()
    
    text = f"🧠 *AI TỰ HỌC - THỐNG KÊ*\n━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Tổng phiên học: {learning_stats['total']}\n"
    text += f"✅ Đúng: {learning_stats['correct']}\n"
    text += f"❌ Sai: {learning_stats['wrong']}\n"
    text += f"🎯 Tỷ lệ: {learning_stats['rate']:.1f}%\n"
    text += f"📝 Lịch sử: {learning_stats['history_count']} bản ghi\n\n"
    
    text += "📊 *Hiệu suất từng thuật toán:*\n"
    for i, name in enumerate(ALGO_KEYS):
        display_name = ALGO_NAMES[i]
        perf = get_algo_performance(name)
        weight = get_algo_weight(name)
        total = perf["total"]
        rate = perf["win"]/total*100 if total > 0 else 0
        text += f"  • {display_name}: {rate:.1f}% ({perf['win']}/{total}) - Trọng số: {weight:.2f}\n"
    
    bot.reply_to(message, text, parse_mode='Markdown', reply_markup=admin_menu())

def toggle_auto(message):
    chat_id = message.chat.id
    
    if auto_bet_running:
        stop_auto_bet()
        bot.reply_to(message, f"""
⏹ *ĐÃ DỪNG AUTO PREDICT*
━━━━━━━━━━━━━━━━━━━
🛑 Bot đã dừng tự động dự đoán.
📌 Bấm "▶️ Bắt đầu" để chạy lại.
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=main_menu())
    else:
        start_auto_bet(chat_id)
        bot.reply_to(message, f"""
▶️ *ĐÃ BẮT ĐẦU AUTO PREDICT*
━━━━━━━━━━━━━━━━━━━
🤖 Bot sẽ tự động dự đoán mỗi phiên mới.
⏳ Đang theo dõi và chờ phiên tiếp theo...
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=main_menu())

def clear_history(message):
    global prediction_history, stats
    prediction_history = []
    stats = {"win": 0, "lose": 0, "total": 0, "streak": 0, "max_streak": 0}
    save_state()
    bot.reply_to(message, f"""
🗑️ *ĐÃ XÓA LỊCH SỬ*
━━━━━━━━━━━━━━━━━━━
✅ Toàn bộ lịch sử dự đoán đã được xóa!
📊 Thống kê đã được reset về 0.
━━━━━━━━━━━━━━━━━━━
""", parse_mode='Markdown', reply_markup=main_menu())

# ================================================================
# 1️⃣7️⃣ WEBHOOK ROUTES
# ================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return """
✅ Webhook is working! 
Send POST from Telegram.
"""
    
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
    return """
🤖 Lotto Predict Bot is running!

📊 Version: 2.0
🧠 AI: Ensemble PRO + Reinforcement Learning
👑 Admin: TBTOOL
"""
@app.route('/health', methods=['GET'])
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ================================================================
# 1️⃣8️⃣ MAIN
# ================================================================

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║  ████████╗██████╗ ████████╗ ██████╗  ██████╗ ██╗      ██╗║
║  ╚══██╔══╝██╔══██╗╚══██╔══╝██╔═══██╗██╔═══██╗██║      ██║║
║     ██║   ██████╔╝   ██║   ██║   ██║██║   ██║██║      ██║║
║     ██║   ██╔══██╗   ██║   ██║   ██║██║   ██║██║      ╚██╗║
║     ██║   ██████╔╝   ██║   ╚██████╔╝╚██████╔╝███████╗ ╚████║
║     ╚═╝   ╚═════╝    ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝  ╚═══╝║
║                                                              ║
║           LOTTO PREDICT BOT - TBTOOL v2.0                   ║
║        ENSEMBLE PRO + AI TỰ HỌC (Reinforcement Learning)    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"🚀 Bot đang chạy trên port {PORT}")
    print(f"👤 Clone ID: {USER_ID}")
    print(f"🔗 Webhook URL: {WEBHOOK_URL}")
    print(f"🧠 AI Learning: {'Enabled' if os.path.exists(LEARNING_FILE) else 'New'}")
    print(f"📊 Admin IDs: {ADMIN_IDS}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "="*60)
    print("✅ Bot sẵn sàng nhận lệnh!")
    print("📌 Gửi /start trên Telegram để bắt đầu")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=PORT)
