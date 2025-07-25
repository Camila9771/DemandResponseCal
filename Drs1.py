import streamlit as st
import numpy as np
import pandas as pd

# 页面配置
st.set_page_config(
    page_title="电力需求响应收益计算系统",
    page_icon="⚡",
    layout="wide"
)

# ==================== 基础函数 ====================

def trimmed_mean(data):
    """
    去掉最大值和最小值后求平均值
    如果数据长度小于等于2，则直接求平均值
    """
    data = np.array(data)
    if len(data) <= 2:
        return np.mean(data)
    
    # 去掉一个最大值和一个最小值
    sorted_data = np.sort(data)[1:-1]
    return np.mean(sorted_data)

def effcal(Qbid, Qbaseline, Qoutput):
    """有效容量计算函数"""
    Qbid = np.array(Qbid)
    Qbaseline = np.array(Qbaseline)
    Qoutput = np.array(Qoutput)
    
    if not (len(Qbid) == len(Qbaseline) == len(Qoutput)):
        raise ValueError("输入向量长度必须相同")
    
    Qactual = Qbaseline - Qoutput
    threshold = Qbid * 1.1
    
    Qeffective = np.where(
        Qactual <= threshold,
        Qactual,
        threshold + (Qactual - threshold) * 0.5
    )
    
    return Qeffective

def clearPrice(length, user_prices=None, price_params=None):
    """
    出清价格计算函数（集成随机价格生成功能）
    
    参数:
    length (int): 时段数量
    user_prices (array-like or str, optional): 
        - None: 使用默认价格
        - 'random': 使用随机生成（需要price_params）
        - array-like: 用户自定义价格向量
    price_params (dict, optional): 随机价格生成参数，包含：
        - base_price: 基准价格
        - fluctuation: 波动范围
        - distribution: 分布类型
        - correlation: 相关性系数
        - seed: 随机种子
    
    返回:
    tuple: (Pclear, adjustment_info)
        - Pclear (numpy.ndarray): 出清价格向量
        - adjustment_info (dict): 调整信息（仅在随机生成时返回）
    """
    if not isinstance(length, int) or length <= 0:
        raise ValueError("时段数量必须是正整数")
    
    # 价格上下限
    price_floor = 0.0
    price_ceiling = 3.0
    
    # 判断价格生成模式
    if user_prices is None:
        # 模式1：使用默认价格
        default_prices = [1.2, 1.2, 1.2, 1.0, 1.0, 1.2]
        if length <= len(default_prices):
            Pclear = np.array(default_prices[:length])
        else:
            repeat_times = (length + len(default_prices) - 1) // len(default_prices)
            extended_prices = (default_prices * repeat_times)[:length]
            Pclear = np.array(extended_prices)
        return Pclear, {'mode': 'default', 'adjusted': False}
    
    elif user_prices == 'random':
        # 模式2：随机生成价格
        if price_params is None:
            raise ValueError("随机模式需要提供price_params参数")
        
        # 提取参数
        base_prices = price_params.get('base_price', 1.2)
        fluctuation_range = price_params.get('fluctuation', 0.1)
        distribution = price_params.get('distribution', 'uniform')
        correlation = price_params.get('correlation', 0.0)
        seed = price_params.get('seed', None)
        
        if seed is not None:
            np.random.seed(seed)
        
        # 将基准价格转换为数组
        if isinstance(base_prices, (int, float)):
            base_array = np.full(length, base_prices)
        else:
            base_array = np.array(base_prices)
            if len(base_array) < length:
                repeat_times = (length + len(base_array) - 1) // len(base_array)
                base_array = np.tile(base_array, repeat_times)[:length]
            else:
                base_array = base_array[:length]
        
        # 智能调整波动范围
        effective_ranges = np.zeros(length)
        adjustment_made = False
        
        for i in range(length):
            if base_array[i] > 0:
                max_down_range = (base_array[i] - price_floor) / base_array[i]
                max_up_range = (price_ceiling - base_array[i]) / base_array[i]
                effective_range = min(fluctuation_range, max_down_range, max_up_range)
                
                if effective_range < fluctuation_range:
                    adjustment_made = True
                
                effective_ranges[i] = effective_range
            else:
                effective_ranges[i] = 0
        
        # 根据分布类型生成价格
        if distribution == 'uniform':
            random_prices = np.zeros(length)
            for i in range(length):
                lower = base_array[i] * (1 - effective_ranges[i])
                upper = base_array[i] * (1 + effective_ranges[i])
                random_prices[i] = np.random.uniform(lower, upper)
        
        elif distribution == 'normal':
            random_prices = np.zeros(length)
            for i in range(length):
                mean = base_array[i]
                std_dev = base_array[i] * effective_ranges[i] / 3
                
                attempts = 0
                while attempts < 100:
                    price = np.random.normal(mean, std_dev)
                    if price_floor <= price <= price_ceiling:
                        random_prices[i] = price
                        break
                    attempts += 1
                else:
                    random_prices[i] = np.clip(price, price_floor, price_ceiling)
        
        elif distribution == 'correlated':
            random_prices = np.zeros(length)
            random_prices[0] = base_array[0] * (1 + np.random.uniform(-effective_ranges[0], effective_ranges[0]))
            
            for t in range(1, length):
                eff_range = effective_ranges[t]
                random_change = np.random.uniform(-eff_range, eff_range)
                inherited_deviation = (random_prices[t-1] / base_array[t-1] - 1) * correlation
                new_price = base_array[t] * (1 + inherited_deviation + random_change * (1 - correlation))
                random_prices[t] = np.clip(new_price, price_floor, price_ceiling)
        
        else:
            raise ValueError(f"不支持的分布类型: {distribution}")
        
        Pclear = np.round(random_prices, 3)
        
        adjustment_info = {
            'mode': 'random',
            'adjusted': adjustment_made,
            'original_range': fluctuation_range,
            'effective_range': np.mean(effective_ranges),
            'base_price': np.mean(base_array)
        }
        
        return Pclear, adjustment_info
    
    else:
        # 模式3：用户自定义价格
        user_prices = np.array(user_prices)
        if len(user_prices) == length:
            Pclear = user_prices
        elif len(user_prices) < length:
            repeat_times = (length + len(user_prices) - 1) // len(user_prices)
            Pclear = np.tile(user_prices, repeat_times)[:length]
        else:
            Pclear = user_prices[:length]
        
        # 检查并限制价格范围
        original_prices = Pclear.copy()
        Pclear = np.clip(Pclear, price_floor, price_ceiling)
        adjusted = not np.array_equal(original_prices, Pclear)
        
        return Pclear, {
            'mode': 'custom',
            'adjusted': adjusted,
            'adjusted_count': np.sum(original_prices != Pclear) if adjusted else 0
        }

