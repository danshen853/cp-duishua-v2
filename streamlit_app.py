import pandas as pd
import numpy as np
import streamlit as st
import io
import re
import logging
from collections import defaultdict
from datetime import datetime
from itertools import combinations
import warnings
import traceback
import tempfile
import os
import base64

# 配置日志和警告
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('LotteryAnalysis')

# 设置页面配置
st.set_page_config(
    page_title="智能彩票分析系统",
    page_icon="🌎",
    layout="wide",
    initial_sidebar_state="expanded"
)

class Config:
    """配置参数类"""
    def __init__(self):
        self.min_amount = 10
        self.amount_similarity_threshold = 0.9
        self.min_continuous_periods = 3
        self.max_accounts_in_group = 5
        self.supported_file_types = ['.xlsx', '.xls', '.csv']
        
        # 列名映射配置
        self.column_mappings = {
            '会员账号': ['会员账号', '会员账户', '账号', '账户', '用户账号'],
            '彩种': ['彩种', '彩票种类', '游戏类型'],
            '期号': ['期号', '期数', '期次', '期'],
            '玩法': ['玩法', '玩法分类', '投注类型', '类型'],
            '内容': ['内容', '投注内容', '下注内容', '注单内容'],
            '金额': ['金额', '下注总额', '投注金额', '总额', '下注金额']
        }
        
        # 根据账户投注期数设置不同的对刷期数阈值
        self.period_thresholds = {
            'low_activity': 10,
            'min_periods_low': 3,
            'min_periods_high': 5
        }
        
        self.direction_patterns = {
            '小': ['两面-小', '和值-小', '小', 'small', 'xia'],
            '大': ['两面-大', '和值-大', '大', 'big', 'da'], 
            '单': ['两面-单', '和值-单', '单', 'odd', 'dan'],
            '双': ['两面-双', '和值-双', '双', 'even', 'shuang']
        }
        
        self.opposite_groups = [{'大', '小'}, {'单', '双'}]

