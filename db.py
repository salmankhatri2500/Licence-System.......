# ================================================================

# db.py - FOS Final Database

# FOS_Master: agents tab + logs tab + queue tab + admin_settings tab

# Agent Sheet (manually created): clients, applications,

#   payments, agent_payments, settings tabs

# ================================================================

import logging

from datetime import datetime, timedelta

from zoneinfo import ZoneInfo



import gspread

from google.oauth2.service_account import Credentials

from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound



from config import GOOGLE_CREDS, SCOPES, MASTER_SHEET, ADMIN_GMAIL

from utils import now_ist, safe_float, safe_int, IST



logger = logging.getLogger(__name__)



HDR = {

    "agents": ["agent_id","agent_name","phone","telegram_id","sheet_name",

               "rate_per_app","qr_file_id","joined_at","status",

               "total_apps","total_clients","balance"],

    "logs":   ["event","agent","detail","timestamp"],

    "queue":  ["queue_id","app_no","dob","password","client_code",

               "client_name","client_tid","agent_id","agent_name",

               "agent_tid","submitted_at","status","done_at","priority"],

    "admin_settings": ["key","value"],

    "clients":      ["client_code","full_name","phone","telegram_id",

                     "joined_at","status","total_apps","balance"],

    "applications": ["app_id","app_no","dob","password","client_code",

                     "agent_id","created_at","status","done_at"],

    "payments":     ["payment_id","client_code","amount","status",

                     "date","time","approved_by","approved_at"],

    "agent_payments":["payment_id","agent_id","amount","status",

                      "date","time","approved_by","approved_at"],

    "settings":     ["key","value"],

}



COL_W = {

    "agents":       [120,160,120,140,180,100,80,150,80,80,90,90],

    "queue":        [130,110,90,130,120,150,120,110,150,120,150,80,150,70],

    "clients":      [120,160,120,140,150,70,70,90],

    "applications": [120,110,90,120,120,110,150,80,150],

    "payments":     [120,120,90,80,100,90,110,150],

    "agent_payments":[120,120,90,80,100,90,110,150],

    "settings":     [160,280],

    "admin_settings":[160,280],

    "logs":         [150,160,300,150],

}



H_BG = {"red":0.13,"green":0.29,"blue":0.53}

H_FG = {"red":1.0,"green":1.0,"blue":1.0}

ROW_C = {

    "active":   {"red":0.72,"green":0.96,"blue":0.73},

    "pending":  {"red":1.0,"green":0.98,"blue":0.80},

    "done":     {"red":0.72,"green":0.96,"blue":0.73},

    "paid":     {"red":0.72,"green":0.96,"blue":0.73},

    "held":     {"red":1.0,"green":0.85,"blue":0.70},

    "blocked":  {"red":1.0,"green":0.80,"blue":0.80},

    "rejected": {"red":1.0,"green":0.80,"blue":0.80},

}