def analyze_price_statistics(prices, base_prices):
    """分析生成价格的统计特性"""
    base_array = np.array(base_prices) if isinstance(base_prices, list) else np.full(len(prices), base_prices)
    if len(base_array) < len(prices):
        repeat_times = (len(prices) + len(base_array) - 1) // len(base_array)
        base_array = np.tile(base_array, repeat_times)[:len(prices)]
    
    deviations = (prices - base_array) / base_array * 100  # 百分比偏差
    
    stats = {
        '平均价格': np.mean(prices),
        '价格标准差': np.std(prices),
        '最高价格': np.max(prices),
        '最低价格': np.min(prices),
        '平均偏离度(%)': np.mean(np.abs(deviations)),
        '最大上偏(%)': np.max(deviations),
        '最大下偏(%)': np.min(deviations)
    }
    
    return stats

# ==================== 继续原有的基础函数 ====================

def rescal(Qeffective, Pclear):
    """响应费用计算函数"""
    Qeffective = np.array(Qeffective)
    Pclear = np.array(Pclear)
    
    if len(Qeffective) != len(Pclear):
        raise ValueError("有效容量向量和出清价格向量长度必须相同")
    
    Fresponse = np.sum(Qeffective * Pclear)
    return Fresponse

def asscal(Qbid, Qeffective, Pclear):
    """考核费用计算函数"""
    Qbid = np.array(Qbid)
    Qeffective = np.array(Qeffective)
    Pclear = np.array(Pclear)
    
    if not (len(Qbid) == len(Qeffective) == len(Pclear)):
        raise ValueError("输入向量长度必须相同")
    
    Cassess = Pclear * 1.1
    assessment_quantity = np.maximum(Qbid * 0.9 - Qeffective, 0)
    Fassess = np.sum(assessment_quantity * Cassess)
    
    return Fassess

def userprice(Pfloor, Pclear, alpha):
    """用户价格确定函数"""
    Pclear = np.array(Pclear)
    
    if not isinstance(Pfloor, (int, float)) or Pfloor < 0:
        raise ValueError("基准价格必须是非负数")
    
    if not isinstance(alpha, (int, float)) or alpha < 0:
        raise ValueError("价格加成系数必须是非负数")
    
    Puser = np.where(
        Pclear <= Pfloor,
        Pfloor,
        Pfloor + (Pclear - Pfloor) * alpha
    )
    
    return Puser

def MonthActual(Qbidall, DrDay, Qcapacity):
    """实际备用容量计算函数"""
    Qbidall = np.array(Qbidall)
    Qcapacity = np.array(Qcapacity)
    
    if len(Qbidall) == 0:
        raise ValueError("Qbidall向量不能为空")
    
    if not isinstance(DrDay, (int, float)) or DrDay not in [0, 1]:
        raise ValueError("DrDay必须是0或1")
    
    # 计算Qcapacity去除最大最小值后的平均值
    Qcaverage = trimmed_mean(Qcapacity)
    
    if DrDay == 0:
        Qactual = Qcaverage
    else:
        Qbidall_mean = np.mean(Qbidall)
        Qactual = min(Qcaverage, Qbidall_mean)
    
    return Qactual

def MonthPrice(user_price):
    """月度备用价格计算函数"""
    if user_price is None:
        raise ValueError("必须输入月度备用价格")
    return float(user_price)

# ==================== 功能模块 ====================

def monthly_reserve_module(AgentState, gamma, Qbidall, DrDay, Qcapacity, user_month_price):
    """
    月度备用模块
    
    参数:
    AgentState (int): 代理状态（0=无代理，1=有代理）
    gamma (float): 代理比例（0 < gamma < 1，无代理时为0）
    Qbidall (array-like): 日前响应中标容量向量
    DrDay (int): 是否启动日前响应判断变量（0或1）
    Qcapacity (array-like): 备用容量中标量向量
    user_month_price (float): 月度备用价格
    
    返回:
    QMonth (float): 实际备用容量（标量）
    PMonth (float): 月度备用价格（标量）
    base_revenue (float): 基础备用收益
    reserve_revenue (float): 最终用户收益（考虑代理比例）
    actual_gamma (float): 实际使用的代理比例
    """
    QMonth = MonthActual(Qbidall, DrDay, Qcapacity)
    PMonth = MonthPrice(user_month_price)
    
    # 计算基础备用收益（标量乘法）
    base_revenue = QMonth * PMonth
    
    # 根据代理状态计算最终收益
    if AgentState == 0:
        # 无代理情况
        reserve_revenue = base_revenue
        actual_gamma = 0.0
    else:
        # 有代理情况，用户收益 = 基础收益 × (1 - gamma)，代理费用 = 基础收益 × gamma
        reserve_revenue = base_revenue * (1 - gamma)
        actual_gamma = gamma
    
    return QMonth, PMonth, base_revenue, reserve_revenue, actual_gamma