class MultiAccountAnalyzer:
    """多账户关联分析模块"""
    def __init__(self, config):
        self.config = config
        self.module_loaded = True
    
    def analyze_multi_account(self, df_valid):
        """多账户关联分析主函数"""
        try:
            if not self.module_loaded:
                return "❌ 多账户分析模块未正确加载"
            
            st.info("🔍 开始多账户关联分析...")
            
            # 完整的多账户关联分析逻辑
            results = self.detect_wash_trades(df_valid)
            correlation_results = self.analyze_account_correlations(df_valid)
            pattern_results = self.detect_suspicious_patterns(df_valid)
            
            return f"{results}\n\n{correlation_results}\n\n{pattern_results}"
            
        except Exception as e:
            error_msg = f"多账户分析错误: {str(e)}"
            st.error(error_msg)
            return error_msg
    
    def detect_wash_trades(self, df_valid):
        """检测对刷交易 - 核心逻辑"""
        try:
            if df_valid is None or len(df_valid) == 0:
                return "❌ 没有有效数据可用于分析"
            
            # 完整的对刷检测逻辑
            wash_trade_results = []
            
            # 按期号分析
            period_groups = df_valid.groupby('期号')
            
            for period, period_data in period_groups:
                # 检测同一期内的对刷行为
                period_wash_trades = self._detect_period_wash_trades(period_data)
                wash_trade_results.extend(period_wash_trades)
            
            # 账户行为分析
            account_behavior = self._analyze_account_behavior(df_valid)
            
            result_text = "📊 多账户分析结果 - 对刷交易检测\n"
            result_text += "=" * 50 + "\n"
            result_text += f"分析账户数量: {df_valid['会员账号'].nunique()}\n"
            result_text += f"总投注记录: {len(df_valid)}\n"
            result_text += f"唯一期号数: {df_valid['期号'].nunique()}\n"
            result_text += f"检测到可疑对刷模式: {len(wash_trade_results)} 个\n\n"
            
            # 显示对刷检测结果
            if wash_trade_results:
                result_text += "🚨 可疑对刷交易:\n"
                for i, trade in enumerate(wash_trade_results[:10], 1):
                    result_text += f"  {i}. 期号: {trade['period']} | 账户组: {trade['accounts']} | 模式: {trade['pattern']}\n"
            
            return result_text
            
        except Exception as e:
            return f"对刷检测错误: {str(e)}"
    
    def _detect_period_wash_trades(self, period_data):
        """检测单期内的对刷交易"""
        wash_trades = []
        
        try:
            # 按投注方向分组
            direction_groups = period_data.groupby('投注方向')
            directions = list(direction_groups.groups.keys())
            
            # 检查对立投注方向
            for dir1, dir2 in self.config.opposite_groups:
                if dir1 in directions and dir2 in directions:
                    dir1_data = direction_groups.get_group(dir1)
                    dir2_data = direction_groups.get_group(dir2)
                    
                    # 检测金额相似的投注
                    for _, bet1 in dir1_data.iterrows():
                        for _, bet2 in dir2_data.iterrows():
                            amount1 = bet1['投注金额']
                            amount2 = bet2['投注金额']
                            
                            # 检查金额相似度
                            if self._is_amount_similar(amount1, amount2):
                                wash_trades.append({
                                    'period': bet1['期号'],
                                    'accounts': f"{bet1['会员账号']} vs {bet2['会员账号']}",
                                    'pattern': f"{dir1}({amount1}) vs {dir2}({amount2})",
                                    'amount1': amount1,
                                    'amount2': amount2
                                })
            
            return wash_trades
            
        except Exception as e:
            st.error(f"单期对刷检测错误: {str(e)}")
            return []
    
    def _is_amount_similar(self, amount1, amount2):
        """检查金额是否相似"""
        if amount1 == 0 or amount2 == 0:
            return False
        
        ratio = min(amount1, amount2) / max(amount1, amount2)
        return ratio >= self.config.amount_similarity_threshold
    
    def _analyze_account_behavior(self, df_valid):
        """分析账户行为模式"""
        try:
            account_stats = df_valid.groupby('会员账号').agg({
                '投注金额': ['count', 'sum', 'mean', 'std'],
                '期号': 'nunique',
                '彩种': 'nunique'
            }).round(2)
            
            # 计算活跃度指标
            account_stats['活跃度'] = account_stats[('投注金额', 'count')] / account_stats[('期号', 'nunique')]
            account_stats['平均每期金额'] = account_stats[('投注金额', 'sum')] / account_stats[('期号', 'nunique')]
            
            return account_stats
            
        except Exception as e:
            st.error(f"账户行为分析错误: {str(e)}")
            return pd.DataFrame()
    
    def analyze_account_correlations(self, df_valid):
        """分析账户关联性"""
        try:
            # 账户共现分析（在同一期出现）
            period_accounts = df_valid.groupby('期号')['会员账号'].apply(set)
            
            correlation_pairs = []
            account_pairs = combinations(df_valid['会员账号'].unique(), 2)
            
            for acc1, acc2 in account_pairs:
                co_occurrence = sum(1 for accounts in period_accounts if acc1 in accounts and acc2 in accounts)
                total_periods = sum(1 for accounts in period_accounts if acc1 in accounts or acc2 in accounts)
                
                if total_periods > 0:
                    correlation = co_occurrence / total_periods
                    if correlation > 0.7:  # 高关联度阈值
                        correlation_pairs.append({
                            'account1': acc1,
                            'account2': acc2,
                            'correlation': correlation,
                            'co_occurrence': co_occurrence
                        })
            
            result_text = "🔗 账户关联性分析\n"
            result_text += "=" * 30 + "\n"
            result_text += f"检测到高关联账户对: {len(correlation_pairs)} 对\n"
            
            for pair in correlation_pairs[:5]:
                result_text += f"  {pair['account1']} ↔ {pair['account2']} | 关联度: {pair['correlation']:.2f}\n"
            
            return result_text
            
        except Exception as e:
            return f"账户关联分析错误: {str(e)}"
    
    def detect_suspicious_patterns(self, df_valid):
        """检测可疑模式"""
        try:
            suspicious_accounts = []
            
            # 分析每个账户的模式
            for account in df_valid['会员账号'].unique():
                account_data = df_valid[df_valid['会员账号'] == account]
                
                # 检查投注模式
                if self._is_suspicious_account(account_data):
                    suspicious_accounts.append(account)
            
            result_text = "🚨 可疑账户模式检测\n"
            result_text += "=" * 30 + "\n"
            result_text += f"检测到可疑模式账户: {len(suspicious_accounts)} 个\n"
            
            for account in suspicious_accounts[:10]:
                result_text += f"  ⚠️ {account}\n"
            
            return result_text
            
        except Exception as e:
            return f"可疑模式检测错误: {str(e)}"
    
    def _is_suspicious_account(self, account_data):
        """判断账户是否可疑"""
        try:
            # 检查条件
            total_bets = len(account_data)
            total_amount = account_data['投注金额'].sum()
            periods_count = account_data['期号'].nunique()
            
            # 高频率投注
            high_frequency = total_bets > periods_count * 5
            
            # 大额投注
            large_bets = total_amount > 10000
            
            # 单一方向偏好
            direction_counts = account_data['投注方向'].value_counts()
            single_direction_bias = len(direction_counts) == 1 and direction_counts.iloc[0] > total_bets * 0.8
            
            return high_frequency or large_bets or single_direction_bias
            
        except Exception as e:
            return False

