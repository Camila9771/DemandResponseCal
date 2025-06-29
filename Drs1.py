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

def clearPrice(length, user_prices=None):
    """
    出清价格计算函数
    
    参数:
    length (int): 时段数量
    user_prices (array-like, optional): 用户输入的价格向量，None时使用默认价格
    
    返回:
    Pclear (numpy.ndarray): 出清价格向量
    
    计算逻辑:
    - 如果user_prices为None，使用默认价格 [90,90,90,80,80,90]
    - 如果user_prices不为None，使用用户输入的价格
    - 当输入价格长度与所需长度不匹配时，自动重复或截取
    """
    if not isinstance(length, int) or length <= 0:
        raise ValueError("时段数量必须是正整数")
    
    if user_prices is None:
        # 使用默认价格
        default_prices = [90, 90, 90, 80, 80, 90]
        if length <= len(default_prices):
            Pclear = np.array(default_prices[:length])
        else:
            # 如果需要的长度超过默认数组，重复使用默认数组
            repeat_times = (length + len(default_prices) - 1) // len(default_prices)
            extended_prices = (default_prices * repeat_times)[:length]
            Pclear = np.array(extended_prices)
        return Pclear
    else:
        # 使用用户输入的价格
        user_prices = np.array(user_prices)
        if len(user_prices) == length:
            return user_prices
        elif len(user_prices) < length:
            # 如果用户输入的价格少于时段数，重复使用
            repeat_times = (length + len(user_prices) - 1) // len(user_prices)
            extended_prices = np.tile(user_prices, repeat_times)[:length]
            return extended_prices
        else:
            # 如果用户输入的价格多于时段数，截取前面部分
            return user_prices[:length]

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
    
    if DrDay == 0:
        Qactual = Qcapacity.copy()
    else:
        Qbidall_mean = np.mean(Qbidall)
        Qactual = np.minimum(Qcapacity, Qbidall_mean)
    
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
    QMonth (numpy.ndarray): 实际备用容量向量
    PMonth (float): 月度备用价格（标量）
    Pmonth1 (numpy.ndarray): 月度备用价格向量
    base_revenue (float): 基础备用收益
    reserve_revenue (float): 最终用户收益（考虑代理比例）
    actual_gamma (float): 实际使用的代理比例
    
    实现流程:
    1. 调用基础函数6 MonthActual() → QMonth
    2. 调用基础函数7 MonthPrice() → PMonth  
    3. 根据QMonth长度创建Pmonth1向量（每个元素都是PMonth）
    4. 调用基础函数3 rescal() → 基础备用收益
    5. 根据代理状态计算最终用户收益：
       - 无代理：用户收益 = 基础收益
       - 有代理：用户收益 = 基础收益 × (1 - gamma)，代理费用 = 基础收益 × gamma
    """
    QMonth = MonthActual(Qbidall, DrDay, Qcapacity)
    PMonth = MonthPrice(user_month_price)
    time_periods = len(QMonth)
    Pmonth1 = np.full(time_periods, PMonth)
    base_revenue = rescal(QMonth, Pmonth1)
    
    # 根据代理状态计算最终收益
    if AgentState == 0:
        # 无代理情况
        reserve_revenue = base_revenue
        actual_gamma = 0.0
    else:
        # 有代理情况，用户收益 = 基础收益 × (1 - gamma)，代理费用 = 基础收益 × gamma
        reserve_revenue = base_revenue * (1 - gamma)
        actual_gamma = gamma
    
    return QMonth, PMonth, Pmonth1, base_revenue, reserve_revenue, actual_gamma

def day_ahead_response_module(stateOFagent, Qb, Qbaseline, Qoutput, user_clear_prices, 
                            agent_mode=None, Pfloor=None, alpha=None, theta=None):
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
    
    实现流程:
    未代理模式:
    1. effcal() → 有效容量
    2. clearPrice() → 出清价格
    3. rescal(有效容量, 出清价格) → 响应费用
    4. asscal() → 考核费用
    5. 净收益 = 响应费用 - 考核费用
    
    有代理模式:
    1. effcal() → 有效容量（同未代理）
    2. clearPrice() → 出清价格（同未代理）
    2.5. 计算用户价格Puser：
         - 模式1：userprice(Pfloor, 出清价格, alpha)
         - 模式2：Puser = Pfloor
    3. rescal(有效容量, 用户价格) → 响应费用
    4. asscal() × theta → 考核费用（乘以考核分成比例）
    5. 净收益 = 响应费用 - 考核费用（同未代理）
    """
    if stateOFagent not in [0, 1]:
        raise ValueError("stateOFagent只能是0（未代理）或1（有代理）")
    
    if stateOFagent == 0:
        # 未代理的处理流程
        Qe = effcal(Qb, Qbaseline, Qoutput)
        time_periods = len(Qb)
        Pc = clearPrice(time_periods, user_clear_prices)
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
        Pc = clearPrice(time_periods, user_clear_prices)
        
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