def day_ahead_response_module(stateOFagent, Qb, Qbaseline, Qoutput, user_clear_prices, 
                            agent_mode=None, Pfloor=None, alpha=None, theta=None, price_params=None):
    """
    日前响应模块
    
    参数:
    stateOFagent (int): 是否代理标志（0=未代理，1=有代理）
    Qb (array-like): 中标容量向量
    Qbaseline (array-like): 基线向量
    Qoutput (array-like): 负荷向量
    user_clear_prices (array-like): 出清价格向量
    agent_mode (int): 代理模式（1=保底+分成，2=固定价格）
    Pfloor (float): 底价/固定价格
    alpha (float): 分成比例（代理模式1使用）
    theta (float): 考核分成比例
    
    返回:
    未代理: Qe, Pc, Cres, Cass, Cday
    有代理: Qe, Pc, Puser, Cres, Cass, Cday, agent_mode
    """
    if stateOFagent not in [0, 1]:
        raise ValueError("stateOFagent只能是0（未代理）或1（有代理）")
    
    if stateOFagent == 0:
        # 未代理的处理流程
        Qe = effcal(Qb, Qbaseline, Qoutput)
        time_periods = len(Qb)
        Pc, _ = clearPrice(time_periods, user_clear_prices, price_params)  # 传递price_params
        Cres = rescal(Qe, Pc)
        Cass = asscal(Qb, Qe, Pc)
        Cday = Cres - Cass
        
        return Qe, Pc, Cres, Cass, Cday
        
    else:
        # 有代理的处理流程
        # 步骤1: 计算有效容量（与未代理相同）
        Qe = effcal(Qb, Qbaseline, Qoutput)
        
        # 步骤2: 获取出清价格（与未代理相同）
        time_periods = len(Qb)
        Pc, _ = clearPrice(time_periods, user_clear_prices, price_params)  # 传递price_params
        
        # 计算用户价格Puser
        if agent_mode == 1:
            # 代理模式1：保底+分成
            Puser = userprice(Pfloor, Pc, alpha)
        elif agent_mode == 2:
            # 代理模式2：固定价格
            Puser = np.full(len(Pc), Pfloor)
        else:
            raise ValueError("代理模式必须是1或2")
        
        # 步骤3: 使用用户价格计算响应费用
        Cres = rescal(Qe, Puser)
        
        # 步骤4: 计算考核费用，乘以考核分成比例
        base_Cass = asscal(Qb, Qe, Pc)
        Cass = base_Cass * theta
        
        # 步骤5: 计算净收益（与未代理相同）
        Cday = Cres - Cass
        
        return Qe, Pc, Puser, Cres, Cass, Cday, agent_mode

def emergency_response_module(Qem, user_clear_prices, price_params=None):
    """应急响应收益模块"""
    Qem = np.array(Qem)
    time_periods = len(Qem)
    Pc, _ = clearPrice(time_periods, user_clear_prices, price_params)  # 传递price_params
    Pem = Pc * 0.1
    Cem = rescal(Qem, Pem)
    
    return Qem, Pc, Pem, Cem

# ==================== Streamlit 应用界面 ====================