class DB:

    def __init__(self):

        self._gc  = None

        self._msh = None



    def connect(self) -> bool:

        try:

            creds    = Credentials.from_service_account_info(GOOGLE_CREDS, scopes=SCOPES)

            self._gc = gspread.authorize(creds)

            self._msh = None

            logger.info("DB: connected")

            return True

        except Exception as e:

            logger.error(f"DB connect: {e}")

            return False



    def _gc_(self):

        if not self._gc:

            self.connect()

        return self._gc



    def open(self, name: str):

        try:

            return self._gc_().open(name)

        except SpreadsheetNotFound:

            return None

        except Exception:

            try:

                self.connect()

                return self._gc_().open(name)

            except Exception as e:

                logger.error(f"open({name}): {e}")

                return None



    def master(self):

        if self._msh:

            try:

                _ = self._msh.title

                return self._msh

            except:

                self._msh = None

        sh = self.open(MASTER_SHEET)

        self._msh = sh

        return sh



    def ws(self, sh, name: str):

        if not sh: return None

        try:

            return sh.worksheet(name)

        except WorksheetNotFound:

            return None



    def ensure(self, sh, tab: str):

        if not sh: return None

        try:

            return sh.worksheet(tab)

        except WorksheetNotFound:

            pass

        try:

            w = sh.add_worksheet(title=tab, rows=2000, cols=25)

            if tab in HDR:

                w.append_row(HDR[tab])

                self._fmt(w, tab)

            return w

        except Exception as e:

            logger.error(f"ensure({tab}): {e}")

            return None



    def _fmt(self, ws, tab: str):

        try:

            wid = ws.id

            n   = len(HDR.get(tab, []))

            r   = []

            r.append({"repeatCell": {

                "range": {"sheetId":wid,"startRowIndex":0,"endRowIndex":1,

                          "startColumnIndex":0,"endColumnIndex":n},

                "cell": {"userEnteredFormat": {

                    "backgroundColor":H_BG,

                    "textFormat":{"foregroundColor":H_FG,"bold":True,"fontSize":10},

                    "horizontalAlignment":"CENTER","verticalAlignment":"MIDDLE"}},

                "fields":"userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"}})

            r.append({"updateSheetProperties":{

                "properties":{"sheetId":wid,"gridProperties":{"frozenRowCount":1}},

                "fields":"gridProperties.frozenRowCount"}})

            r.append({"updateDimensionProperties":{

                "range":{"sheetId":wid,"dimension":"ROWS","startIndex":0,"endIndex":2000},

                "properties":{"pixelSize":22},"fields":"pixelSize"}})

            for i, px in enumerate(COL_W.get(tab, [])):

                if i >= n: break

                r.append({"updateDimensionProperties":{

                    "range":{"sheetId":wid,"dimension":"COLUMNS","startIndex":i,"endIndex":i+1},

                    "properties":{"pixelSize":px},"fields":"pixelSize"}})

            ws.spreadsheet.batch_update({"requests":r})

        except Exception as e:

            logger.warning(f"_fmt({tab}): {e}")



    def color_row(self, ws, row_idx: int, status: str):

        try:

            bg = ROW_C.get(str(status).lower())

            if not bg: return

            ws.spreadsheet.batch_update({"requests":[{"repeatCell":{

                "range":{"sheetId":ws.id,"startRowIndex":row_idx-1,"endRowIndex":row_idx,

                         "startColumnIndex":0,"endColumnIndex":ws.col_count},

                "cell":{"userEnteredFormat":{"backgroundColor":bg}},

                "fields":"userEnteredFormat.backgroundColor"}}]})

        except Exception as e:

            logger.warning(f"color_row: {e}")



    def rows(self, ws) -> list:

        try:

            data = ws.get_all_values()

            if len(data) < 2: return []

            hdr = data[0]

            out = []

            for row in data[1:]:

                while len(row) < len(hdr): row.append("")

                if any(v.strip() for v in row):

                    out.append(dict(zip(hdr, row)))

            return out

        except:

            return []



    def find(self, ws, col: int, val: str):

        try:

            data = ws.get_all_values()

            if not data: return None, None

            hdr = data[0]

            for i, row in enumerate(data[1:], start=2):

                while len(row) < len(hdr): row.append("")

                if row[col].strip() == str(val).strip():

                    return i, dict(zip(hdr, row))

        except: pass

        return None, None



    def update(self, ws, col: int, key: str, field: str, val) -> bool:

        try:

            data = ws.get_all_values()

            if not data: return False

            hdr = data[0]

            if field not in hdr: return False

            fc = hdr.index(field) + 1

            for i, row in enumerate(data[1:], start=2):

                if len(row) > col and row[col].strip() == str(key).strip():

                    ws.update_cell(i, fc, val)

                    return True

        except Exception as e:

            logger.error(f"update({field}): {e}")

        return False





db = DB()
# ── Sheet helpers ─────────────────────────────────────────────

