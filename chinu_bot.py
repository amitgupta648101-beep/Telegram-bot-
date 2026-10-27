# chinu_bot.py — CHINU MODS · Fast 5000 Devices + 5000 IPs Rotation
import hmac, hashlib, requests, string, random, json, codecs, time, os, sys, base64, asyncio
import threading, re, logging, urllib.request, queue
from datetime import datetime, timezone
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import urllib3
from requests.adapters import HTTPAdapter

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8463813853:AAGS_D79bkftC4zyavL2HKhAIcoJ6shJi2c").strip()
if not BOT_TOKEN:
    print("ERROR: set TELEGRAM_BOT_TOKEN environment variable"); sys.exit(1)

# ============================================================
# BRAND & CONFIG
# ============================================================
BOT_NAME        = "GUEST GEN"
BOT_TAGLINE     = "Guest Generator"
BOT_VERSION     = "v2.5"
DEFAULT_PREFIX  = "CHINNU"

REFERRAL_COINS = 10  
CUSTOM_CHANNEL_LINK = "https://t.me/the_of_father"

ADMIN_ID = int(os.environ.get("ADMIN_ID", "8391469325")) 

def is_admin(chat_id):
    return ADMIN_ID != 0 and int(chat_id) == ADMIN_ID

# ============================================================
# EMOJI VARIABLES DEFINITION (FIX FOR NameError)
# ============================================================
E_TIME   = "⏳"
E_GEM    = "💎"
E_ZAP    = "⚡"
E_TARGET = "🎯"
E_USER   = "👤"
E_LINK   = "🔗"
E_COIN   = "🪙"
E_CROSS  = "❌"
E_CHECK  = "✅"
E_ROCKET = "🚀"
E_STOP   = "🛑"
E_INFO   = "ℹ️"
E_GLOBE  = "🌍"
E_SPEAK  = "🗣"
E_TROPHY = "🏆"
E_TICKET = "🎟"
E_BOT    = "🤖"
E_FOLDER = "📁"


# ============================================================
# SAFE MESSAGE WRAPPERS (STRICT ERROR HANDLING)
# ============================================================
async def safe_send(chat_or_msg, text, **kwargs):
    try:
        if hasattr(chat_or_msg, 'send_message'):
            return await chat_or_msg.send_message(text, **kwargs)
        elif hasattr(chat_or_msg, 'reply_text'):
            return await chat_or_msg.reply_text(text, **kwargs)
    except telegram.error.BadRequest as e:
        clean_text = re.sub(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', r'\1', text)
        kwargs['parse_mode'] = ParseMode.HTML
        if hasattr(chat_or_msg, 'send_message'):
            return await chat_or_msg.send_message(clean_text, **kwargs)
        elif hasattr(chat_or_msg, 'reply_text'):
            return await chat_or_msg.reply_text(clean_text, **kwargs)

async def safe_edit(obj, text, **kwargs):
    try:
        if hasattr(obj, 'edit_message_text'):
            return await obj.edit_message_text(text, **kwargs)
        elif hasattr(obj, 'edit_text'):
            return await obj.edit_text(text, **kwargs)
    except telegram.error.BadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        clean_text = re.sub(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', r'\1', text)
        kwargs['parse_mode'] = ParseMode.HTML
        if hasattr(obj, 'edit_message_text'):
            return await obj.edit_message_text(clean_text, **kwargs)
        elif hasattr(obj, 'edit_text'):
            return await obj.edit_text(clean_text, **kwargs)

# ============================================================
# AUTO-REFILL PROXY QUEUE
# ============================================================
class ProxyQueue:
    def __init__(self):
        self.queue = queue.Queue()
        self._lock = threading.Lock()
        self._is_fetching = False
        self.fetch_proxies()

    def fetch_proxies(self):
        with self._lock:
            if self._is_fetching: return
            self._is_fetching = True
        
        urls = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
        ]
        proxies = set()
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    for line in response.read().decode().splitlines():
                        line = line.strip()
                        if ":" in line and not line.startswith("#"):
                            proxies.add(f"http://{line}")
            except Exception:
                pass
        
        proxies = list(proxies)
        random.shuffle(proxies)
        for p in proxies:
            self.queue.put(p)
            
        with self._lock:
            self._is_fetching = False

    def get_ip(self):
        if self.queue.qsize() < 100:
            threading.Thread(target=self.fetch_proxies, daemon=True).start()
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None

PROXY_QUEUE = ProxyQueue()

# ============================================================
# CONFIG & CRYPTO
# ============================================================
class Config:
    AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th","BD":"bn",
                   "PK":"ur","TW":"zh","CIS":"ru","SAC":"es","BR":"pt"}

REGION_LANG = Config.REGION_LANG
HEX_KEY = bytes.fromhex(
    "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
)

HTTP_TIMEOUT    = 4   
HTTP_RETRIES    = 0   
STALL_TIMEOUT   = 300  
MAX_WORKERS     = 3000
DEVICE_POOL_SIZE    = 5000  
DEFAULT_THRESHOLD   = 6
DEVICE_COOLDOWN_SEC = 45

API_SEMAPHORE = threading.Semaphore(150) 

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
BASE_FOLDER = os.path.join(BASE_DIR, "CHINU-MODS")
os.makedirs(BASE_FOLDER, exist_ok=True)

# ============================================================
# USER & REDEEM DATABASE
# ============================================================
USERS_FILE = os.path.join(BASE_FOLDER, "users.json")
REDEEM_FILE = os.path.join(BASE_FOLDER, "redeem_codes.json")

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)
    except Exception:
        pass

def get_user(chat_id, first_name="User"):
    users = load_users()
    cid = str(chat_id)
    if cid not in users:
        users[cid] = {
            "name": first_name,
            "coins": 0,
            "referrals": 0,
            "generated": 0,
            "referred_by": None
        }
        save_users(users)
    return users[cid]