def main():
    st.title("⚡ 电力需求响应收益计算系统")
    st.markdown("---")
    
    # 侧边栏选择
    st.sidebar.title("📋 系统配置")
    
    # 省份细则选择
    st.sidebar.markdown("### 🗺️ 省份细则选择")
    province = st.sidebar.selectbox(
        "选择省份需求响应细则:",
        ["四川", "上海", "海南"],
        key="province"
    )
    
    # 根据省份显示状态
    if province == "四川":
        st.sidebar.success("✅ 四川省需求响应细则 (已实现)")
        province_available = True
    else:
        st.sidebar.warning(f"⚠️ {province}省需求响应细则 (待开发)")
        province_available = False
    
    st.sidebar.markdown("---")
    
    # 模块选择（根据省份调整）
    if province == "四川":
        # 四川省的模块选择
        response_type = st.sidebar.selectbox(
            "选择需求响应类型:",
            ["月度备用模块", "日前响应模块", "应急响应收益模块"],
            key="response_type"
        )
    else:
        # 其他省份暂时显示占位符
        st.sidebar.markdown("**需求响应类型:**")
        st.sidebar.info(f"💡 {province}省的具体模块配置待完善")
        response_type = None
    
    st.sidebar.markdown("---")
    
    # 如果省份不可用，显示提示信息
    if not province_available:
        st.header(f"📍 {province}省需求响应收益计算")
        st.info(f"🚧 {province}省需求响应细则正在开发中，敬请期待！")
        st.markdown("### 🗺️ 已支持省份")
        st.success("✅ **四川省** - 完整支持月度备用、日前响应、应急响应三个模块")
        st.warning("⚠️ **上海省** - 开发中")
        st.warning("⚠️ **海南省** - 开发中")
        
        st.markdown("### 📋 四川省功能展示")
        st.markdown("""
        **四川省需求响应细则包含以下模块：**
        
        🏢 **月度备用模块**
        - 支持无代理和有代理两种模式
        - 代理费用 = 基础收益 × γ，用户收益 = 基础收益 × (1-γ)
        
        ⏰ **日前响应模块**  
        - 支持未代理模式和有代理模式
        - 有代理模式分为：保底+分成、固定价格两种子模式
        
        🚨 **应急响应收益模块**
        - 应急价格 = 出清价格 × 0.1
        - 简化的收益计算流程
        """)
        
        st.info("💡 请在左侧选择 **四川** 省份体验完整功能")
        return
    
    # 价格设置区域（仅四川省显示）
    st.sidebar.markdown("### 💰 价格设置")
    
    # 出清价格设置模式选择
    st.sidebar.markdown("**出清价格设置模式**")
    price_mode = st.sidebar.selectbox(
        "选择出清价格模式",
        ["默认", "自定义", "范围内随机生成", "根据历史价格估算", "模拟电力系统生成"],
        key="price_mode"
    )
    
    # 添加价格限制说明
    st.sidebar.info("💡 系统自动限制价格在 0-3 元/kW 范围内")
    
    user_clear_prices = None
    price_params = None  # 存储随机价格生成参数
    
    if price_mode == "默认":
        st.sidebar.success("✅ 使用默认出清价格: [1.2,1.2,1.2,1.0,1.0,1.2] 元/kW")
        user_clear_prices = None  # None表示使用默认价格
        
    elif price_mode == "自定义":
        # 自定义出清价格输入
        st.sidebar.markdown("**自定义出清价格 (Pclear)** *必填 [元/kW]")
        clear_price_input = st.sidebar.text_input(
            "出清价格向量 (元/kW)", 
            placeholder="例如: 1.2,1.0,1.5,1.3", 
            help="格式：价格1,价格2,价格3,价格4（用英文逗号分隔，单位：元/kW）",
            key="clear_prices"
        )
        
        if clear_price_input.strip():
            try:
                user_clear_prices = [float(x.strip()) for x in clear_price_input.split(',')]
                st.sidebar.success(f"✅ 出清价格已设置: {user_clear_prices} 元/kW")
            except:
                st.sidebar.error("❌ 价格格式错误，请使用逗号分隔的数字")
                user_clear_prices = None
        else:
            st.sidebar.warning("📝 请输入自定义出清价格")
            user_clear_prices = None
            
    elif price_mode == "范围内随机生成":
        st.sidebar.markdown("**随机价格生成参数**")
        
        # 基准价格输入
        base_price_type = st.sidebar.radio(
            "基准价格类型",
            ["单一价格", "分时段价格"],
            key="base_price_type"
        )
        
        if base_price_type == "单一价格":
            base_price = st.sidebar.number_input(
                "基准价格 (元/kW)",
                min_value=0.1,
                value=1.2,
                step=0.1,
                key="single_base_price"
            )
        else:
            base_price_input = st.sidebar.text_input(
                "分时段基准价格",
                value="1.2,1.0,1.5",
                help="用逗号分隔，如: 1.2,1.0,1.5",
                key="multi_base_price"
            )
            try:
                base_price = [float(x.strip()) for x in base_price_input.split(',')]
            except:
                st.sidebar.error("价格格式错误")
                base_price = 1.2
        
        # 波动范围
        fluctuation = st.sidebar.slider(
            "价格波动范围 (%)",
            min_value=0,
            max_value=50,
            value=10,
            help="生成的价格将在基准价格±此百分比范围内波动",
            key="fluctuation"
        ) / 100
        
        # 智能提示：检查基准价格是否接近边界
        if base_price_type == "单一价格":
            if base_price >= 2.5:
                max_safe_fluctuation = ((3.0 - base_price) / base_price) * 100
                st.sidebar.warning(f"⚠️ 基准价格接近上限，建议波动范围不超过 {max_safe_fluctuation:.0f}%")
            elif base_price <= 0.5:
                max_safe_fluctuation = ((base_price - 0.0) / base_price) * 100
                st.sidebar.warning(f"⚠️ 基准价格接近下限，建议波动范围不超过 {max_safe_fluctuation:.0f}%")
        
        # 高级选项
        with st.sidebar.expander("高级选项"):
            distribution = st.sidebar.selectbox(
                "随机分布类型",
                ["uniform", "normal", "correlated"],
                format_func=lambda x: {
                    "uniform": "均匀分布",
                    "normal": "正态分布",
                    "correlated": "相关随机游走"
                }[x],
                key="distribution"
            )
            
            correlation = 0.0
            if distribution == "correlated":
                correlation = st.sidebar.slider(
                    "时段相关性",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.5,
                    help="相邻时段价格的相关程度",
                    key="correlation"
                )
            
            use_seed = st.sidebar.checkbox("使用固定随机种子", key="use_seed")
            seed = st.sidebar.number_input("随机种子", value=42, key="seed") if use_seed else None
        
        # 存储参数
        price_params = {
            'base_price': base_price,
            'fluctuation': fluctuation,
            'distribution': distribution,
            'correlation': correlation,
            'seed': seed
        }
        
        st.sidebar.info("💡 价格将在计算时根据时段数自动生成")
        
    elif price_mode == "根据历史价格估算":
        st.sidebar.info("🚧 历史价格估算功能开发中...")
        st.sidebar.markdown("此功能将基于历史数据使用机器学习模型预测价格")
        user_clear_prices = None
        
    elif price_mode == "模拟电力系统生成":
        st.sidebar.info("🚧 电力系统模拟功能开发中...")
        st.sidebar.markdown("此功能将基于供需平衡模拟市场出清价格")
        user_clear_prices = None
    
    # 备用价格输入
    user_month_price = None
    if response_type == "月度备用模块":
        st.sidebar.markdown("**月度备用价格 (Pmonth)** *必填 [元/kW]")
        month_price_input = st.sidebar.text_input(
            "月度备用价格 (元/kW)", 
            placeholder="例如: 5.0",
            help="输入单个数值，单位：元/kW",
            key="month_price"
        )
        
        if month_price_input.strip():
            try:
                user_month_price = float(month_price_input.strip())
                st.sidebar.success(f"✅ 备用价格已设置: {user_month_price} 元/kW")
            except:
                st.sidebar.error("❌ 价格格式错误，请输入有效数字")
                user_month_price = None
        else:
            st.sidebar.warning("📝 请输入月度备用价格")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💡 说明")
    if response_type == "月度备用模块":
        st.sidebar.info("计算月度备用容量相关收益\n\n- 无代理：用户获得全部收益\n- 有代理：代理费用=基础收益×γ，用户收益=基础收益×(1-γ)")
    elif response_type == "日前响应模块":
        st.sidebar.info("计算日前响应相关收益\n\n- 未代理：使用出清价格计算\n- 有代理：使用用户价格计算，支持保底+分成或固定价格模式")
    else:
        st.sidebar.info("计算应急响应相关收益")
    
    # 主界面内容
    st.header(f"📊 {province}省 - {response_type}")
    
    if response_type == "月度备用模块":
        render_monthly_reserve_ui(user_clear_prices, user_month_price, price_mode, price_params)
    elif response_type == "日前响应模块":
        render_day_ahead_ui(user_clear_prices, price_mode, price_params)
    else:
        render_emergency_ui(user_clear_prices, price_mode, price_params)