def _aw():

    sh = db.master()

    return db.ensure(sh, "agents") if sh else None



def _lw():

    sh = db.master()

    return db.ensure(sh, "logs") if sh else None



def _qw():

    sh = db.master()

    return db.ensure(sh, "queue") if sh else None



def _asw():

    sh = db.master()

    return db.ensure(sh, "admin_settings") if sh else None



def _sw(agent: dict, tab: str):

    sn = agent.get("sheet_name", "")

    if not sn: return None

    sh = db.open(sn)

    return db.ensure(sh, tab) if sh else None





# ================================================================

# ADMIN SETTINGS

# ================================================================

def get_admin_setting(key: str) -> str:

    w = _asw()

    if not w: return ""

    for r in db.rows(w):

        if r.get("key","").strip() == key:

            return r.get("value","")

    return ""



def set_admin_setting(key: str, val: str) -> bool:

    w = _asw()

    if not w: return False

    rows = w.get_all_values()

    for i, row in enumerate(rows[1:], start=2):

        if row and row[0].strip() == key:

            w.update_cell(i, 2, val)

            return True

    w.append_row([key, val])

    return True



def get_admin_rate() -> float:

    return safe_float(get_admin_setting("rate_per_app"))



def get_admin_qr() -> str:

    return get_admin_setting("qr_file_id")





# ================================================================

# AGENTS

# ================================================================

def all_agents() -> list:

    w = _aw()

    return db.rows(w) if w else []



def agent_by_tid(tid: int):

    s = str(tid).strip()

    for a in all_agents():

        if str(a.get("telegram_id","")).strip() == s:

            return a

    return None



def agent_by_id(aid: str):

    for a in all_agents():

        if a.get("agent_id","").strip() == aid.strip():

            return a

    return None



def add_agent(data: dict) -> bool:

    try:

        w = _aw()

        if not w: return False

        row = [data["agent_id"], data["agent_name"], data["phone"],

               str(data["telegram_id"]), data["sheet_name"],

               data["rate"], "", now_ist(), "active", 0, 0, 0]

        w.append_row(row)

        n = len(w.get_all_values())

        db.color_row(w, n, "active")

        master_log("AGENT_ADDED", data["agent_name"], data["agent_id"])

        return True

    except Exception as e:

        logger.error(f"add_agent: {e}")

        return False



def set_agent_field(agent_id: str, field: str, val) -> bool:

    w = _aw()

    return db.update(w, 0, agent_id, field, val) if w else False



def remove_agent(agent_id: str) -> bool:

    try:

        w = _aw()

        if not w: return False

        ri, _ = db.find(w, 0, agent_id)

        if ri:

            w.delete_rows(ri)

            return True

    except Exception as e:

        logger.error(f"remove_agent: {e}")

    return False



def agent_active(agent: dict) -> bool:

    return str(agent.get("status","active")).strip() not in ("blocked","deleted")



def get_agent_balance(agent_id: str) -> float:

    for a in all_agents():

        if a.get("agent_id","") == agent_id:

            return safe_float(a.get("balance", 0))

    return 0.0



def add_agent_balance(agent_id: str, amount: float) -> bool:

    cur = get_agent_balance(agent_id)

    return set_agent_field(agent_id, "balance", round(cur + amount, 2))



def deduct_agent_balance(agent_id: str, amount: float) -> bool:

    cur = get_agent_balance(agent_id)

    if cur < amount: return False

    return set_agent_field(agent_id, "balance", round(cur - amount, 2))



def master_log(event: str, agent: str, detail: str):

    try:

        w = _lw()

        if w: w.append_row([event, agent, detail, now_ist()])

    except: pass





# ================================================================

# SETUP MANUAL SHEET

# ================================================================