def emergency_response_module(Qem, user_clear_prices):
    """应急响应收益模块"""
    Qem = np.array(Qem)
    time_periods = len(Qem)
    Pc = clearPrice(time_periods, user_clear_prices)
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
        ["默认", "自定义"],
        key="price_mode"
    )
    
    user_clear_prices = None
    if price_mode == "默认":
        st.sidebar.success("✅ 使用默认出清价格: [90,90,90,80,80,90] 元/kW")
        user_clear_prices = None  # None表示使用默认价格
    else:
        # 自定义出清价格输入
        st.sidebar.markdown("**自定义出清价格 (Pclear)** *必填 [元/kW]")
        clear_price_input = st.sidebar.text_input(
            "出清价格向量 (元/kW)", 
            placeholder="例如: 90,60,20,30", 
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
    
    # 备用价格输入提示
    
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
    
    # 主界面内容 - 改为全宽显示
    st.header(f"📊 {province}省 - {response_type}")
    
    if response_type == "月度备用模块":
        render_monthly_reserve_ui(user_clear_prices, user_month_price)
    elif response_type == "日前响应模块":
        render_day_ahead_ui(user_clear_prices)
    else:
        render_emergency_ui(user_clear_prices)

def render_monthly_reserve_ui(user_clear_prices, user_month_price):
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
        qbidall_input = st.text_input("格式: 75,85,95,80", value="75,85,95,80", key="qbidall", help="单位：kW")
        
        st.markdown("**是否启动日前响应 (DrDay)**")
        drday = st.selectbox("选择", [0, 1], format_func=lambda x: "未启动" if x == 0 else "启动", key="drday")
    
    with col2:
        st.markdown("**备用容量中标量向量 (Qcapacity) [kW]**")
        qcapacity_input = st.text_input("格式: 110,95,140,105", value="110,95,140,105", key="qcapacity", help="单位：kW")
    
    # 检查价格设置
    def is_clear_price_ready():
        if 'price_mode' in st.session_state:
            if st.session_state.price_mode == "默认":
                return True
            else:
                return user_clear_prices is not None
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
            QMonth, PMonth, Pmonth1, base_revenue, reserve_revenue, actual_gamma = monthly_reserve_module(
                agent_state, gamma, Qbidall, drday, Qcapacity, user_month_price
            )
            
            # 显示详细结果
            st.success("计算完成！")
            
            st.markdown("### 计算结果")
            
            # 结果表格
            results_df = pd.DataFrame({
                '时段': [f'第{i+1}时段' for i in range(len(QMonth))],
                '实际备用容量 (kW)': QMonth,
                '月度备用价格 (元/kW)': Pmonth1,
                '基础时段收益 (元)': QMonth * Pmonth1,
                '用户时段收益 (元)': (QMonth * Pmonth1) * (1 - actual_gamma if agent_state == 1 else 1.0)
            })
            
            st.dataframe(results_df, use_container_width=True)
            
            # 详细信息
            if agent_state == 0:
                # 无代理情况
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("月度备用价格", f"{PMonth} 元/kW")
                with col2:
                    st.metric("总备用容量", f"{np.sum(QMonth):.2f} kW")
                with col3:
                    st.metric("总收益", f"{reserve_revenue:.2f} 元")
            else:
                # 有代理情况
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("月度备用价格", f"{PMonth} 元/kW")
                with col2:
                    st.metric("总备用容量", f"{np.sum(QMonth):.2f} kW")
                with col3:
                    st.metric("基础总收益", f"{base_revenue:.2f} 元")
                with col4:
                    agent_fee = base_revenue - reserve_revenue
                    st.metric("用户最终收益", f"{reserve_revenue:.2f} 元", f"-{agent_fee:.2f}")
                
                # 代理费用分析
                st.markdown("### 代理费用分析")
                agent_fee = base_revenue - reserve_revenue
                agent_analysis_df = pd.DataFrame({
                    '项目': ['基础备用收益', '代理费用', '用户最终收益'],
                    '金额 (元)': [base_revenue, agent_fee, reserve_revenue],
                    '比例 (%)': [100, actual_gamma * 100, (1 - actual_gamma) * 100]
                })
                st.dataframe(agent_analysis_df, use_container_width=True)
                
        except Exception as e:
            st.error(f"计算错误: {str(e)}")

def render_day_ahead_ui(user_clear_prices):
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
                placeholder="例如: 50.0",
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
        qb_input = st.text_input("格式: 100,150,200,120", value="100,150,200,120", key="qb", help="单位：kW")
        
        st.markdown("**基线向量 (Qbaseline) [kW]**")
        qbaseline_input = st.text_input("格式: 0,180,250,140", value="0,180,250,140", key="qbaseline", help="单位：kW")
    
    with col2:
        st.markdown("**负荷向量 (Qoutput) [kW]**")
        qoutput_input = st.text_input("格式: 0,30,10,25", value="0,30,10,25", key="qoutput", help="单位：kW")
    
    # 检查所有必需参数
    def is_clear_price_ready():
        if 'price_mode' in st.session_state:
            if st.session_state.price_mode == "默认":
                return True
            else:
                return user_clear_prices is not None
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
            
            # 调用模块
            if state_agent == 0:
                # 未代理模式
                Qe, Pc, Cres, Cass, Cday = day_ahead_response_module(
                    state_agent, Qb, Qbaseline, Qoutput, user_clear_prices
                )
                
                # 显示详细结果
                st.success("计算完成！")
                st.markdown("### 计算结果")
                
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
                Qe, Pc, Puser, Cres, Cass, Cday, used_agent_mode = day_ahead_response_module(
                    state_agent, Qb, Qbaseline, Qoutput, user_clear_prices,
                    agent_mode, Pfloor, alpha, theta
                )
                
                # 显示详细结果
                st.success("计算完成！")
                st.markdown("### 计算结果")
                
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

def render_emergency_ui(user_clear_prices):
    """应急响应收益模块界面"""
    st.markdown("### 输入参数")
    
    st.markdown("**应急响应容量向量 (Qem) [kW]**")
    qem_input = st.text_input("格式: 50,80,120,90", value="50,80,120,90", key="qem", help="单位：kW")
    
    # 检查价格设置
    def is_clear_price_ready():
        if 'price_mode' in st.session_state:
            if st.session_state.price_mode == "默认":
                return True
            else:
                return user_clear_prices is not None
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
            
            # 调用模块
            Qem_result, Pc, Pem, Cem = emergency_response_module(Qem, user_clear_prices)
            
            # 显示详细结果
            st.success("计算完成！")
            
            st.markdown("### 计算结果")
            
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