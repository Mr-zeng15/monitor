"""
公司数据库对接模块
连接公司 PostgreSQL 数据库，实时获取产量数据
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CompanyDatabase:
    """公司数据库连接管理器"""
    
    def __init__(self):
        self.config = getattr(settings, 'COMPANY_DB_CONFIG', {})
        self.connection = None
    
    def get_connection(self):
        """获取数据库连接"""
        if not self.config:
            raise Exception("未配置公司数据库连接信息")
        
        try:
            if self.connection is None or self.connection.closed:
                self.connection = psycopg2.connect(
                    host=self.config.get('HOST', 'localhost'),
                    port=self.config.get('PORT', 5432),
                    database=self.config.get('NAME', ''),
                    user=self.config.get('USER', ''),
                    password=self.config.get('PASSWORD', ''),
                    cursor_factory=RealDictCursor
                )
            return self.connection
        except Exception as e:
            logger.error(f"连接公司数据库失败: {e}")
            raise
    
    def close(self):
        """关闭连接"""
        if self.connection and not self.connection.closed:
            self.connection.close()
    
    def execute_query(self, query, params=None):
        """执行查询"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            self.close()  # 连接可能已断开，关闭重连
            raise
    
    def get_production_data(self, product_code, date):
        """
        获取指定产品在指定日期的产量
        这里需要根据公司实际数据库表结构调整 SQL
        
        示例：假设公司数据库有 production_table 表
        """
        query = """
            SELECT 
                product_code,
                production_date,
                SUM(quantity) as total_quantity
            FROM production_table
            WHERE product_code = %s 
                AND production_date = %s
            GROUP BY product_code, production_date
        """
        result = self.execute_query(query, (product_code, date))
        return result[0] if result else None
    
    def get_monthly_production(self, product_code, year, month):
        """
        获取指定产品在指定月份的总产量
        """
        query = """
            SELECT 
                product_code,
                EXTRACT(YEAR FROM production_date) as year,
                EXTRACT(MONTH FROM production_date) as month,
                SUM(quantity) as total_quantity
            FROM production_table
            WHERE product_code = %s 
                AND EXTRACT(YEAR FROM production_date) = %s
                AND EXTRACT(MONTH FROM production_date) = %s
            GROUP BY product_code, year, month
        """
        result = self.execute_query(query, (product_code, year, month))
        return result[0] if result else None


# 全局实例
company_db = CompanyDatabase()