def setup_manual_sheet(sheet_name: str, agent_id: str,

                       agent_name: str, rate: float) -> bool:

    sh = db.open(sheet_name)

    if not sh:

        logger.error(f"Sheet not found: {sheet_name}")

        return False

    for tab in ("clients","applications","payments","agent_payments","settings"):

        try:

            w = db.ws(sh, tab)

            if w is None:

                db.ensure(sh, tab)

            else:

                rows = w.get_all_values()

                if not rows or rows[0] != HDR[tab]:

                    w.clear()

                    w.append_row(HDR[tab])

                    db._fmt(w, tab)

        except Exception as e:

            logger.error(f"setup tab {tab}: {e}")

            return False

    try:

        sw   = db.ws(sh, "settings")

        keys = {r.get("key","") for r in db.rows(sw)}

        for k, v in [("rate_per_app",str(rate)),("qr_file_id",""),

                     ("agent_name",agent_name),("agent_id",agent_id)]:

            if k not in keys:

                sw.append_row([k, v])

    except Exception as e:

        logger.error(f"setup settings: {e}")

    return True





# ================================================================

# SETTINGS

# ================================================================

def get_setting(agent: dict, key: str) -> str:

    try:

        w = _sw(agent, "settings")

        if not w: return ""

        for r in db.rows(w):

            if r.get("key","").strip() == key:

                return r.get("value","")

    except: pass

    return ""



def put_setting(agent: dict, key: str, val: str) -> bool:

    try:

        w = _sw(agent, "settings")

        if not w: return False

        rows = w.get_all_values()

        for i, row in enumerate(rows[1:], start=2):

            if row and row[0].strip() == key:

                w.update_cell(i, 2, val)

                return True

        w.append_row([key, val])

        return True

    except Exception as e:

        logger.error(f"put_setting: {e}")

        return False





# ================================================================

# CLIENTS

# ================================================================

def all_clients(agent: dict) -> list:

    w = _sw(agent, "clients")

    return db.rows(w) if w else []



def find_client(tid: int):

    s = str(tid).strip()

    for ag in all_agents():

        if not agent_active(ag): continue

        for c in all_clients(ag):

            if str(c.get("telegram_id","")).strip() == s:

                return c, ag

    return {}, {}



def client_by_code(agent: dict, code: str):

    for c in all_clients(agent):

        if c.get("client_code","").strip() == code.strip():

            return c

    return None



def add_client(agent: dict, data: dict) -> bool:

    try:

        w = _sw(agent, "clients")

        if not w: return False

        row = [data["client_code"], data["full_name"],

               str(data["phone"]), str(data["telegram_id"]),

               now_ist(), "active", 0, 0]

        w.append_row(row)

        n = len(w.get_all_values())

        db.color_row(w, n, "active")

        try:

            cur = safe_int(agent.get("total_clients",0))

            set_agent_field(agent["agent_id"], "total_clients", cur+1)

        except: pass

        return True

    except Exception as e:

        logger.error(f"add_client: {e}")

        return False



def set_client_field(agent: dict, code: str, field: str, val) -> bool:

    w = _sw(agent, "clients")

    if not w: return False

    ok = db.update(w, 0, code, field, val)

    if ok and field == "status":

        ri, _ = db.find(w, 0, code)

        if ri: db.color_row(w, ri, str(val))

    return ok

def get_balance(agent: dict, code: str) -> float:

    w = _sw(agent, "clients")

    if not w: return 0.0

    _, row = db.find(w, 0, code)

    return safe_float(row.get("balance",0)) if row else 0.0



def add_balance(agent: dict, code: str, amount: float) -> bool:

    cur = get_balance(agent, code)

    return set_client_field(agent, code, "balance", round(cur+amount, 2))



def deduct_balance(agent: dict, code: str, amount: float) -> bool:

    cur = get_balance(agent, code)

    if cur < amount: return False

    return set_client_field(agent, code, "balance", round(cur-amount, 2))



def inc_client_apps(agent: dict, code: str):

    w = _sw(agent, "clients")

    if not w: return

    _, row = db.find(w, 0, code)

    if row:

        db.update(w, 0, code, "total_apps", safe_int(row.get("total_apps",0))+1)