class SpecialCodeAnalyzer:
    """特码完美覆盖分析模块"""
    def __init__(self, config):
        self.config = config
        self.module_loaded = True
    
    def analyze_special_code(self, df_valid):
        """特码完美覆盖分析"""
        try:
            if not self.module_loaded:
                return "❌ 特码分析模块未正确加载"
            
            st.info("🔍 开始特码完美覆盖分析...")
            
            # 筛选特码相关投注
            special_bets = df_valid[df_valid['内容'].str.contains('特码|特马|特号', na=False)]
            
            if len(special_bets) == 0:
                return "❌ 未找到特码相关投注记录"
            
            # 完整分析
            coverage_analysis = self._analyze_coverage_patterns(special_bets)
            account_analysis = self._analyze_special_code_accounts(special_bets)
            period_analysis = self._analyze_special_code_periods(special_bets)
            
            return f"{coverage_analysis}\n\n{account_analysis}\n\n{period_analysis}"
            
        except Exception as e:
            return f"特码分析错误: {str(e)}"
    
    def _analyze_coverage_patterns(self, special_bets):
        """分析覆盖模式"""
        try:
            # 提取特码数字
            special_bets = special_bets.copy()
            special_bets['特码数字'] = special_bets['内容'].apply(self._extract_special_numbers)
            
            # 分析数字分布
            all_numbers = []
            for numbers in special_bets['特码数字'].dropna():
                all_numbers.extend(numbers)
            
            number_distribution = pd.Series(all_numbers).value_counts().sort_index()
            
            result_text = "🎯 特码完美覆盖分析结果\n"
            result_text += "=" * 50 + "\n"
            result_text += f"特码投注记录数: {len(special_bets)}\n"
            result_text += f"涉及账户数: {special_bets['会员账号'].nunique()}\n"
            result_text += f"涉及期号数: {special_bets['期号'].nunique()}\n\n"
            
            # 金额统计
            total_amount = special_bets['投注金额'].sum()
            avg_amount = special_bets['投注金额'].mean()
            result_text += f"特码总投注金额: {total_amount:.2f} 元\n"
            result_text += f"平均每注金额: {avg_amount:.2f} 元\n\n"
            
            # 数字覆盖分析
            result_text += "🔢 特码数字覆盖分析:\n"
            coverage_rate = len(number_distribution) / 49  # 假设49个数字
            result_text += f"数字覆盖度: {coverage_rate:.1%} ({len(number_distribution)}/49)\n"
            
            # 显示最常投注的数字
            if len(number_distribution) > 0:
                result_text += "最常投注特码(前10):\n"
                for num, count in number_distribution.head(10).items():
                    result_text += f"  数字 {num}: {count} 次\n"
            
            return result_text
            
        except Exception as e:
            return f"覆盖模式分析错误: {str(e)}"
    
    def _extract_special_numbers(self, content):
        """从内容中提取特码数字"""
        try:
            if pd.isna(content):
                return []
            
            content_str = str(content)
            numbers = []
            
            # 多种数字提取模式
            patterns = [
                r'特[码马号]\s*(\d{1,2})',
                r'特\s*(\d{1,2})',
                r'(\d{1,2})\s*特',
                r'特码[：:]\s*(\d{1,2})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content_str)
                numbers.extend([int(match) for match in matches if match.isdigit()])
            
            # 去重并返回
            return list(set(numbers))
            
        except Exception as e:
            return []
    
    def _analyze_special_code_accounts(self, special_bets):
        """分析特码投注账户"""
        try:
            # 账户排名
            top_accounts = special_bets.groupby('会员账号').agg({
                '投注金额': ['sum', 'count', 'mean'],
                '期号': 'nunique'
            }).round(2)
            
            # 重命名列
            top_accounts.columns = ['总金额', '投注次数', '平均金额', '参与期数']
            top_accounts = top_accounts.sort_values('总金额', ascending=False)
            
            result_text = "🏆 特码投注账户排名:\n"
            for account, row in top_accounts.head(10).iterrows():
                result_text += f"  {account} | 总金额: {row['总金额']:.2f} | 注数: {row['投注次数']} | 期数: {row['参与期数']}\n"
            
            return result_text
            
        except Exception as e:
            return f"账户分析错误: {str(e)}"
    
    def _analyze_special_code_periods(self, special_bets):
        """分析特码投注期号分布"""
        try:
            period_stats = special_bets.groupby('期号').agg({
                '投注金额': ['sum', 'count'],
                '会员账号': 'nunique'
            }).round(2)
            
            period_stats.columns = ['期总金额', '期注数', '期账户数']
            period_stats = period_stats.sort_values('期总金额', ascending=False)
            
            result_text = "📅 特码投注期号分析:\n"
            result_text += f"最高投注期: {period_stats.index[0]} (金额: {period_stats.iloc[0]['期总金额']:.2f})\n"
            result_text += f"平均每期特码投注: {period_stats['期总金额'].mean():.2f} 元\n"
            
            return result_text
            
        except Exception as e:
            return f"期号分析错误: {str(e)}"

class LotteryAnalysisSystem:
    """彩票分析系统主类"""
    def __init__(self):
        self.config = Config()
        self.multi_analyzer = MultiAccountAnalyzer(self.config)
        self.special_analyzer = SpecialCodeAnalyzer(self.config)
        self.data_processed = False
        self.df_valid = None
    
    def process_uploaded_file(self, uploaded_file):
        """处理上传的文件"""
        try:
            if uploaded_file is None:
                return "❌ 没有上传文件", None
            
            filename = uploaded_file.name
            logger.info(f"✅ 已上传文件: {filename}")
            
            if not any(filename.endswith(ext) for ext in self.config.supported_file_types):
                return f"❌ 不支持的文件类型: {filename}", None
            
            # 读取文件内容
            file_content = uploaded_file.read()
            
            if filename.endswith('.csv'):
                # 尝试多种编码
                encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
                for encoding in encodings:
                    try:
                        df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    return "❌ 无法解码CSV文件，请检查文件编码", None
            else:
                df = pd.read_excel(io.BytesIO(file_content))
            
            logger.info(f"原始数据维度: {df.shape}")
            return df, filename
            
        except Exception as e:
            logger.error(f"文件处理失败: {str(e)}")
            return f"❌ 文件处理失败: {str(e)}", None
    
    def preprocess_data(self, df):
        """数据预处理"""
        try:
            st.info("🔄 开始数据预处理...")
            
            # 列名标准化
            df_standardized = self.standardize_columns(df)
            
            # 数据清洗
            df_clean = self.clean_data(df_standardized)
            
            # 提取特征
            df_processed = self.extract_features(df_clean)
            
            self.data_processed = True
            self.df_valid = df_processed
            
            st.success(f"✅ 数据预处理完成，有效记录: {len(df_processed)}")
            return df_processed
            
        except Exception as e:
            st.error(f"❌ 数据预处理失败: {str(e)}")
            return None
    
    def standardize_columns(self, df):
        """列名标准化"""
        column_mapping = {}
        
        for col in df.columns:
            col_str = str(col).strip()
            
            # 匹配标准列名
            for standard_col, possible_names in self.config.column_mappings.items():
                for name in possible_names:
                    if name in col_str:
                        column_mapping[col] = standard_col
                        break
                if col in column_mapping:
                    break
        
        if column_mapping:
            df_renamed = df.rename(columns=column_mapping)
            st.success(f"✅ 列名标准化完成，映射 {len(column_mapping)} 个列")
            return df_renamed
        else:
            st.warning("⚠️ 未进行列名映射，使用原始列名")
            return df
    
    def clean_data(self, df):
        """数据清洗"""
        required_cols = ['会员账号', '期号', '内容', '金额']
        
        # 检查必要列
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"缺少必要列: {missing_cols}")
        
        # 基础清洗
        df_clean = df[required_cols].copy()
        if '彩种' in df.columns:
            df_clean['彩种'] = df['彩种']
        else:
            df_clean['彩种'] = '未知彩种'
        
        # 去除空值
        initial_count = len(df_clean)
        df_clean = df_clean.dropna(subset=required_cols)
        after_clean_count = len(df_clean)
        
        st.info(f"数据清洗: 移除空值记录 {initial_count - after_clean_count} 条")
        
        # 数据类型处理
        for col in ['会员账号', '期号', '内容', '彩种']:
            df_clean[col] = df_clean[col].astype(str).str.strip()
        
        return df_clean
    
    def extract_features(self, df_clean):
        """特征提取"""
        df_processed = df_clean.copy()
        
        # 提取金额
        df_processed['投注金额'] = df_processed['金额'].apply(self.extract_amount)
        
        # 提取投注方向
        df_processed['投注方向'] = df_processed['内容'].apply(self.extract_direction)
        
        # 过滤有效记录
        initial_count = len(df_processed)
        df_valid = df_processed[
            (df_processed['投注方向'] != '') & 
            (df_processed['投注金额'] >= self.config.min_amount)
        ].copy()
        after_filter_count = len(df_valid)
        
        st.info(f"特征提取: 过滤无效记录 {initial_count - after_filter_count} 条")
        
        return df_valid
    
    def extract_amount(self, amount_text):
        """提取金额"""
        try:
            if pd.isna(amount_text):
                return 0
            
            text = str(amount_text).strip()
            
            # 直接转换尝试
            try:
                cleaned = text.replace(',', '').replace('，', '')
                amount = float(cleaned)
                if amount >= self.config.min_amount:
                    return amount
            except:
                pass
            
            # 正则提取
            patterns = [
                r'投注[:：]?\s*(\d+[,，]?\d*\.?\d*)',
                r'金额[:：]?\s*(\d+[,，]?\d*\.?\d*)',
                r'(\d+[,，]?\d*\.?\d*)\s*元',
                r'￥\s*(\d+[,，]?\d*\.?\d*)',
                r'(\d+[,，]?\d*\.?\d*)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    amount_str = match.group(1).replace(',', '').replace('，', '')
                    try:
                        amount = float(amount_str)
                        if amount >= self.config.min_amount:
                            return amount
                    except:
                        continue
            
            return 0
        except Exception as e:
            return 0
    
    def extract_direction(self, content):
        """提取投注方向"""
        try:
            if pd.isna(content):
                return ""
            
            content_str = str(content).strip().lower()
            
            for direction, patterns in self.config.direction_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in content_str:
                        return direction
            
            return ""
        except Exception as e:
            return ""
    
    def run_complete_analysis(self, uploaded_file):
        """运行完整分析"""
        try:
            # 处理上传文件
            df, filename = self.process_uploaded_file(uploaded_file)
            if df is None:
                return "❌ 文件处理失败，请检查文件格式", None
            
            # 数据预处理
            df_processed = self.preprocess_data(df)
            if df_processed is None:
                return "❌ 数据预处理失败", None
            
            # 创建标签页显示不同分析结果
            tab1, tab2, tab3, tab4 = st.tabs(["📊 数据概览", "👥 多账户分析", "🎯 特码分析", "📈 详细统计"])
            
            with tab1:
                self.display_data_overview(df, df_processed)
            
            with tab2:
                multi_result = self.multi_analyzer.analyze_multi_account(df_processed)
                st.text_area("多账户分析结果", multi_result, height=400)
            
            with tab3:
                special_result = self.special_analyzer.analyze_special_code(df_processed)
                st.text_area("特码分析结果", special_result, height=400)
            
            with tab4:
                self.display_detailed_stats(df_processed)
            
            # 生成Excel报告
            excel_file = self.generate_excel_report(df_processed, filename)
            
            return "✅ 分析完成！请查看上方标签页获取详细结果。", excel_file
            
        except Exception as e:
            error_msg = f"❌ 分析过程中出现错误: {str(e)}"
            st.error(error_msg)
            st.text(traceback.format_exc())
            return error_msg, None
    
    def display_data_overview(self, df_raw, df_processed):
        """显示数据概览"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("原始记录数", len(df_raw))
        with col2:
            st.metric("有效记录数", len(df_processed))
        with col3:
            st.metric("数据处理率", f"{(len(df_processed)/len(df_raw))*100:.1f}%")
        
        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric("唯一账户数", df_processed['会员账号'].nunique())
        with col5:
            st.metric("唯一期号数", df_processed['期号'].nunique())
        with col6:
            st.metric("彩种数量", df_processed['彩种'].nunique())
        
        # 显示数据预览
        st.subheader("数据预览")
        st.dataframe(df_processed.head(20), use_container_width=True)
    
    def display_detailed_stats(self, df_processed):
        """显示详细统计"""
        st.subheader("详细统计分析")
        
        # 账户统计
        account_stats = df_processed.groupby('会员账号').agg({
            '投注金额': ['count', 'sum', 'mean', 'max'],
            '期号': 'nunique'
        }).round(2)
        
        account_stats.columns = ['投注次数', '总金额', '平均金额', '最大金额', '参与期数']
        account_stats = account_stats.sort_values('总金额', ascending=False)
        
        st.write("### 账户排名")
        st.dataframe(account_stats.head(20), use_container_width=True)
        
        # 期号统计
        period_stats = df_processed.groupby('期号').agg({
            '投注金额': ['sum', 'count'],
            '会员账号': 'nunique'
        }).round(2)
        
        period_stats.columns = ['期总金额', '期注数', '期账户数']
        period_stats = period_stats.sort_values('期总金额', ascending=False)
        
        st.write("### 期号统计")
        st.dataframe(period_stats.head(20), use_container_width=True)
    
    def generate_excel_report(self, df_processed, filename):
        """生成Excel报告"""
        try:
            if df_processed is None or len(df_processed) == 0:
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"彩票分析报告_{timestamp}.xlsx"
            
            with pd.ExcelWriter(export_filename, engine='openpyxl') as writer:
                # 基础数据表
                df_processed.to_excel(writer, sheet_name='基础数据', index=False)
                
                # 统计摘要表
                stats_data = {
                    '统计项目': ['总记录数', '有效记录数', '唯一账户数', '唯一期号数', '彩种数量', '总投注金额'],
                    '数值': [
                        len(df_processed),
                        len(df_processed),
                        df_processed['会员账号'].nunique(),
                        df_processed['期号'].nunique(),
                        df_processed['彩种'].nunique(),
                        df_processed['投注金额'].sum()
                    ]
                }
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name='统计摘要', index=False)
                
                # 账户排名表
                account_ranking = df_processed.groupby('会员账号').agg({
                    '投注金额': ['count', 'sum', 'mean'],
                    '期号': 'nunique'
                }).round(2)
                account_ranking.columns = ['投注次数', '总金额', '平均金额', '参与期数']
                account_ranking = account_ranking.sort_values('总金额', ascending=False)
                account_ranking.to_excel(writer, sheet_name='账户排名')
            
            st.success(f"✅ Excel报告已生成: {export_filename}")
            return export_filename
            
        except Exception as e:
            st.error(f"❌ 生成Excel报告失败: {str(e)}")
            return None

def get_file_download_link(filename):
    """生成文件下载链接"""
    with open(filename, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📥 下载 {filename}</a>'
    return href

def main():
    """主函数"""
    st.title("🎯 智能彩票分析系统 - 🌎Streamlit完整版 (v2-xwu1588158)")
    st.markdown("一站式多维度彩票数据分析平台，整合核心分析引擎")
    
    # 初始化分析系统
    if 'analysis_system' not in st.session_state:
        st.session_state.analysis_system = LotteryAnalysisSystem()
    
    # 侧边栏
    with st.sidebar:
        st.header("📊 分析设置")
        
        st.subheader("📁 上传数据文件")
        uploaded_file = st.file_uploader(
            "选择Excel或CSV文件",
            type=['xlsx', 'xls', 'csv'],
            help="支持包含会员账号、期号、内容、金额等列的数据文件"
        )
        
        st.subheader("⚙️ 分析选项")
        analysis_type = st.radio(
            "分析模式",
            ["完整分析", "快速分析", "深度分析"],
            index=0,
            help="完整分析包含所有检测模块"
        )
        
        st.subheader("🔧 系统信息")
        st.info(f"最小投注金额: {st.session_state.analysis_system.config.min_amount}元")
        st.info(f"支持文件类型: {', '.join(st.session_state.analysis_system.config.supported_file_types)}")
    
    # 主内容区
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("数据分析面板")
        
        if uploaded_file is not None:
            st.success(f"✅ 已加载文件: {uploaded_file.name}")
            
            if st.button("🚀 开始分析", type="primary", use_container_width=True):
                with st.spinner("分析中，请稍候..."):
                    result, excel_file = st.session_state.analysis_system.run_complete_analysis(uploaded_file)
                    
                    # 显示分析状态
                    if "完成" in result:
                        st.balloons()
                    
                    # 提供下载链接
                    if excel_file and os.path.exists(excel_file):
                        st.markdown(get_file_download_link(excel_file), unsafe_allow_html=True)
        else:
            st.info("👆 请在侧边栏上传数据文件开始分析")
    
    with col2:
        st.header("📋 功能说明")
        st.markdown("""
        ### 🔍 核心功能
        - **👥 多账户关联分析**
          - 对刷交易检测
          - 账户关联性分析
          - 可疑模式识别
        
        - **🎯 特码完美覆盖分析**
          - 特码投注模式分析
          - 数字覆盖度统计
          - 账户行为分析
        
        - **📈 统计分析**
          - 数据质量检查
          - 投注行为统计
          - 趋势分析
        """)
        
        st.header("📝 使用说明")
        st.markdown("""
        1. **上传** Excel/CSV数据文件
        2. **点击** "开始分析"按钮
        3. **查看** 各标签页分析结果
        4. **下载** 完整Excel报告
        """)

if __name__ == "__main__":
    main()