def render_monthly_reserve_ui(user_clear_prices, user_month_price, price_mode, price_params):
    """月度备用模块界面"""
    st.markdown("### 输入参数")
    
    # 代理状态选择
    st.markdown("**代理状态 (AgentState)**")
    agent_state = st.selectbox(
        "选择代理状态", 
        [0, 1], 
        format_func=lambda x: "无代理" if x == 0 else "有代理",
        key="agent_state_monthly"
    )
    
    # 代理比例输入
    gamma = 0.0
    if agent_state == 1:
        st.markdown("**代理比例 (gamma)** *必填")
        gamma_input = st.text_input(
            "代理比例 (0 < gamma < 1)", 
            placeholder="例如: 0.2",
            help="输入0到1之间的小数，表示代理费用占基础收益的比例",
            key="gamma_monthly"
        )
        
        if gamma_input.strip():
            try:
                gamma = float(gamma_input.strip())
                if 0 < gamma < 1:
                    st.success(f"✅ 代理比例已设置: {gamma}")
                else:
                    st.error("❌ 代理比例必须在0到1之间")
                    gamma = 0.0
            except:
                st.error("❌ 代理比例格式错误，请输入有效数字")
                gamma = 0.0
        else:
            st.warning("📝 请输入代理比例")
    else:
        st.info("💡 无代理模式，代理比例自动设为0")
    
    # 输入区域
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**日前响应中标容量向量 (Qbidall) [kW]**")
        qbidall_input = st.text_input("格式: 19000,20010,20005,19500", value="19000,20010,20005,19500", key="qbidall", help="单位：kW")
        
        st.markdown("**是否启动日前响应 (DrDay)**")
        drday = st.selectbox("选择", [0, 1], format_func=lambda x: "未启动" if x == 0 else "启动", key="drday")
    
    with col2:
        st.markdown("**备用容量中标量向量 (Qcapacity) [kW]**")
        qcapacity_input = st.text_input("格式: 19773,19773,20000,20050", value="19773,19773,20000,20050", key="qcapacity", help="单位：kW")
    
    # 检查价格设置
    def is_clear_price_ready():
        if price_mode == "默认":
            return True
        elif price_mode == "自定义":
            return user_clear_prices is not None
        elif price_mode == "范围内随机生成":
            return price_params is not None
        else:
            return False
    
    price_ready = is_clear_price_ready() and user_month_price is not None
    gamma_ready = agent_state == 0 or (agent_state == 1 and gamma > 0)
    all_ready = price_ready and gamma_ready
    
    if not price_ready:
        st.warning("⚠️ 请先在左侧设置出清价格和备用价格")
    if agent_state == 1 and gamma <= 0:
        st.warning("⚠️ 请设置有效的代理比例")
    
    if st.button("计算月度备用收益", type="primary", disabled=not all_ready):
        if not all_ready:
            st.error("请先设置所有必需的参数")
            return
            
        try:
            # 解析输入
            Qbidall = [float(x.strip()) for x in qbidall_input.split(',')]
            Qcapacity = [float(x.strip()) for x in qcapacity_input.split(',')]
            
            # 调用模块
            QMonth, PMonth, base_revenue, reserve_revenue, actual_gamma = monthly_reserve_module(
                agent_state, gamma, Qbidall, drday, Qcapacity, user_month_price
            )
            
            # 显示详细结果
            st.success("计算完成！")
            
            st.markdown("### 计算结果")
            
            # 结果表格
            st.markdown("#### 备用容量计算详情")
            
            # 显示输入向量的处理过程
            capacity_df = pd.DataFrame({
                '时段': [f'第{i+1}时段' for i in range(len(Qcapacity))],
                '备用容量中标量 (kW)': Qcapacity,
                '日前响应中标容量 (kW)': Qbidall if len(Qbidall) == len(Qcapacity) else ['—'] * len(Qcapacity)
            })
            st.dataframe(capacity_df, use_container_width=True)
            
            # 显示处理结果
            if len(Qcapacity) > 2:
                sorted_capacity = np.sort(Qcapacity)
                trimmed_capacity = sorted_capacity[1:-1]  # 去掉最大最小值
                st.info(f"📊 备用容量去除极值处理：去掉最小值{sorted_capacity[0]}kW和最大值{sorted_capacity[-1]}kW，剩余容量平均值：{np.mean(trimmed_capacity):.2f}kW")
            else:
                st.info(f"📊 备用容量长度≤2，不去除极值，直接平均：{np.mean(Qcapacity):.2f}kW")
            
            if drday == 1:
                st.info(f"📊 日前响应影响：取备用容量均值({QMonth:.2f}kW)与日前响应均值({np.mean(Qbidall):.2f}kW)的最小值")
            
            # 详细信息
            if agent_state == 0:
                # 无代理情况
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("月度备用价格", f"{PMonth} 元/kW")
                with col2:
                    st.metric("实际备用容量", f"{QMonth:.2f} kW")
                with col3:
                    st.metric("总收益", f"{reserve_revenue:.2f} 元")
            else:
                # 有代理情况
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("月度备用价格", f"{PMonth} 元/kW")
                with col2:
                    st.metric("实际备用容量", f"{QMonth:.2f} kW")
                with col3:
                    st.metric("基础总收益", f"{base_revenue:.2f} 元")
                with col4:
                    agent_fee = base_revenue - reserve_revenue
                    st.metric("用户最终收益", f"{reserve_revenue:.2f} 元", f"-{agent_fee:.2f}")
                
                # 代理费用分析
                st.markdown("### 代理费用分析")
                agent_fee = base_revenue - reserve_revenue
                agent_analysis_df = pd.DataFrame({
                    '项目': ['实际备用容量', '月度备用价格', '基础备用收益', '代理费用', '用户最终收益'],
                    '数值': [f'{QMonth:.2f} kW', f'{PMonth} 元/kW', f'{base_revenue:.2f} 元', f'{agent_fee:.2f} 元', f'{reserve_revenue:.2f} 元'],
                    '比例 (%)': ['—', '—', '100%', f'{actual_gamma * 100:.1f}%', f'{(1 - actual_gamma) * 100:.1f}%']
                })
                st.dataframe(agent_analysis_df, use_container_width=True)
                
        except Exception as e:
            st.error(f"计算错误: {str(e)}")