def load_codes():
    if os.path.exists(REDEEM_FILE):
        try:
            with open(REDEEM_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_codes(codes):
    try:
        with open(REDEEM_FILE, "w", encoding="utf-8") as f:
            json.dump(codes, f, indent=2)
    except Exception:
        pass

# ============================================================
# HTTP & 5000 DEVICE POOL
# ============================================================
class WAFBypass:
    _uas = [
        "GarenaMSDK/4.0.42(SM-A525F ;Android)",
        "GarenaMSDK/4.0.39(SM-A325M;Android 13;en;HK;)",
        "GarenaMSDK/4.0.38(Redmi Note 10;Android 12;en;ID;)",
        "GarenaMSDK/4.0.40(Poco X3;Android 11;en;SG;)",
        "GarenaMSDK/4.0.41(SM-S918B;Android 14;en;IN;)",
        "GarenaMSDK/4.0.42(OnePlus 11;Android 13;en;US;)",
        "GarenaMSDK/4.0.39(Xiaomi 13 Pro;Android 13;pt;BR;)",
        "GarenaMSDK/4.0.40(Pixel 7 Pro;Android 14;en;US;)",
        "GarenaMSDK/4.0.42(Infinix X6819;Android 13;en;PK;)",
        "GarenaMSDK/4.0.41(vivo 1906;Android 11;en;BD;)",
    ]
    @staticmethod
    def get_ua(): return random.choice(WAFBypass._uas)

class DevicePool:
    _devices, _index, _lock = [], 0, threading.Lock()
    _cooldown_until = {}
    _hits = {}

    DEVICE_MODELS = [
        ("Asus ASUS_I005DA","ARMv7 VFPv3 NEON VMH | 2400 | 2","Adreno (TM) 640"),
        ("SM-A525F","ARMv8 VFPv4 NEON VMH | 2200 | 8","Adreno (TM) 618"),
        ("SM-A325M","ARMv8 VFPv4 NEON VMH | 2000 | 8","Mali-G52"),
        ("SM-S918B","ARMv8 VFPv4 NEON VMH | 3200 | 8","Adreno (TM) 740"),
        ("Redmi Note 10","ARMv8 VFPv4 NEON VMH | 2200 | 8","Adreno (TM) 619"),
        ("Redmi Note 11","ARMv8 VFPv4 NEON VMH | 2400 | 8","Adreno (TM) 610"),
        ("Poco X3","ARMv8 VFPv4 NEON VMH | 2300 | 8","Adreno (TM) 618"),
        ("Poco M4 Pro","ARMv8 VFPv4 NEON VMH | 2200 | 8","Mali-G57"),
        ("Pixel 6","ARMv8 VFPv4 NEON VMH | 2800 | 8","Mali-G78"),
        ("Pixel 7 Pro","ARMv8 VFPv4 NEON VMH | 2800 | 8","Mali-G710"),
        ("OnePlus 9","ARMv8 VFPv4 NEON VMH | 2800 | 8","Adreno (TM) 660"),
        ("OnePlus 11","ARMv8 VFPv4 NEON VMH | 3200 | 8","Adreno (TM) 740"),
        ("Xiaomi 13 Pro","ARMv8 VFPv4 NEON VMH | 3200 | 8","Adreno (TM) 740"),
        ("Infinix X6819","ARMv8 VFPv4 NEON VMH | 2400 | 8","Mali-G57"),
        ("vivo 1906","ARMv8 VFPv4 NEON VMH | 2000 | 8","Adreno (TM) 610"),
        ("OPPO CPH2211","ARMv8 VFPv4 NEON VMH | 2200 | 8","Adreno (TM) 619"),
        ("realme RMX3363","ARMv8 VFPv4 NEON VMH | 2400 | 8","Adreno (TM) 642"),
        ("TECNO KI5","ARMv8 VFPv4 NEON VMH | 2000 | 8","Mali-G52"),
    ]
    ANDROID_VERSIONS = [
        ("Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)","9","28"),
        ("Android OS 10 / API-29 (QKQ1.200114.002)","10","29"),
        ("Android OS 11 / API-30 (RP1A.201005.001)","11","30"),
        ("Android OS 12 / API-31 (SP1A.210812.016)","12","31"),
        ("Android OS 12L / API-32 (SP2A.220505.002)","12","32"),
        ("Android OS 13 / API-33 (TQ3A.230805.001)","13","33"),
        ("Android OS 14 / API-34 (UP1A.231005.007)","14","34"),
    ]
    NETWORKS  = ["WIFI","4G","5G"]
    OPERATORS = ["ATM Mobils","Telkomsel","Indosat","XL Axiata","Airtel","Jio","Vodafone",
                 "Globe","Smart","Viettel","Mobifone","Claro","Vivo"]
    SDK_VER   = ["4.0.38","4.0.39","4.0.40","4.0.41","4.0.42"]

    @classmethod
    def _rh(cls, n): return ''.join(random.choices("0123456789abcdef", k=n))
    @classmethod
    def _uuid(cls): return f"{cls._rh(8)}-{cls._rh(4)}-{cls._rh(4)}-{cls._rh(4)}-{cls._rh(12)}"
    @classmethod
    def _mac(cls):  return "02:" + ":".join(cls._rh(2) for _ in range(5))

    @classmethod
    def init_pool(cls, count=DEVICE_POOL_SIZE):
        if cls._devices: return
        for _ in range(count):
            model, cpu, gpu = random.choice(cls.DEVICE_MODELS)
            android_full, android_ver, api = random.choice(cls.ANDROID_VERSIONS)
            cls._devices.append({
                "model": model, "brand": model.split()[0], "cpu": cpu, "gpu": gpu,
                "android_full": android_full, "android_version": android_ver, "api_level": api,
                "operator": random.choice(cls.OPERATORS), "network": random.choice(cls.NETWORKS),
                "sdk": random.choice(cls.SDK_VER), "mac": cls._mac(),
                "device_id": cls._rh(32), "android_id": cls._rh(16), "uuid": cls._uuid(),
                "imei": cls._rh(15), "fingerprint": cls._rh(40), "gl_renderer": "OpenGL ES 3.2",
                "lang_code": random.choice(["en","in","ar","hi","vi","th","pt","ru","es","bn","ur","zh"]),
            })

    @classmethod
    def get(cls):
        now = time.time()
        with cls._lock:
            n = len(cls._devices)
            for _ in range(n):
                dev = cls._devices[cls._index % n]
                cls._index += 1
                if cls._cooldown_until.get(dev["device_id"], 0) <= now:
                    cls._hits[dev["device_id"]] = cls._hits.get(dev["device_id"], 0) + 1
                    return dev
            dev = cls._devices[cls._index % n]
            cls._index += 1
            return dev

    @classmethod
    def cool(cls, device_id, seconds=DEVICE_COOLDOWN_SEC):
        with cls._lock:
            cls._cooldown_until[device_id] = time.time() + seconds

    @classmethod
    def headers(cls, device=None):
        d = device or cls.get()
        return {
            "X-Device-Id": d["device_id"], "X-Android-Id": d["android_id"],
            "X-Device-Model": d["model"],  "X-Device-Brand": d["brand"],
            "X-OS-Version": d["android_version"], "X-API-Level": d["api_level"],
            "X-SDK-Version": d["sdk"], "X-Network-Type": d["network"],
            "X-Operator": d["operator"], "X-IMEI": d["imei"],
            "X-Mac": d["mac"], "X-Client-Uuid": d["uuid"],
        }

DevicePool.init_pool(DEVICE_POOL_SIZE)

# ============================================================
# ENCODING / PROTO
# ============================================================
def encode_f14(s):
    ks = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
          0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    return bytes(ord(c) ^ ks[i % len(ks)] for i, c in enumerate(s))

FIELD_22 = bytes.fromhex(
    "4747524501010100620200001052aa0d669c6a368f08338060d2ee0690053af84a41edcd3558556ec10f24f4"
    "6c93ac64ca41a16732c46a2cb071246a79b8929032f9e1b6f4ef331bd53cabf29b09b97349a46e9863c0314e"
    "1a0d80819fef8aabf03876b3d037db354a7ccb5c1bce96411fb3753f6f50e44c69c4ed617fa30efb8ffc0517"
    "ff2f636739be1f304d999cfd6fd48bf69454199794c3dc88f55a4bdbd66534d5a061359cdfd1fb680cd37918"
    "df9fdb3cf7d80067b0a3506c90063cf62b2ccec11e23913a2fd7c4ef091331967bb518a5ad1e551146b90821"
    "be800883abadde39d6c80a5d798611466c748f075481806c5842ce45e6bd4e3368ec08fe2ec41ceb880cd862"
    "49eb71693f79f0bccf9e590c3fae12519fe08c7a1905d0927690109e0df28574bb14847225db1a59230e6662"
    "ed7730e15ff9a6c815cb41b420edeada735a4b03e181037c37c2c850257311df2f07b0a56e759372cbd0268e"
    "3f13a292ee4373e38ab5096e0342a5e0d7fec6da2bbc265d74baadd2b24ee4f74862f82c21d6694bac53f8ce"
    "80312a30068a6276a641c19b11d0305c6fe2f531ac7de578b29f543697f5c73663e6f23aa15277b6122dcd4d"
    "4171e38f9ac0b173f39c58416a16c5c1f4a35acd065ce78f449cf538a249339e763272d458e4ed86c976591a"
    "9c066b3a37111e44091eb6b5a795249f3e5145db022a6055f2cc675936391312f688f89627845df222a91156"
    "555225be36f9714a0ba50246d0f003bda3c9c1292ab73b4f79635ddd023218eda93a302d79e023404c143965"
    "44a930b98ed54771aca7fec10d095587685b473e81a9619764fad9256529dcd6e911f4f4629612287d4ee3ec"
    "5389f6ec4ec020b0e2aac017232a9197be9e46239ce690fe5d4872b2e98e651510c971667f3aca8b59f3e9d5"
    "0e43"
)

def encode_varint(n):
    if n < 0: return b''
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict):
            nested = build_proto(v)
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(nested)) + nested)
        elif isinstance(v, int):
            parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)

