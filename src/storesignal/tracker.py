"""Resolution tracker (SQLite): Detected -> Reviewed -> Assigned -> Action
taken -> Resolved, with an event audit trail and reviewer feedback."""
import datetime as dt
import json
import sqlite3

from .config import ROOT, cfg

STATUSES = ['Detected', 'Reviewed', 'Assigned', 'Action taken', 'Resolved']
VERDICTS = ['correct', 'incorrect', 'duplicate', 'already_resolved', 'misrouted']


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def connect():
    processed = ROOT / cfg['paths']['processed']
    processed.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(processed / 'tracker.sqlite')


def init_db(con):
    con.execute('''CREATE TABLE IF NOT EXISTS alerts (
      alert_id TEXT PRIMARY KEY, tier TEXT, store_id TEXT, region TEXT, issue TEXT,
      severity TEXT, owner TEXT, status TEXT DEFAULT 'Detected', alert_ts TEXT,
      sla_due TEXT, payload_json TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id TEXT, ts TEXT, actor TEXT,
      from_status TEXT, to_status TEXT, note TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS feedback (
      id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id TEXT, ts TEXT, reviewer TEXT,
      verdict TEXT, note TEXT)''')
    con.commit()
    return con


def upsert_alert(con, a):
    alert_ts = a['alert_ts']
    if hasattr(alert_ts, 'isoformat'):
        alert_ts = alert_ts.isoformat()
    due = (dt.datetime.fromisoformat(alert_ts.replace('Z', '+00:00'))
           + dt.timedelta(hours=a.get('sla_hours', 72))).isoformat()
    con.execute('''INSERT OR IGNORE INTO alerts
      (alert_id, tier, store_id, region, issue, severity, owner, alert_ts, sla_due, payload_json)
      VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (a['alert_id'], a['tier'], str(a['store_id']), a.get('region', 'Unknown'),
                 a['issue'], a['severity'], a['owner'], alert_ts, due, json.dumps(a, default=str)))
    con.commit()


def set_status(con, alert_id, to_status, actor, note=''):
    cur = con.execute('SELECT status FROM alerts WHERE alert_id=?', (alert_id,)).fetchone()
    if cur is None:
        raise KeyError(alert_id)
    con.execute('UPDATE alerts SET status=? WHERE alert_id=?', (to_status, alert_id))
    con.execute('''INSERT INTO events (alert_id, ts, actor, from_status, to_status, note)
      VALUES (?,?,?,?,?,?)''', (alert_id, now(), actor, cur[0], to_status, note))
    con.commit()


def override_owner(con, alert_id, new_owner, actor, reason):
    cur = con.execute('SELECT owner, status FROM alerts WHERE alert_id=?', (alert_id,)).fetchone()
    if cur is None:
        raise KeyError(alert_id)
    con.execute('UPDATE alerts SET owner=? WHERE alert_id=?', (new_owner, alert_id))
    con.execute('''INSERT INTO events (alert_id, ts, actor, from_status, to_status, note)
      VALUES (?,?,?,?,?,?)''',
                (alert_id, now(), actor, cur[1], cur[1], 'owner %s -> %s: %s' % (cur[0], new_owner, reason)))
    con.commit()


def add_feedback(con, alert_id, reviewer, verdict, note=''):
    con.execute('INSERT INTO feedback (alert_id, ts, reviewer, verdict, note) VALUES (?,?,?,?,?)',
                (alert_id, now(), reviewer, verdict, note))
    con.commit()


def overdue(con):
    return con.execute(
        "SELECT alert_id, owner, sla_due FROM alerts WHERE status != 'Resolved' AND sla_due < ?",
        (now(),)).fetchall()


def open_alerts(con):
    return con.execute("SELECT * FROM alerts WHERE status != 'Resolved' ORDER BY sla_due").fetchall()