# ================================================================

# QUEUE

# ================================================================

def queue_add(data: dict) -> bool:

    try:

        w = _qw()

        if not w: return False

        row = [data["queue_id"], data["app_no"], data["dob"], data["password"],

               data["client_code"], data["client_name"], str(data.get("client_tid","")),

               data["agent_id"], data["agent_name"], str(data.get("agent_tid","")),

               now_ist(), "PENDING", "", data.get("priority","normal")]

        w.append_row(row)

        n = len(w.get_all_values())

        db.color_row(w, n, "pending")

        return True

    except Exception as e:

        logger.error(f"queue_add: {e}")

        return False



def queue_all() -> list:

    w = _qw()

    return db.rows(w) if w else []



def queue_pending() -> list:

    items = [r for r in queue_all() if r.get("status","").upper() == "PENDING"]

    items.sort(key=lambda x: (0 if x.get("priority")=="high" else 1, x.get("submitted_at","")))

    return items



def queue_held_by_agent(agent_id: str) -> list:

    return [r for r in queue_all()

            if r.get("agent_id") == agent_id and r.get("status","").upper() == "HELD"]



def queue_mark_done(queue_id: str) -> bool:

    w = _qw()

    if not w: return False

    ok = db.update(w, 0, queue_id, "status", "DONE")

    db.update(w, 0, queue_id, "done_at", now_ist())

    if ok:

        ri, _ = db.find(w, 0, queue_id)

        if ri: db.color_row(w, ri, "done")

    return ok



def queue_mark_held(queue_id: str) -> bool:

    w = _qw()

    if not w: return False

    ok = db.update(w, 0, queue_id, "status", "HELD")

    if ok:

        ri, _ = db.find(w, 0, queue_id)

        if ri: db.color_row(w, ri, "held")

    return ok



def queue_release_held(agent_id: str) -> list:

    w = _qw()

    if not w: return []

    held     = queue_held_by_agent(agent_id)

    released = []

    for item in held:

        qid = item.get("queue_id","")

        if qid:

            db.update(w, 0, qid, "status", "PENDING")

            ri, _ = db.find(w, 0, qid)

            if ri: db.color_row(w, ri, "pending")

            released.append(item)

    return released



def queue_get(queue_id: str) -> dict:

    w = _qw()

    if not w: return {}

    _, row = db.find(w, 0, queue_id)

    return row or {}



def queue_today_count() -> dict:

    today = today_ist()

    items = [r for r in queue_all() if r.get("submitted_at","").startswith(today)]

    return {

        "total":   len(items),

        "pending": sum(1 for r in items if r.get("status","").upper() == "PENDING"),

        "done":    sum(1 for r in items if r.get("status","").upper() == "DONE"),

        "held":    sum(1 for r in items if r.get("status","").upper() == "HELD"),

    }





# ================================================================

# APPLICATIONS (agent sheet copy)

# ================================================================

def all_apps(agent: dict) -> list:

    w = _sw(agent, "applications")

    return db.rows(w) if w else []



def add_app(agent: dict, data: dict) -> bool:

    try:

        w = _sw(agent, "applications")

        if not w: return False

        row = [data["app_id"], data["app_no"], data["dob"], data["password"],

               data["client_code"], agent.get("agent_id",""), now_ist(), "PENDING", ""]

        w.append_row(row)

        n = len(w.get_all_values())

        db.color_row(w, n, "pending")

        try:

            cur = safe_int(agent.get("total_apps",0))

            set_agent_field(agent["agent_id"], "total_apps", cur+1)

        except: pass

        return True

    except Exception as e:

        logger.error(f"add_app: {e}")

        return False