def render_day_ahead_ui(user_clear_prices, price_mode, price_params):
    """日前响应模块界面"""
    st.markdown("### 输入参数")
    
    # 代理状态选择
    st.markdown("**代理状态 (stateOFagent)**")
    state_agent = st.selectbox(
        "选择代理状态", 
        [0, 1], 
        format_func=lambda x: "未代理" if x == 0 else "有代理",
        key="state_agent"
    )
    
    # 代理模式相关参数
    agent_mode = None
    Pfloor = None
    alpha = None
    theta = None
    agent_params_ready = True
    
    if state_agent == 1:
        # 代理模式选择
        st.markdown("**代理模式**")
        agent_mode = st.selectbox(
            "选择代理模式",
            [1, 2],
            format_func=lambda x: "模式1: 保底+分成" if x == 1 else "模式2: 固定价格",
            key="agent_mode"
        )
        
        # 代理参数输入
        col_agent1, col_agent2 = st.columns(2)
        
        with col_agent1:
            st.markdown("**底价 (Pfloor) [元/kW]** *必填")
            pfloor_input = st.text_input(
                "底价/固定价格", 
                placeholder="例如: 0.8",
                help="代理模式1为底价，代理模式2为固定价格",
                key="pfloor_dayahead"
            )
            
            if pfloor_input.strip():
                try:
                    Pfloor = float(pfloor_input.strip())
                    if Pfloor >= 0:
                        st.success(f"✅ 底价已设置: {Pfloor} 元/kW")
                    else:
                        st.error("❌ 底价不能为负数")
                        Pfloor = None
                except:
                    st.error("❌ 底价格式错误")
                    Pfloor = None
            else:
                st.warning("📝 请输入底价")
                agent_params_ready = False
        
        with col_agent2:
            if agent_mode == 1:
                st.markdown("**分成比例 (alpha)** *必填")
                alpha_input = st.text_input(
                    "分成比例 (0 < alpha ≤ 1)", 
                    placeholder="例如: 0.8",
                    help="超额部分的分成比例",
                    key="alpha_dayahead"
                )
                
                if alpha_input.strip():
                    try:
                        alpha = float(alpha_input.strip())
                        if 0 < alpha <= 1:
                            st.success(f"✅ 分成比例已设置: {alpha}")
                        else:
                            st.error("❌ 分成比例必须在0到1之间")
                            alpha = None
                    except:
                        st.error("❌ 分成比例格式错误")
                        alpha = None
                else:
                    st.warning("📝 请输入分成比例")
                    agent_params_ready = False
            else:
                st.info("💡 固定价格模式，无需分成比例")
                alpha = 1.0  # 固定价格模式下alpha不影响计算
        
        # 考核分成比例
        st.markdown("**考核分成比例 (theta)** *必填")
        theta_input = st.text_input(
            "考核分成比例 (0 < theta ≤ 1)", 
            placeholder="例如: 0.5",
            help="代理承担的考核费用比例",
            key="theta_dayahead"
        )
        
        if theta_input.strip():
            try:
                theta = float(theta_input.strip())
                if 0 < theta <= 1:
                    st.success(f"✅ 考核分成比例已设置: {theta}")
                else:
                    st.error("❌ 考核分成比例必须在0到1之间")
                    theta = None
            except:
                st.error("❌ 考核分成比例格式错误")
                theta = None
        else:
            st.warning("📝 请输入考核分成比例")
            agent_params_ready = False
        
        # 检查代理参数完整性
        if agent_mode == 1:
            agent_params_ready = agent_params_ready and Pfloor is not None and alpha is not None and theta is not None
        else:
            agent_params_ready = agent_params_ready and Pfloor is not None and theta is not None
    
    # 基础参数输入区域
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**中标容量向量 (Qb) [kW]**")
        qb_input = st.text_input("格式: 19970,19000,19500,19800", value="19970,19000,19500,19800", key="qb", help="单位：kW")
        
        st.markdown("**基线向量 (Qbaseline) [kW]**")
        qbaseline_input = st.text_input("格式: 21220,19785,18733,19700", value="21220,19785,18733,19700", key="qbaseline", help="单位：kW")
    
    with col2:
        st.markdown("**负荷向量 (Qoutput) [kW]**")
        qoutput_input = st.text_input("格式: 0,0,100,2500", value="0,0,100,2500", key="qoutput", help="单位：kW")
    
    # 检查所有必需参数
    def is_clear_price_ready():
        if price_mode == "默认":
            return True
        elif price_mode == "自定义":
            return user_clear_prices is not None
        elif price_mode == "范围内随机生成":
            return price_params is not None
        else:
            return False
    
    price_ready = is_clear_price_ready()
    all_ready = price_ready and (state_agent == 0 or agent_params_ready)
    
    if not price_ready:
        st.warning("⚠️ 请先在左侧设置出清价格")
    if state_agent == 1 and not agent_params_ready:
        st.warning("⚠️ 请设置完整的代理参数")
    
    if st.button("计算日前响应收益", type="primary", disabled=not all_ready):
        if not all_ready:
            st.error("请先设置所有必需的参数")
            return
            
        try:
            # 解析输入
            Qb = [float(x.strip()) for x in qb_input.split(',')]
            Qbaseline = [float(x.strip()) for x in qbaseline_input.split(',')]
            Qoutput = [float(x.strip()) for x in qoutput_input.split(',')]
            
            # 获取时段数
            time_periods = len(Qb)
            
            # 根据价格模式生成出清价格
            if price_mode == "范围内随机生成" and price_params:
                # 使用随机模式调用clearPrice
                Pc, adjustment_info = clearPrice(time_periods, 'random', price_params)
                
                # 提示波动范围调整信息
                if adjustment_info['adjusted']:
                    base_val = adjustment_info['base_price']
                    if base_val >= 2.5:
                        st.info(f"💡 基准价格({base_val:.2f}元)接近上限，系统已智能调整波动范围以保持价格分布合理性")
                    elif base_val <= 0.5:
                        st.info(f"💡 基准价格({base_val:.2f}元)接近下限，系统已智能调整波动范围以保持价格分布合理性")
                
                user_clear_prices = Pc.tolist()
            else:
                # 使用其他模式
                user_clear_prices_input = user_clear_prices if price_mode == "自定义" else None
                Pc, _ = clearPrice(time_periods, user_clear_prices_input)
            
            # 调用模块
            if state_agent == 0:
                # 未代理模式
                # 准备价格参数
                if price_mode == "范围内随机生成":
                    clear_prices_arg = 'random'
                else:
                    clear_prices_arg = user_clear_prices
                
                Qe, Pc, Cres, Cass, Cday = day_ahead_response_module(
                    state_agent, Qb, Qbaseline, Qoutput, clear_prices_arg, 
                    price_params=price_params if price_mode == "范围内随机生成" else None
                )
                
                # 显示详细结果
                st.success("计算完成！")
                st.markdown("### 计算结果")
                
                # 如果使用随机价格，显示统计信息
                if price_mode == "范围内随机生成":
                    st.markdown("#### 随机价格生成结果")
                    stats = analyze_price_statistics(Pc, price_params['base_price'])
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("平均价格", f"{stats['平均价格']:.3f} 元/kW")
                    with col_stat2:
                        st.metric("价格标准差", f"{stats['价格标准差']:.3f}")
                    with col_stat3:
                        st.metric("价格范围", f"{stats['最低价格']:.3f} - {stats['最高价格']:.3f}")
                
                # 结果表格
                results_df = pd.DataFrame({
                    '时段': [f'第{i+1}时段' for i in range(len(Qe))],
                    '中标容量 (kW)': Qb,
                    '有效容量 (kW)': Qe,
                    '出清价格 (元/kW)': Pc,
                    '时段响应收益 (元)': Qe * Pc
                })
                
                st.dataframe(results_df, use_container_width=True)
                
                # 详细信息
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("响应费用", f"{Cres:.2f} 元")
                with col2:
                    st.metric("考核费用", f"{Cass:.2f} 元")
                with col3:
                    st.metric("净收益", f"{Cday:.2f} 元")
                with col4:
                    if Cday > 0:
                        st.metric("收益状态", "盈利 ✅")
                    else:
                        st.metric("收益状态", "亏损 ❌")
            
            else:
                # 有代理模式
                # 准备价格参数
                if price_mode == "范围内随机生成":
                    clear_prices_arg = 'random'
                else:
                    clear_prices_arg = user_clear_prices
                
                Qe, Pc, Puser, Cres, Cass, Cday, used_agent_mode = day_ahead_response_module(
                    state_agent, Qb, Qbaseline, Qoutput, clear_prices_arg,
                    agent_mode, Pfloor, alpha, theta,
                    price_params=price_params if price_mode == "范围内随机生成" else None
                )
                
                # 显示详细结果
                st.success("计算完成！")
                st.markdown("### 计算结果")
                
                # 如果使用随机价格，显示统计信息
                if price_mode == "范围内随机生成":
                    st.markdown("#### 随机价格生成结果")
                    stats = analyze_price_statistics(Pc, price_params['base_price'])
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("平均价格", f"{stats['平均价格']:.3f} 元/kW")
                    with col_stat2:
                        st.metric("价格标准差", f"{stats['价格标准差']:.3f}")
                    with col_stat3:
                        st.metric("价格范围", f"{stats['最低价格']:.3f} - {stats['最高价格']:.3f}")
                
                # 结果表格
                results_df = pd.DataFrame({
                    '时段': [f'第{i+1}时段' for i in range(len(Qe))],
                    '中标容量 (kW)': Qb,
                    '有效容量 (kW)': Qe,
                    '出清价格 (元/kW)': Pc,
                    '用户价格 (元/kW)': Puser,
                    '时段响应收益 (元)': Qe * Puser
                })
                
                st.dataframe(results_df, use_container_width=True)
                
                # 详细信息
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("响应费用", f"{Cres:.2f} 元")
                with col2:
                    st.metric("考核费用", f"{Cass:.2f} 元")
                with col3:
                    st.metric("净收益", f"{Cday:.2f} 元")
                with col4:
                    if Cday > 0:
                        st.metric("收益状态", "盈利 ✅")
                    else:
                        st.metric("收益状态", "亏损 ❌")
                
                # 代理模式分析
                st.markdown("### 代理模式分析")
                mode_name = "保底+分成" if used_agent_mode == 1 else "固定价格"
                
                agent_analysis_df = pd.DataFrame({
                    '时段': [f'第{i+1}时段' for i in range(len(Pc))],
                    '出清价格 (元/kW)': Pc,
                    '用户价格 (元/kW)': Puser,
                    '价格差异 (元/kW)': Puser - Pc
                })
                st.dataframe(agent_analysis_df, use_container_width=True)
                
                st.info(f"📊 代理模式: {mode_name} | 底价: {Pfloor} 元/kW | 考核分成: {theta}")
                if used_agent_mode == 1:
                    st.info(f"🔄 分成比例: {alpha}")
                
        except Exception as e:
            st.error(f"计算错误: {str(e)}")

