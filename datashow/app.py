# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, send_from_directory
import pandas as pd
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DATABASE'] = 'datashow.db'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS test_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        region TEXT,
        test_time TEXT,
        production_date TEXT,
        test_type TEXT,
        executor TEXT,
        project_name TEXT,
        transaction_code TEXT,
        transaction_name TEXT,
        is_baffle_test TEXT,
        test_env_config TEXT,
       压测参数 TEXT,
        tps REAL,
        response_time REAL,
        error_rate REAL,
        anomaly_description TEXT,
        optimized_response_time TEXT
    )''')
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_float(value, default=0):
    try:
        if value == '' or value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def import_excel_to_db(filepath):
    try:
        df = pd.read_excel(filepath, engine='openpyxl')
        df = df.fillna('')
        
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('DELETE FROM test_data')
        
        for _, row in df.iterrows():
            if str(row.get('地区', '')).strip() == '':
                continue
            c.execute('''INSERT INTO test_data (
                region, test_time, production_date, test_type, executor,
                project_name, transaction_code, transaction_name, is_baffle_test,
                test_env_config,压测参数, tps, response_time, error_rate,
                anomaly_description, optimized_response_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    str(row.get('地区', '')),
                    str(row.get('测试时间', '')),
                    str(row.get('投产日期', '')),
                    str(row.get('测试类型\n(专项/常规)', '')),
                    str(row.get('测试执行人\n(负责人姓名)', '')),
                    str(row.get('项目名称', '')),
                    str(row.get('交易码', '')),
                    str(row.get('交易名称', '')),
                    str(row.get('是否加挡板测试', '')),
                    str(row.get('测试环境及配置', '')),
                    str(row.get('压测参数', '')),
                    safe_float(row.get('TPS', 0)),
                    safe_float(row.get('响应时间', 0)),
                    safe_float(row.get('错误率', 0)),
                    str(row.get('测试指标异常说明', '')),
                    str(row.get('优化前后响应时间', ''))
                ))
        
        conn.commit()
        conn.close()
        return True, "导入成功"
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    offset = (page - 1) * limit
    
    filters = {}
    if request.args.get('region'):
        filters['region'] = request.args.get('region')
    if request.args.get('project_name'):
        filters['project_name'] = request.args.get('project_name')
    if request.args.get('transaction_name'):
        filters['transaction_name'] = request.args.get('transaction_name')
    
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = 'SELECT * FROM test_data WHERE 1=1'
    params = []
    
    for key, value in filters.items():
        if value:
            query += f' AND {key} LIKE ?'
            params.append(f'%{value}%')
    
    c.execute('SELECT COUNT(*) ' + query[15:], params)
    total = c.fetchone()[0]
    
    query += ' ORDER BY id DESC LIMIT ? OFFSET ?'
    c.execute(query, params + [limit, offset])
    rows = c.fetchall()
    
    data = [dict(row) for row in rows]
    conn.close()
    
    return jsonify({'total': total, 'data': data})

@app.route('/api/import', methods=['POST'])
def import_data():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        success, message = import_excel_to_db(filepath)
        
        if success or '成功' in message:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    
    return jsonify({'success': False, 'message': '不支持的文件格式'})

@app.route('/api/edit', methods=['POST'])
def edit_data():
    data = request.json
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    
    c.execute('''UPDATE test_data SET
        region=?, test_time=?, production_date=?, test_type=?, executor=?,
        project_name=?, transaction_code=?, transaction_name=?, is_baffle_test=?,
        test_env_config=?,压测参数=?, tps=?, response_time=?, error_rate=?,
        anomaly_description=?, optimized_response_time=?
        WHERE id=?''',
        (
            data.get('region'), data.get('test_time'), data.get('production_date'),
            data.get('test_type'), data.get('executor'), data.get('project_name'),
            data.get('transaction_code'), data.get('transaction_name'),
            data.get('is_baffle_test'), data.get('test_env_config'),
            data.get('压测参数'), data.get('tps'), data.get('response_time'),
            data.get('error_rate'), data.get('anomaly_description'),
            data.get('optimized_response_time'), data.get('id')
        ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': '更新成功'})

@app.route('/api/batch-query', methods=['POST'])
def batch_query():
    data = request.json
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'success': False, 'message': '请选择要查询的数据'})
    
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    placeholders = ','.join('?' * len(ids))
    c.execute(f'SELECT * FROM test_data WHERE id IN ({placeholders})', ids)
    rows = c.fetchall()
    
    result = [dict(row) for row in rows]
    conn.close()
    
    return jsonify({'success': True, 'data': result})

@app.route('/api/stats')
def get_stats():
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM test_data')
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT project_name) FROM test_data WHERE project_name != ''")
    projects = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT region) FROM test_data WHERE region != ''")
    regions = c.fetchone()[0]
    
    c.execute('SELECT AVG(tps) FROM test_data WHERE tps > 0')
    avg_tps = c.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total': total,
        'projects': projects,
        'regions': regions,
        'avg_tps': round(avg_tps, 2)
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