def aes_encrypt(hex_data):
    return AES.new(Config.AES_KEY, AES.MODE_CBC, Config.AES_IV).encrypt(pad(bytes.fromhex(hex_data), AES.block_size))

def encrypt_api(plain_hex):
    return AES.new(Config.AES_KEY, AES.MODE_CBC, Config.AES_IV).encrypt(pad(bytes.fromhex(plain_hex), AES.block_size)).hex()

def _login_host(region: str) -> str:
    return ("loginbp.common.ggbluefox.com"
            if region.upper() in ("ME", "TH")
            else "loginbp.ppmainecoonghj.com")

def _merge_headers(headers, device=None):
    base = dict(headers or {})
    dev = device or DevicePool.get()
    for k, v in DevicePool.headers(dev).items():
        base.setdefault(k, v)
    return base

def request_retry(method, url, tag="HTTP", proxy=None, **kwargs):
    original_headers = kwargs.pop("headers", None)
    try:
        sess = requests.Session()
        call_kwargs = {k: v for k, v in kwargs.items()}
        call_kwargs["headers"] = _merge_headers(original_headers)
        call_kwargs["timeout"] = HTTP_TIMEOUT
        call_kwargs["verify"]  = False
        
        if proxy:
            call_kwargs["proxies"] = {"http": proxy, "https": proxy}
            
        resp = sess.request(method, url, **call_kwargs)
        if resp.status_code in (429, 500, 502, 503, 504, 408, 403):
            return None
        return resp
    except Exception:
        return None

# ============================================================
# RARITY
# ============================================================
_PATTERNS_RAW = {
    "R4": [r"(\d)\1{3,}", 3], "R3": [r"(\d)\1\1(\d)\2\2", 2],
    "S5": [r"(12345|23456|34567|45678|56789)", 4],
    "S4": [r"(0123|1234|2345|3456|4567|5678|6789|9876|8765|7654|6543|5432|4321|3210)", 3],
    "P6": [r"^(\d)(\d)(\d)\3\2\1$", 5], "P4": [r"^(\d)(\d)\2\1$", 3],
    "SPH": [r"(69|420|1337|007)", 4], "SPM": [r"(100|200|300|400|500|666|777|888|999)", 2],
    "QD": [r"(1111|2222|3333|4444|5555|6666|7777|8888|9999|0000)", 4],
    "MH": [r"^(\d{2,3})\1$", 3], "MM": [r"(\d{2})0\1", 2], "GD": [r"1618|0618", 3],
    "PAIR3": [r"(\d)\1(\d)\2(\d)\3", 3],
    "PAIRX": [r"(\d)\1.*(\d)\2.*(\d)\3", 2],
    "ALT": [r"(\d)(\d)\1\2\1\2", 3], "ALT8": [r"(\d)(\d)\1\2\1\2\1\2", 4],
    "TAIL0": [r"0{4,}$", 3], "HEAD1": [r"^1{2,}", 2],
    "BLOCK": [r"(\d{2,3})\1{1,}", 4],
    "STEP2": [r"(13579|2468|8642|97531)", 4],
    "MIX": [r"(55|66|77|88|99){2,}", 3]
}
PATTERNS = [(re.compile(v[0]), v[1]) for v in _PATTERNS_RAW.values()]

def check_rarity(account_id, threshold=DEFAULT_THRESHOLD):
    if not account_id or account_id == "N/A":
        return False, 0
    score = 0
    for pat, pts in PATTERNS:
        if pat.search(account_id): score += pts
    digits = [int(d) for d in account_id if d.isdigit()]
    if len(digits) >= 4 and len(set(digits)) == 1: score += 5
    if len(digits) >= 4:
        diffs = [digits[i+1] - digits[i] for i in range(len(digits)-1)]
        if len(set(diffs)) == 1: score += 4
    if len(account_id) <= 8 and account_id.isdigit() and int(account_id) < 1000000: score += 3
    return (score > threshold), score

def generate_random_name(prefix):
    chars = string.ascii_letters + string.digits
    return prefix + ''.join(random.choice(chars) for _ in range(6)).upper()

