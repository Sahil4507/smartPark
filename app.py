from flask import Flask, request, jsonify, send_from_directory
import mysql.connector
from datetime import datetime

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'sql-username',
    'password': 'sql-password',
    'database': 'smartpark'
}

def get_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS slots (
            id INT AUTO_INCREMENT PRIMARY KEY,
            slot_number VARCHAR(10) UNIQUE NOT NULL,
            is_occupied TINYINT(1) DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            vehicle_number VARCHAR(20) NOT NULL,
            slot_number VARCHAR(10) NOT NULL,
            entry_time DATETIME NOT NULL,
            exit_time DATETIME,
            active_vehicle VARCHAR(20) GENERATED ALWAYS AS (IF(exit_time IS NULL, vehicle_number, NULL)) STORED,
            active_slot VARCHAR(10) GENERATED ALWAYS AS (IF(exit_time IS NULL, slot_number, NULL)) STORED,
            UNIQUE INDEX uq_one_active_per_vehicle (active_vehicle),
            UNIQUE INDEX uq_one_active_per_slot (active_slot)
        )
    ''')

    # ── Triggers ─────────────────────────────────────────────────────────────

    c.execute('DROP TRIGGER IF EXISTS after_insert_record')
    c.execute('''
        CREATE TRIGGER after_insert_record
        AFTER INSERT ON records
        FOR EACH ROW
        BEGIN
            UPDATE slots
            SET is_occupied = 1
            WHERE slot_number = NEW.slot_number;
        END
    ''')

    c.execute('DROP TRIGGER IF EXISTS after_update_record')
    c.execute('''
        CREATE TRIGGER after_update_record
        AFTER UPDATE ON records
        FOR EACH ROW
        BEGIN
            IF NEW.exit_time IS NOT NULL THEN
                UPDATE slots
                SET is_occupied = 0
                WHERE slot_number = NEW.slot_number;
            END IF;
        END
    ''')

    c.execute('DROP TRIGGER IF EXISTS after_delete_record')
    c.execute('''
        CREATE TRIGGER after_delete_record
        AFTER DELETE ON records
        FOR EACH ROW
        BEGIN
            UPDATE slots
            SET is_occupied = 0
            WHERE slot_number = OLD.slot_number;
        END
    ''')
    # ─────────────────────────────────────────────────────────────────────────

    c.execute('SELECT COUNT(*) FROM slots')
    if c.fetchone()[0] == 0:
        slots = []
        for row in 'ABCD':
            for col in range(1, 17):
                slots.append((f'{row}{col}',))
        for row in 'EFG':
            for col in range(1, 21):
                slots.append((f'{row}{col}',))
        c.executemany('INSERT INTO slots (slot_number) VALUES (%s)', slots)

    conn.commit()
    c.close()
    conn.close()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/index.css')
def css():
    return send_from_directory('.', 'index.css')

@app.route('/index.js')
def js():
    return send_from_directory('.', 'index.js')

@app.route('/slots', methods=['GET'])
def get_slots():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute('SELECT slot_number, is_occupied FROM slots ORDER BY slot_number')
    slots = c.fetchall()
    c.close()
    conn.close()
    return jsonify(slots)

@app.route('/records', methods=['GET'])
def get_records():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute('SELECT * FROM records ORDER BY id DESC')
    records = c.fetchall()
    c.close()
    conn.close()
    result = []
    for r in records:
        r['entry_time'] = r['entry_time'].strftime('%Y-%m-%d %H:%M:%S') if r['entry_time'] else ''
        r['exit_time'] = r['exit_time'].strftime('%Y-%m-%d %H:%M:%S') if r['exit_time'] else 'Still parked'
        result.append(r)
    return jsonify(result)

@app.route('/assign', methods=['POST'])
def assign_slot():
    data = request.get_json()
    vehicle = data.get('vehicle_number', '').strip().upper()
    slot_number = data.get('slot_number', '').strip().upper()

    if not vehicle:
        return jsonify({'error': 'Vehicle number required.'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)

    try:
        if slot_number:
            c.execute('SELECT slot_number FROM slots WHERE slot_number = %s', (slot_number,))
            if not c.fetchone():
                return jsonify({'error': f'Slot {slot_number} does not exist.'}), 400
            slot = slot_number
        else:
            c.execute('SELECT slot_number FROM slots WHERE is_occupied = 0 ORDER BY slot_number LIMIT 1')
            free = c.fetchone()
            if not free:
                return jsonify({'error': 'No free slots available.'}), 400
            slot = free['slot_number']

        now = datetime.now()
        c.execute(
            'INSERT INTO records (vehicle_number, slot_number, entry_time) VALUES (%s, %s, %s)',
            (vehicle, slot, now)
        )
        conn.commit()
        return jsonify({'message': f'{vehicle} assigned to slot {slot}.'})

    except mysql.connector.IntegrityError as e:
        conn.rollback()
        msg = str(e)
        if 'uq_one_active_per_vehicle' in msg:
            return jsonify({'error': f'{vehicle} is already parked.'}), 400
        if 'uq_one_active_per_slot' in msg:
            return jsonify({'error': f'Slot {slot} is already occupied.'}), 400
        return jsonify({'error': 'Database integrity error.'}), 400
    finally:
        c.close()
        conn.close()

@app.route('/release', methods=['POST'])
def release_slot():
    data = request.get_json()
    vehicle = data.get('vehicle_number', '').strip().upper()
    if not vehicle:
        return jsonify({'error': 'Vehicle number required.'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)

    try:
        c.execute('SELECT * FROM records WHERE vehicle_number = %s AND exit_time IS NULL', (vehicle,))
        record = c.fetchone()
        if not record:
            return jsonify({'error': f'{vehicle} not found in active records.'}), 404

        now = datetime.now()
        c.execute('UPDATE records SET exit_time = %s WHERE id = %s', (now, record['id']))
        conn.commit()
        return jsonify({'message': f'{vehicle} released from slot {record["slot_number"]}.'})

    except Exception as e:
        conn.rollback()
        return jsonify({'error': 'Database error: ' + str(e)}), 500
    finally:
        c.close()
        conn.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)