def render_emergency_ui(user_clear_prices, price_mode, price_params):
    """应急响应收益模块界面"""
    st.markdown("### 输入参数")
    
    st.markdown("**应急响应容量向量 (Qem) [kW]**")
    qem_input = st.text_input("格式: 500,800,1200,900", value="500,800,1200,900", key="qem", help="单位：kW")
    
    # 检查价格设置
    def is_clear_price_ready():
        if price_mode == "默认":
            return True
        elif price_mode == "自定义":
            return user_clear_prices is not None
        elif price_mode == "范围内随机生成":
            return price_params is not None
        else:
            return False
    
    price_ready = is_clear_price_ready()
    
    if not price_ready:
        st.warning("⚠️ 请先在左侧设置出清价格")
    
    if st.button("计算应急响应收益", type="primary", disabled=not price_ready):
        if not price_ready:
            st.error("请先设置出清价格")
            return
            
        try:
            # 解析输入
            Qem = [float(x.strip()) for x in qem_input.split(',')]
            
            # 获取时段数
            time_periods = len(Qem)
            
            # 根据价格模式生成出清价格
            if price_mode == "范围内随机生成" and price_params:
                # 实时生成随机价格
                Pc, adjustment_made = generate_random_prices(
                    price_params['base_price'],
                    price_params['fluctuation'],
                    time_periods,
                    price_params.get('distribution', 'uniform'),
                    price_params.get('correlation', 0.0),
                    price_params.get('seed', None)
                )
                
                # 提示波动范围调整信息
                if adjustment_made:
                    base_val = price_params['base_price'] if isinstance(price_params['base_price'], (int, float)) else np.mean(price_params['base_price'])
                    if base_val >= 2.5:
                        st.info(f"💡 基准价格({base_val:.2f}元)接近上限，系统已智能调整波动范围以保持价格分布合理性")
                    elif base_val <= 0.5:
                        st.info(f"💡 基准价格({base_val:.2f}元)接近下限，系统已智能调整波动范围以保持价格分布合理性")
                
                user_clear_prices = Pc.tolist()
            
            # 调用模块
            if price_mode == "范围内随机生成":
                clear_prices_arg = 'random'
            else:
                clear_prices_arg = user_clear_prices
            
            Qem_result, Pc, Pem, Cem = emergency_response_module(
                Qem, clear_prices_arg, 
                price_params if price_mode == "范围内随机生成" else None
            )
            
            # 显示详细结果
            st.success("计算完成！")
            
            st.markdown("### 计算结果")
            
            # 如果使用随机价格，显示统计信息
            if price_mode == "范围内随机生成":
                st.markdown("#### 随机价格生成结果")
                stats = analyze_price_statistics(Pc, price_params['base_price'])
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("平均价格", f"{stats['平均价格']:.3f} 元/kW")
                with col_stat2:
                    st.metric("价格标准差", f"{stats['价格标准差']:.3f}")
                with col_stat3:
                    st.metric("价格范围", f"{stats['最低价格']:.3f} - {stats['最高价格']:.3f}")
            
            # 结果表格
            results_df = pd.DataFrame({
                '时段': [f'第{i+1}时段' for i in range(len(Qem_result))],
                '应急响应容量 (kW)': Qem_result,
                '出清价格 (元/kW)': Pc,
                '应急价格 (元/kW)': Pem,
                '时段收益 (元)': Qem_result * Pem
            })
            
            st.dataframe(results_df, use_container_width=True)
            
            # 详细信息
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总应急容量", f"{np.sum(Qem_result):.2f} kW")
            with col2:
                st.metric("平均应急价格", f"{np.mean(Pem):.2f} 元/kW")
            with col3:
                st.metric("总收益", f"{Cem:.2f} 元")
            
            # 价格对比
            st.markdown("### 价格对比")
            price_comparison_df = pd.DataFrame({
                '时段': [f'第{i+1}时段' for i in range(len(Pc))],
                '出清价格 (元/kW)': Pc,
                '应急价格 (元/kW)': Pem,
                '价格比例 (%)': (Pem / Pc * 100)
            })
            st.dataframe(price_comparison_df, use_container_width=True)
                
        except Exception as e:
            st.error(f"计算错误: {str(e)}")

if __name__ == "__main__":
    main()
