


from flask import Flask, request, render_template, jsonify
import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime

app = Flask(__name__)
load_dotenv()


# 数据库配置（保持不变）
def get_db_config():
    return {
        'host': os.getenv('DB1_HOST', 'localhost'),
        'port': int(os.getenv('DB1_PORT', '3306')),
        'user': os.getenv('DB1_USER', 'root'),
        'password': os.getenv('DB1_PASS', ''),
        'database': 'data_insight'
    }


def get_db_connection():
    config = get_db_config()
    return mysql.connector.connect(**config)


# 核心路由
@app.route('/')
def index():
    return render_template('form.html')


@app.route('/search', methods=['POST'])
def search():
    region = request.form.get('region')
    style_code = request.form.get('style_code')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                listed_date, order_data, sales_data,
                inventory_data, stocked_orders, out_quantity,
                later_sales, avg_sales
            FROM `21-要货收集表`
            WHERE region = %s AND style_code = %s
        """, (region, style_code))
        result = cursor.fetchone() or {}
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    try:
        # 校验必要字段
        required_fields = ['submit_date', 'region', 'style_code', 'demand_qty', 'estimated_cycle', 'listed_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'message': f'字段 {field} 缺失'}), 400

        # 解析日期
        try:
            listed_date = datetime.strptime(data['listed_date'], '%Y-%m-%d')
            submit_date = datetime.strptime(data['submit_date'], '%Y-%m-%d')
        except ValueError as e:
            return jsonify({'status': 'error', 'message': f'日期格式错误: {e}'}), 400

        # 计算阶段
        diff_days = (submit_date - listed_date).days
        stage = '爆发阶段'
        if diff_days < -28:
            stage = '锁单阶段'
        elif -28 <= diff_days <= -14:
            stage = '锁客阶段'

        # 计算信用分（防止除零）
        demand_qty = int(data['demand_qty'])
        if demand_qty <= 0:
            demand_qty = 1
        later_sales = int(data.get('later_sales', 0))
        ratio = later_sales / demand_qty

        credit = 10
        if stage == '锁单阶段':
            credit += (ratio - 0.65) // 0.05
        elif stage == '锁客阶段':
            credit += (ratio - 0.75) // 0.05
        else:
            credit += (ratio - 0.85) // 0.05
        credit = max(int(credit), 0)

        # 插入数据库
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO collected_data (
                submit_date, region, style_code, demand_qty, estimated_cycle,
                listed_date, order_data, sales_data, inventory_data,
                stocked_orders, later_sales, avg_sales, out_quantity, stage, credit
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['submit_date'],
            data['region'],
            data['style_code'],
            demand_qty,
            data['estimated_cycle'],
            data['listed_date'],
            data.get('order_data', 0),
            data.get('sales_data', 0),
            data.get('inventory_data', 0),
            data.get('stocked_orders', 0),
            later_sales,
            data.get('avg_sales', 0),
            data.get('out_quantity', 0),
            stage,
            credit
        ))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"❌ 提交错误详情: {str(e)}")
        print(f"❌ 错误发生时的数据: {data}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/get_records')
def get_records():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM collected_data ORDER BY id DESC")
        records = cursor.fetchall()
        conn.close()

        # 格式化日期字段
        for record in records:
            # 处理 submit_date
            if isinstance(record.get('submit_date'), datetime):
                record['submit_date'] = record['submit_date'].strftime('%Y-%m-%d')
            # 处理 listed_date
            if isinstance(record.get('listed_date'), datetime):
                record['listed_date'] = record['listed_date'].strftime('%Y-%m-%d')
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)