def mark_app_done(agent: dict, app_id: str) -> bool:

    w = _sw(agent, "applications")

    if not w: return False

    ok = db.update(w, 0, app_id, "status", "DONE")

    db.update(w, 0, app_id, "done_at", now_ist())

    if ok:

        ri, _ = db.find(w, 0, app_id)

        if ri: db.color_row(w, ri, "done")

    return ok





# ================================================================

# CLIENT PAYMENTS (Client -> Agent)

# ================================================================

def all_payments(agent: dict) -> list:

    w = _sw(agent, "payments")

    return db.rows(w) if w else []



def add_payment(agent: dict, data: dict) -> bool:

    try:

        w = _sw(agent, "payments")

        if not w: return False

        now = datetime.now(IST)

        row = [data["pay_id"], data["client_code"], data["amount"],

               "PENDING", now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "", ""]

        w.append_row(row)

        n = len(w.get_all_values())

        db.color_row(w, n, "pending")

        return True

    except Exception as e:

        logger.error(f"add_payment: {e}")

        return False



def approve_payment(agent: dict, pay_id: str, by: str) -> bool:

    w = _sw(agent, "payments")

    if not w: return False

    db.update(w, 0, pay_id, "status", "PAID")

    db.update(w, 0, pay_id, "approved_by", by)

    db.update(w, 0, pay_id, "approved_at", now_ist())

    ri, _ = db.find(w, 0, pay_id)

    if ri: db.color_row(w, ri, "paid")

    return True



def reject_payment(agent: dict, pay_id: str) -> bool:

    w = _sw(agent, "payments")

    if not w: return False

    db.update(w, 0, pay_id, "status", "REJECTED")

    ri, _ = db.find(w, 0, pay_id)

    if ri: db.color_row(w, ri, "rejected")

    return True



def get_payment_amount(agent: dict, pay_id: str) -> float:

    for p in all_payments(agent):

        if p.get("payment_id") == pay_id:

            return safe_float(p.get("amount", 0))

    return 0.0





# ================================================================

# AGENT PAYMENTS (Agent -> Admin)

# ================================================================

def all_agent_payments(agent: dict) -> list:

    w = _sw(agent, "agent_payments")

    return db.rows(w) if w else []



def add_agent_payment(agent: dict, data: dict) -> bool:

    try:

        w = _sw(agent, "agent_payments")

        if not w: return False

        now = datetime.now(IST)

        row = [data["pay_id"], agent.get("agent_id",""), data["amount"],

               "PENDING", now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "", ""]

        w.append_row(row)

        n = len(w.get_all_values())

        db.color_row(w, n, "pending")

        return True

    except Exception as e:

        logger.error(f"add_agent_payment: {e}")

        return False



def approve_agent_payment(agent: dict, pay_id: str) -> bool:

    w = _sw(agent, "agent_payments")

    if not w: return False

    db.update(w, 0, pay_id, "status", "PAID")

    db.update(w, 0, pay_id, "approved_by", "admin")

    db.update(w, 0, pay_id, "approved_at", now_ist())

    ri, _ = db.find(w, 0, pay_id)

    if ri: db.color_row(w, ri, "paid")

    return True



def reject_agent_payment(agent: dict, pay_id: str) -> bool:

    w = _sw(agent, "agent_payments")

    if not w: return False

    db.update(w, 0, pay_id, "status", "REJECTED")

    ri, _ = db.find(w, 0, pay_id)

    if ri: db.color_row(w, ri, "rejected")

    return True



def get_agent_payment_amount(agent: dict, pay_id: str) -> float:

    for p in all_agent_payments(agent):

        if p.get("payment_id") == pay_id:

            return safe_float(p.get("amount", 0))

    return 0.0





# ================================================================

# DETECT ROLE

# ================================================================

def detect_role(tid: int) -> str:

    from config import SUPER_ADMIN_ID

    if tid == SUPER_ADMIN_ID: return "admin"

    if agent_by_tid(tid): return "agent"

    c, _ = find_client(tid)

    if c: return "client"

    return "unknown"





                    