# ============================================================
# REGISTRATION PIPELINE
# ============================================================
def create_account(region, account_name, password_prefix, device, proxy):
    try:
        rand_part = "".join(random.choices("0123456789ABCDEF", k=16))
        password = f"{password_prefix}_{rand_part}"
        url = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
        payload = {"app_id": 100067, "client_type": 2, "password": password, "source": 2}
        body_json = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(HEX_KEY, body_json.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = _merge_headers({
            "User-Agent": WAFBypass.get_ua(),
            "Connection": "Keep-Alive",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Authorization": f"Signature {signature}",
            "Content-Type": "application/json; charset=utf-8",
            "Host": "100067.connect.garena.com",
        }, device=device)

        resp = request_retry('POST', url, tag="Register", proxy=proxy, headers=headers, data=body_json)
        if resp and resp.status_code == 200:
            res = resp.json()
            if "data" in res and "uid" in res["data"]:
                return get_token(str(res["data"]["uid"]), password, region, account_name, password_prefix, device, proxy)
        return None
    except Exception:
        return None

def get_token(uid, password, region, account_name, password_prefix, device, proxy):
    try:
        url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        headers = _merge_headers({
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": WAFBypass.get_ua(),
        }, device=device)
        body = {"uid": uid, "password": password, "response_type": "token",
                "client_type": "2", "client_secret": HEX_KEY, "client_id": "100067"}
        resp = request_retry('POST', url, tag="Token", proxy=proxy, headers=headers, data=body)

        if resp and resp.status_code == 200 and 'open_id' in resp.json():
            j = resp.json()
            open_id = j['open_id']
            access_token = j["access_token"]
            keystream = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
                         0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
            encoded = "".join(chr(ord(open_id[i]) ^ keystream[i % len(keystream)]) for i in range(len(open_id)))
            field = codecs.decode(
                ''.join(c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in encoded),
                'unicode_escape'
            ).encode('latin1')
            return major_register(access_token, open_id, field, uid, password, region, account_name, password_prefix, device, proxy)
        return None
    except Exception:
        return None

def major_register(access_token, open_id, field, uid, password, region, account_name, password_prefix, device, proxy):
    try:
        host = _login_host(region)
        url = f"https://{host}/MajorRegister"
        name = generate_random_name(account_name)
        headers = _merge_headers({
            'Host': host,
            'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Accept': '*/*', 'Accept-Encoding': 'deflate, gzip',
            'Authorization': 'Bearer', 'X-GA': 'v1 1',
            'ReleaseVersion': "OB55",
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Unity-Version': '2018.4.12f1',
        }, device=device)
        lang = REGION_LANG.get(region.upper(), "en")
        reg_msg = {1: name, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1, 13: 1,
                   14: encode_f14(open_id), 15: lang, 16: 2, 20: "2.132.4", 21: 1, 22: FIELD_22}
        payload_bytes = build_proto(reg_msg)
        encrypted = aes_encrypt(payload_bytes.hex())

        request_retry('POST', url, tag="MajorRegister", proxy=proxy, headers=headers, data=encrypted)
        login_result = major_login(uid, password, access_token, open_id, region, device, proxy)
        account_id = login_result.get("account_id", "N/A")
        jwt_token  = login_result.get("jwt_token", "")
        if account_id != "N/A":
            if jwt_token and region.upper() != "BR":
                try: force_region_bind(region, jwt_token, device, proxy)
                except: pass
            return {
                "uid": uid, "password": password, "name": name, "region": region,
                "account_id": account_id, "jwt_token": jwt_token,
                "device_model": device["model"], "device_id": device["device_id"],
                "ip_used": proxy,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        return None
    except Exception:
        return None

def major_login(uid, password, access_token, open_id, region, device, proxy):
    try:
        lang = REGION_LANG.get(region.upper(), "en")
        gpu = device["gpu"]; gpu_full = f"{gpu}|OpenGL ES 3.2"
        model = device["model"]; os_str = device["android_full"]
        operator = device["operator"]; network = device["network"]
        device_uuid = device["uuid"]; cpu = device["cpu"]
        
        ip_addr = f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        
        open_id_b      = open_id.encode()      if isinstance(open_id, str)      else open_id
        access_token_b = access_token.encode() if isinstance(access_token, str) else access_token

        payload_dict = {
            3:  datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            4:  b'free fire', 5: 1, 7: "2.132.4", 8: os_str,
            9: b'Handheld', 10: operator, 11: network,
            12: 1280, 13: 720, 14: b'240', 15: cpu,
            16: random.choice([5951, 6000, 6100, 5500]),
            17: gpu, 18: gpu_full, 19: f'Google|{device_uuid}', 20: ip_addr,
            21: lang, 22: open_id_b, 23: b'4', 24: b'Handheld', 25: model, 26: lang,
            29: access_token_b, 30: 1, 41: operator, 42: network,
            57: b'1ac4b80ecf0478a44203bf8fac6120f5',
            60: 30000, 61: 30000, 62: 2519, 63: 243,
            64: 32357, 65: 34308, 66: 32357, 67: 34308, 73: 1,
            74: b'/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/lib/arm',
            76: 2,
            77: b'428775ab8c8845bd341b5357ec61d15e|/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/base.apk',
            78: 2, 79: 1, 81: b'32', 83: b'2019118525', 85: 3,
            86: b'OpenGLES3', 87: 4095, 88: 4,
            92: random.choice([19788, 20000, 21000]),
            93: b'android_max',
            94: b'KqsHT2gyPt7vUCc9SCjv2ioi3WEZSEL86ErvXB38suVVK/Z4IVt78ESl/r2S15C1pqu/j6ZmgFL7HbwoFiiVconX08ooKiisQffvEAPCo/C+Lahr',
            96: b'{"cur_rate":null,"support_etc2":true}',
            97: 1, 98: 1, 99: b'4', 100: b'4', 102: b'',
            104: 77149, 105: 1,
            106: b'https://dl.cdn.freefiremobile.com/live/ABHotUpdates/|https://dl-core.cdn.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462',
            107: b'c8e41b7a93f02d56e1a94c7b8203f5d1',
        }
        data = build_proto(payload_dict)

        host = _login_host(region)
        url = f"https://{host}/MajorLogin"
        headers = _merge_headers({
            'Host': host,
            'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Accept': '*/*', 'Accept-Encoding': 'deflate, gzip',
            'Authorization': 'Bearer', 'X-GA': 'v1 1',
            'X-Ga-Sv': '1789534056', 'ReleaseVersion': "OB55",
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Unity-Version': '2018.4.12f1',
        }, device=device)

        enc_hex = encrypt_api(data.hex())
        resp = request_retry('POST', url, tag="MajorLogin", proxy=proxy, headers=headers, data=bytes.fromhex(enc_hex))

        if resp and resp.status_code == 200 and len(resp.text) > 10:
            jwt_start = resp.text.find("eyJ")
            if jwt_start != -1:
                jwt_token = resp.text[jwt_start:]
                second_dot = jwt_token.find(".", jwt_token.find(".") + 1)
                if second_dot != -1:
                    jwt_token = jwt_token[:second_dot + 44]
                    try:
                        parts = jwt_token.split('.')
                        if len(parts) >= 2:
                            pp = parts[1]
                            padding = 4 - len(pp) % 4
                            if padding != 4: pp += '=' * padding
                            claims = json.loads(base64.urlsafe_b64decode(pp))
                            account_id = claims.get('account_id') or claims.get('external_id')
                            if account_id:
                                return {"account_id": str(account_id), "jwt_token": jwt_token}
                    except Exception:
                        pass
        return {"account_id": "N/A", "jwt_token": ""}
    except Exception:
        return {"account_id": "N/A", "jwt_token": ""}

def force_region_bind(region, jwt_token, device, proxy):
    try:
        host = _login_host(region)
        url = f"https://{host}/ChooseRegion"
        region_code = "RU" if region.upper() == "CIS" else region.upper()
        proto_data = build_proto({1: region_code})
        encrypted = encrypt_api(proto_data.hex())
        headers = _merge_headers({
            "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "Accept": "*/*", "Accept-Encoding": "deflate, gzip",
            "X-Ga-Sv": "1789534056",
            "Authorization": f"Bearer {jwt_token}",
            "X-Ga": "v1 1", "Releaseversion": "OB55",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Unity-Version": "2018.4.12f1"
        }, device=device)
        request_retry('POST', url, tag="ForceRegionBind", proxy=proxy, data=bytes.fromhex(encrypted), headers=headers)
    except Exception:
        pass

# ============================================================
# JOB
# ============================================================
class GenerationJob:
    def __init__(self, chat_id, region, name_prefix, is_ghost, target, threads, threshold):
        self.chat_id = chat_id
        self.region = region
        self.name_prefix = name_prefix
        self.is_ghost = is_ghost
        self.target = target
        self.threads = threads
        self.threshold = threshold
        self.count_ok = 0
        self.rare_cnt = 0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.start_time = time.time()
        self.last_progress = time.time()
        self.results = []
        self.rare_results = []
        self.user_dir = os.path.join(BASE_FOLDER, str(chat_id))
        os.makedirs(self.user_dir, exist_ok=True)

ACTIVE_JOBS = {}
JOBS_LOCK = threading.Lock()
_running_tasks = set()

def process_result(job, acc, thread_id):
    is_rare, score = check_rarity(acc.get("account_id",""), job.threshold)
    record = {
        "uid": acc.get("uid","N/A"),
        "password": acc.get("password",""),
        "name": acc.get("name","N/A"),
        "account_id": acc.get("account_id","N/A"),
        "jwt_token": acc.get("jwt_token",""),
        "device_model": acc.get("device_model","N/A"),
        "device_id": acc.get("device_id","N/A"),
        "ip_used": acc.get("ip_used","N/A"),
        "score": score,
        "rare": is_rare,
        "thread": thread_id,
    }
    with job.lock:
        if job.count_ok >= job.target: return
        job.count_ok += 1
        job.last_progress = time.time()
        job.results.append(record)
        if is_rare:
            job.rare_cnt += 1
            job.rare_results.append(record)
        if job.count_ok >= job.target:
            job.stop_event.set()

def worker_loop(job, thread_id):
    while not job.stop_event.is_set():
        with job.lock:
            if job.count_ok >= job.target: return
        
        proxy = PROXY_QUEUE.get_ip()
        if not proxy:
            time.sleep(1.0)
            continue

        device = DevicePool.get()

        acc = None
        with API_SEMAPHORE:
            try:
                acc = create_account(job.region, job.name_prefix, DEFAULT_PREFIX, device, proxy)
            except:
                acc = None
            
        if acc and acc.get("account_id","N/A") != "N/A":
            process_result(job, acc, thread_id)

def write_job_files(job):
    region_tag = "GHOST" if job.is_ghost else job.region.upper()
    files = {}

    acc_path = os.path.join(job.user_dir, f"accounts-{region_tag}.json")
    with open(acc_path, "w", encoding="utf-8") as f:
        json.dump([{
            "uid": r["uid"], "password": r["password"],
            "name": r["name"], "account_id": r["account_id"],
        } for r in job.results], f, indent=2, ensure_ascii=False)
    files["accounts"] = acc_path

    tok = [r for r in job.results if r.get("jwt_token")]
    if tok:
        tok_path = os.path.join(job.user_dir, f"tokens-{region_tag}.json")
        with open(tok_path, "w", encoding="utf-8") as f:
            json.dump([{
                "uid": r["uid"], "account_id": r["account_id"],
                "jwt_token": r["jwt_token"],
            } for r in tok], f, indent=2, ensure_ascii=False)
        files["tokens"] = tok_path

    if job.rare_results:
        rare_path = os.path.join(job.user_dir, f"rare-{region_tag}.json")
        with open(rare_path, "w", encoding="utf-8") as f:
            json.dump(job.rare_results, f, indent=2, ensure_ascii=False)
        files["rare"] = rare_path

    map_path = os.path.join(job.user_dir, f"device_mapping-{region_tag}.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump([{
            "account_id": r["account_id"],
            "device_model": r["device_model"],
            "device_id": r["device_id"],
            "ip_used": r["ip_used"]
        } for r in job.results], f, indent=2, ensure_ascii=False)
    files["device_mapping"] = map_path

    return files

# ============================================================
# UI HELPERS
# ============================================================
def main_menu_kb(chat_id=None):
    kb = [
        [InlineKeyboardButton("🎯 Generate", callback_data="gen:start"),
         InlineKeyboardButton("🪙 My Coins", callback_data="coins")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
         InlineKeyboardButton("🔗 Refer & Earn", callback_data="refer")],
        [InlineKeyboardButton("🎟 Redeem Code", callback_data="redeem")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(kb)

def region_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ME",  callback_data="region:ME"),
         InlineKeyboardButton("IND", callback_data="region:IND"),
         InlineKeyboardButton("ID",  callback_data="region:ID")],
        [InlineKeyboardButton("VN",  callback_data="region:VN"),
         InlineKeyboardButton("TH",  callback_data="region:TH"),
         InlineKeyboardButton("BD",  callback_data="region:BD")],
        [InlineKeyboardButton("PK",  callback_data="region:PK"),
         InlineKeyboardButton("TW",  callback_data="region:TW"),
         InlineKeyboardButton("CIS", callback_data="region:CIS")],
        [InlineKeyboardButton("SAC", callback_data="region:SAC")],
        [InlineKeyboardButton("👻 GHOST", callback_data="region:GHOST")],
        [InlineKeyboardButton("« Back", callback_data="main:menu")],
    ])

def progress_bar(cur, total, width=20):
    if total <= 0: return "░" * width
    filled = min(width, int(width * cur / total))
    return "█" * filled + "░" * (width - filled)

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}h {m}m {s}s"
    if m > 0: return f"{m}m {s}s"
    return f"{s}s"

def format_progress(job):
    elapsed = max(0.001, time.time() - job.start_time)
    speed = job.count_ok / elapsed
    remain = max(0, job.target - job.count_ok)
    eta = remain / speed if speed > 0 else 0
    region_tag = "GHOST" if job.is_ghost else job.region.upper()
    eta_str = format_time(eta)
    return (
        f"{E_TIME} <b>{BOT_NAME} — {region_tag}</b>\n\n"
        f"<code>[{progress_bar(job.count_ok, job.target)}]</code>\n"
        f"<b>{job.count_ok}</b> / {job.target}  •  {E_GEM} <b>{job.rare_cnt}</b> rare\n"
        f"{E_ZAP} {speed:.1f} acc/s  •  {E_TIME} ETA: {eta_str}\n"
        f"🧵 Threads: {job.threads}  •  {E_TARGET} Score&gt;{job.threshold}"
    )

# ============================================================
# HANDLERS
# ============================================================
ST_REGION, ST_NAME, ST_TARGET = range(3)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    users = load_users()

    if context.args and len(context.args) > 0:
        ref_id = context.args[0]
        if ref_id != chat_id and ref_id in users and chat_id not in users:
            users[chat_id] = {
                "name": user.first_name,
                "coins": 0,
                "referrals": 0,
                "generated": 0,
                "referred_by": ref_id
            }
            users[ref_id]["referrals"] += 1
            users[ref_id]["coins"] += REFERRAL_COINS
            save_users(users)

    if chat_id not in users:
        users[chat_id] = {
            "name": user.first_name,
            "coins": 0,
            "referrals": 0,
            "generated": 0,
            "referred_by": None
        }
        save_users(users)

    u = users[chat_id]

    if is_admin(chat_id):
        coins_disp = "∞ (Unlimited)"
    else:
        coins_disp = u['coins']

    text = (
        f"{E_ZAP} <b>Free Fire Account Generator</b>\n"
        f"────────────────────\n"
        f"{E_USER} <b>{u['name']}</b>\n"
        f"{E_COIN} Coins    : <b>{coins_disp}</b>\n"
        f"{E_LINK} Referrals : <b>{u['referrals']}</b>\n"
        f"{E_TARGET} Generated : <b>{u['generated']}</b>\n"
        f"────────────────────"
    )
    await safe_send(update.effective_chat, text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(chat_id))

async def gen_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    chat_id = update.effective_chat.id
    with JOBS_LOCK:
        if chat_id in ACTIVE_JOBS:
            msg = f"{E_CROSS} A generation is already running. Use /stop first."
            if query: await safe_edit(query, msg, parse_mode=ParseMode.HTML)
            else: await safe_send(update.effective_chat, msg, parse_mode=ParseMode.HTML)
            return ConversationHandler.END
    text = f"{E_GLOBE} <b>Select region</b>"
    if query: await safe_edit(query, text, parse_mode=ParseMode.HTML, reply_markup=region_kb())
    else:     await safe_send(update.effective_chat, text, parse_mode=ParseMode.HTML, reply_markup=region_kb())
    return ST_REGION

async def region_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":", 1)[1]
    if data == "GHOST":
        context.user_data["region"] = "BD"
        context.user_data["is_ghost"] = True
        label = "👻 GHOST"
    else:
        context.user_data["region"] = data
        context.user_data["is_ghost"] = False
        label = data
    await safe_edit(query, 
        f"{E_GLOBE} Region: <b>{label}</b>\n\n"
        f"Send the <b>name prefix</b> (default: <code>{DEFAULT_PREFIX}</code>):",
        parse_mode=ParseMode.HTML,
    )
    return ST_NAME

async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefix = (update.message.text or "").strip() or DEFAULT_PREFIX
    context.user_data["name_prefix"] = prefix[:12]
    await safe_send(update.message, 
        f"✏️ Prefix: <b>{context.user_data['name_prefix']}</b>\n\n"
        f"Send the <b>target count</b> (1 – 500, default 10):\n"
        f"<i>(1 Coin = 1 Account)</i>",
        parse_mode=ParseMode.HTML,
    )
    return ST_TARGET

async def target_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int((update.message.text or "").strip() or "10")
        n = max(1, min(n, 500))
    except ValueError:
        await safe_send(update.message, f"{E_CROSS} Invalid number. Send a count (1–500).", parse_mode=ParseMode.HTML)
        return ST_TARGET

    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)
    u = get_user(chat_id_str)
    
    if not is_admin(chat_id_str) and u["coins"] < n:
        await safe_send(update.message, 
            f"{E_CROSS} <b>Not enough coins!</b>\n\n"
            f"You need <b>{n}</b> coins to generate {n} accounts.\n"
            f"Your balance: <b>{u['coins']} coins</b>\n\n"
            f"Invite friends using 'Refer & Earn' to get more coins!",
            parse_mode=ParseMode.HTML
        )
        return ST_TARGET

    context.user_data["target"] = n
    
    if not is_admin(chat_id_str):
        users = load_users()
        if chat_id_str in users and users[chat_id_str]["coins"] >= n:
            users[chat_id_str]["coins"] -= n
            save_users(users)
        else:
            await safe_send(update.message, f"{E_CROSS} Error: Not enough coins or double click detected.", parse_mode=ParseMode.HTML)
            return ConversationHandler.END

    if n <= 50:
        threads_to_use = 30
    elif n <= 200:
        threads_to_use = 70
    else:
        threads_to_use = 150

    job = GenerationJob(
        chat_id=chat_id,
        region=context.user_data["region"],
        name_prefix=context.user_data["name_prefix"],
        is_ghost=context.user_data["is_ghost"],
        target=n,
        threads=threads_to_use,
        threshold=DEFAULT_THRESHOLD,
    )
    with JOBS_LOCK:
        ACTIVE_JOBS[chat_id] = job

    deduct_msg = "Unlimited" if is_admin(chat_id_str) else f"{n} Coins Deducted"
    await safe_send(update.message, 
        f"{E_ROCKET} <b>{BOT_NAME} — Starting</b>\n"
        f"Region: <b>{'GHOST' if job.is_ghost else job.region}</b>  •  "
        f"Target: <b>{job.target}</b>  •  Threads: <b>{job.threads}</b>\n"
        f"{E_COIN} <b>{deduct_msg}</b>",
        parse_mode=ParseMode.HTML,
    )
    task = asyncio.create_task(_run_generation_task(job, update, context))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return ConversationHandler.END

async def _run_generation_task(job, update, context):
    chat = update.effective_chat
    for i in range(job.threads):
        threading.Thread(target=worker_loop, args=(job, i+1), daemon=True).start()

    stop_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Generation", callback_data="stop:gen")]])
    status = await safe_send(chat, format_progress(job), parse_mode=ParseMode.HTML, reply_markup=stop_markup)
    
    last_text = None
    stall_cycles = 0

    while not job.stop_event.is_set():
        await asyncio.sleep(2.5)
        with job.lock:
            done = job.count_ok >= job.target
            stalled = (time.time() - job.last_progress) > STALL_TIMEOUT
        if done: break
        if stalled:
            stall_cycles += 1
            if stall_cycles >= 2:
                await safe_send(chat, f"{E_CROSS} Stall detected — stopping.", parse_mode=ParseMode.HTML)
                break
        else:
            stall_cycles = 0
        
        text = format_progress(job)
        if text != last_text:
            last_text = text
            try:
                await safe_edit(status, text, parse_mode=ParseMode.HTML, reply_markup=stop_markup)
            except Exception:
                pass

    job.stop_event.set()
    await asyncio.sleep(0.4)

    try:
        await safe_edit(status, f"{E_CHECK} Generation Finished!", reply_markup=None, parse_mode=ParseMode.HTML)
    except Exception:
        pass

    chat_id_str = str(job.chat_id)
    users = load_users()
    
    if chat_id_str in users:
        if job.count_ok < job.target and not is_admin(chat_id_str):
            refund = job.target - job.count_ok
            users[chat_id_str]["coins"] += refund
        users[chat_id_str]["generated"] += job.count_ok
        save_users(users)

    files = write_job_files(job)
    elapsed = max(0.001, time.time() - job.start_time)
    speed = job.count_ok / elapsed
    region_tag = "GHOST" if job.is_ghost else job.region.upper()

    summary = (
        f"{E_CHECK if job.count_ok >= job.target else '⚠️'} "
        f"<b>{job.count_ok}/{job.target}</b> — {region_tag}\n"
        f"{E_TIME} {elapsed:.1f}s  •  {E_ZAP} {speed:.1f} acc/s  •  {E_GEM} {job.rare_cnt} rare"
    )
    await safe_send(chat, summary, parse_mode=ParseMode.HTML)

    for label, path in files.items():
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                with open(path, "rb") as fh:
                    await chat.send_document(document=fh, filename=os.path.basename(path), caption=label)
            except Exception:
                pass

    with JOBS_LOCK:
        ACTIVE_JOBS.pop(job.chat_id, None)

async def stop_generation_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    with JOBS_LOCK:
        job = ACTIVE_JOBS.get(chat_id)
    
    if not job:
        await safe_edit(query, f"{E_INFO} Nothing is running right now.", reply_markup=None, parse_mode=ParseMode.HTML)
        return

    job.stop_event.set()
    await safe_edit(query, f"{E_STOP} Stop requested — sending partial results...", reply_markup=None, parse_mode=ParseMode.HTML)

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with JOBS_LOCK:
        job = ACTIVE_JOBS.get(chat_id)
    if not job:
        await safe_send(update.effective_chat, f"{E_INFO} Nothing is running.", parse_mode=ParseMode.HTML)
        return
    job.stop_event.set()
    await safe_send(update.effective_chat, f"{E_STOP} Stop requested — sending partial results...", parse_mode=ParseMode.HTML)

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.effective_chat, f"{E_CROSS} Cancelled.", reply_markup=main_menu_kb(update.effective_chat.id), parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    u = get_user(chat_id)
    
    if is_admin(chat_id):
        coins_disp = "∞ (Unlimited)"
    else:
        coins_disp = u['coins']

    text = (
        f"{E_ZAP} <b>Free Fire Account Generator</b>\n"
        f"────────────────────\n"
        f"{E_USER} <b>{u['name']}</b>\n"
        f"{E_COIN} Coins    : <b>{coins_disp}</b>\n"
        f"{E_LINK} Referrals : <b>{u['referrals']}</b>\n"
        f"{E_TARGET} Generated : <b>{u['generated']}</b>\n"
        f"────────────────────"
    )
    await safe_edit(query, text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(chat_id))
    return ConversationHandler.END

async def coins_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    u = get_user(chat_id)
    
    if is_admin(chat_id):
        coins_disp = "∞ (Unlimited Admin)"
    else:
        coins_disp = f"{u['coins']} coins"

    await safe_edit(query, 
        f"{E_COIN} <b>Your Coins</b>\n\n"
        f"You currently have <b>{coins_disp}</b>.\n"
        f"1 Coin = 1 Account Generation.\n\n"
        f"Invite friends to earn <b>{REFERRAL_COINS} Coins</b> per referral!",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(chat_id)
    )

async def leaderboard_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    users = load_users()
    top_users = sorted(users.items(), key=lambda x: x[1].get("generated", 0), reverse=True)[:10]
    
    text = f"{E_TROPHY} <b>Top 10 Generators</b>\n\n"
    for i, (uid, data) in enumerate(top_users, 1):
        text += f"{i}. <b>{data.get('name', 'User')}</b> — {data.get('generated', 0)} accs\n"
        
    await safe_edit(query, text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(chat_id))

async def refer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    bot_username = context.bot.username
    invite_link = f"https://t.me/{bot_username}?start={chat_id}"
    
    text = (
        f"{E_LINK} <b>Refer & Earn</b>\n\n"
        f"Invite your friends using your link and earn <b>{REFERRAL_COINS} Coins</b> per invite!\n\n"
        f"👇 <b>Your Invite Link (Share this):</b>\n"
        f"<code>{invite_link}</code>\n\n"
        f"{E_SPEAK} <b>Join Our Main Channel:</b>\n"
        f"{CUSTOM_CHANNEL_LINK}"
    )
    
    await safe_edit(query, 
        text, 
        parse_mode=ParseMode.HTML, 
        disable_web_page_preview=True,
        reply_markup=main_menu_kb(chat_id)
    )

async def redeem_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    await safe_edit(query, 
        f"{E_TICKET} <b>Redeem Code</b>\n\n"
        f"To redeem your gift code, please send:\n"
        f"<code>/redeem YOUR_CODE</code>\n\n"
        f"<i>Example: /redeem CHINU50</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(chat_id)
    )

async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await safe_send(update.message, f"{E_CROSS} Usage: <code>/redeem YOUR_CODE</code>", parse_mode=ParseMode.HTML)
        return
    
    code = context.args[0].upper()
    codes = load_codes()
    
    if code not in codes:
        await safe_send(update.message, f"{E_CROSS} Invalid or expired redeem code.", parse_mode=ParseMode.HTML)
        return
        
    code_data = codes[code]
    
    if code_data["uses"] >= code_data["max_uses"]:
        await safe_send(update.message, f"{E_CROSS} This code has reached its maximum usage limit.", parse_mode=ParseMode.HTML)
        return

    users_who_used = code_data.get("users", [])
    if chat_id in users_who_used:
        await safe_send(update.message, f"{E_CROSS} You have already redeemed this code!", parse_mode=ParseMode.HTML)
        return

    users = load_users()
    if chat_id in users:
        users[chat_id]["coins"] += code_data["amount"]
        save_users(users)
        
    codes[code]["uses"] += 1
    if "users" not in codes[code]:
        codes[code]["users"] = []
    codes[code]["users"].append(chat_id)
    save_codes(codes)

    await safe_send(update.message, 
        f"{E_CHECK} <b>Code Redeemed Successfully!</b>\n\n"
        f"You received <b>{code_data['amount']} Coins</b>.\n"
        f"Your new balance: <b>{users[chat_id]['coins']} Coins</b>.",
        parse_mode=ParseMode.HTML
    )

async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    await safe_edit(query, 
        f"{E_BOT} <b>{BOT_NAME} — Help</b>\n\n"
        f"{E_TARGET} <b>Generate</b> — Create accounts (1 Coin = 1 Acc)\n"
        f"{E_COIN} <b>Coins</b> — View your balance\n"
        f"{E_LINK} <b>Refer</b> — Invite friends for coins\n"
        f"{E_TICKET} <b>Redeem</b> — Redeem a code (/redeem CODE)\n"
        f"{E_TROPHY} <b>Leaderboard</b> — Top users\n\n"
        f"<i>Commands:</i>\n"
        f"/start — Menu\n"
        f"/stop — Abort generation",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(chat_id)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    await safe_send(update.effective_chat, 
        f"{E_BOT} <b>{BOT_NAME} — All Commands</b>\n\n"
        f"🔹 /start — Main Menu\n"
        f"🔹 /generate — Quick Start\n"
        f"🔹 /stop — Abort current run\n"
        f"🔹 /redeem CODE — Redeem a gift code\n"
        f"🔹 /help — This message\n\n"
        f"{E_FOLDER} Outputs saved under <code>CHINU-MODS/&lt;chat_id&gt;/</code>.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(chat_id)
    )

# ============================================================
# ADMIN COMMANDS
# ============================================================
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not is_admin(chat_id):
        return
        
    text = (
        f"👑 <b>Admin Panel</b>\n\n"
        f"<b>Available Commands:</b>\n"
        f"1️⃣ <b>Broadcast:</b>\n"
        f"<code>/broadcast Your message here</code>\n\n"
        f"2️⃣ <b>Give Coins:</b>\n"
        f"<code>/givecoins user_id amount</code>\n"
        f"<i>Example: /givecoins 123456789 50</i>\n\n"
        f"3️⃣ <b>Create Redeem Code:</b>\n"
        f"<code>/createcode CODE amount max_uses</code>\n"
        f"<i>Example: /createcode CHINU50 50 100</i>"
    )
    await safe_send(update.effective_chat, text, parse_mode=ParseMode.HTML)

async def admin_givecoins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not is_admin(chat_id): return
    
    if len(context.args) != 2:
        await safe_send(update.message, f"{E_CROSS} Usage: <code>/givecoins user_id amount</code>", parse_mode=ParseMode.HTML)
        return
        
    target_id = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await safe_send(update.message, f"{E_CROSS} Invalid amount.", parse_mode=ParseMode.HTML)
        return
        
    users = load_users()
    if target_id not in users:
        await safe_send(update.message, f"{E_CROSS} User ID {target_id} not found in database. They must /start the bot first.", parse_mode=ParseMode.HTML)
        return
        
    users[target_id]["coins"] += amount
    save_users(users)
    
    await safe_send(update.message, 
        f"{E_CHECK} Successfully added <b>{amount} Coins</b> to user <code>{target_id}</code>.\n"
        f"Their new balance: <b>{users[target_id]['coins']} Coins</b>.",
        parse_mode=ParseMode.HTML
    )

async def admin_createcode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not is_admin(chat_id): return
    
    if len(context.args) != 3:
        await safe_send(update.message, f"{E_CROSS} Usage: <code>/createcode CODE amount max_uses</code>", parse_mode=ParseMode.HTML)
        return
        
    code = context.args[0].upper()
    try:
        amount = int(context.args[1])
        max_uses = int(context.args[2])
    except ValueError:
        await safe_send(update.message, f"{E_CROSS} Invalid amount or max_uses.", parse_mode=ParseMode.HTML)
        return
        
    codes = load_codes()
    codes[code] = {
        "amount": amount,
        "max_uses": max_uses,
        "uses": 0,
        "users": []
    }
    save_codes(codes)
    
    await safe_send(update.message, 
        f"{E_CHECK} <b>Redeem Code Created!</b>\n\n"
        f"Code: <code>{code}</code>\n"
        f"Amount: <b>{amount} Coins</b>\n"
        f"Max Uses: <b>{max_uses}</b> (1 per user)",
        parse_mode=ParseMode.HTML
    )

async def admin_broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not is_admin(chat_id): return
    
    if not context.args:
        await safe_send(update.message, f"{E_CROSS} Usage: <code>/broadcast Your message here</code>", parse_mode=ParseMode.HTML)
        return
        
    msg_text = " ".join(context.args)
    users = load_users()
    total = len(users)
    
    status_msg = await safe_send(update.message, f"{E_ZAP} Broadcasting to {total} users...", parse_mode=ParseMode.HTML)
    
    success = 0
    failed = 0
    for uid in users.keys():
        try:
            await context.bot.send_message(chat_id=uid, text=msg_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
            
    await safe_edit(status_msg, 
        f"{E_CHECK} <b>Broadcast Complete</b>\n\n"
        f"Total: {total}\n"
        f"Success: {success}\n"
        f"Failed: {failed}",
        parse_mode=ParseMode.HTML
    )

# ============================================================
# APP
# ============================================================
async def _on_error(update, context):
    logging.getLogger("axiom").exception(
        "handler error: %s", context.error, exc_info=context.error)

def build_app():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("generate", gen_start),
            CallbackQueryHandler(gen_start, pattern="^gen:start$"),
        ],
        states={
            ST_REGION:  [CallbackQueryHandler(region_selected, pattern="^region:")],
            ST_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)],
            ST_TARGET:  [MessageHandler(filters.TEXT & ~filters.COMMAND, target_received)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conv),
            CommandHandler("stop", stop_cmd),
            CallbackQueryHandler(back_to_menu, pattern="^main:menu$"),
        ],
        allow_reentry=True,
    )

    # Slash Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("redeem", redeem_cmd))
    
    # Admin Commands
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("givecoins", admin_givecoins_cmd))
    app.add_handler(CommandHandler("createcode", admin_createcode_cmd))
    app.add_handler(CommandHandler("broadcast", admin_broadcast_cmd))
    
    app.add_handler(conv)
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(coins_cb, pattern="^coins$"))
    app.add_handler(CallbackQueryHandler(leaderboard_cb, pattern="^leaderboard$"))
    app.add_handler(CallbackQueryHandler(refer_cb, pattern="^refer$"))
    app.add_handler(CallbackQueryHandler(redeem_cb, pattern="^redeem$"))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^main:menu$"))
    app.add_handler(CallbackQueryHandler(stop_generation_cb, pattern="^stop:gen$"))
    
    app.add_error_handler(_on_error)

    return app

if __name__ == "__main__":
    print(f"[{BOT_NAME}] {BOT_TAGLINE} · devices={DEVICE_POOL_SIZE} · strict 1:1 IP rotation")
    build_app().run_polling(drop_pending_updates=True)
