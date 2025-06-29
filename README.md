# 四川省电力需求侧市场化响应收益计算方法

## 1. 符号定义

### 1.1 基本变量
- $R_{total}$：用户总收益
- $R_{capacity}$：备用容量收益
- $R_{response}$：日前响应电量收益
- $R_{emergency}$：应急响应电量收益
- $F_{response}$ ：相应费用
- $F_{assess}$ ： 考核费用
- $C_{capacity}$：备用容量价格
- $C_{response}$：日前响应价格
- $C_{emergency}$：应急响应价格
- $C_{assess}$：考核价格
- $Q_{output}$: 负荷出力
- $Q_{bid}$：中标容量
- $Q_{actual}$：实际响应容量
- $Q_{effective}$：有效响应容量
- $Q_{baseline}$：基线负荷
- $P_{clear}$：日前出清价格
- $P_{emergency}$：应急响应价格
- $P_{fixed}$：固定价格
- $P_{floor}$：保底价格
- $\alpha$：响应费用分成比例
- $\gamma$: 备用容量分成比例
- $\theta$: 考核费用向代理用户分摊比例

### 1.2 时间索引
- $h$：小时索引
- $d$：日期索引
- $m$：月份索引

## 2. 总体收益计算

$R_{total} = R_{capacity} + R_{response} + R_{emergency}$

## 3. 备用容量收益

### 3.1 基本计算公式

$$R_{capacity} = Q_{actual,capacity} \times C_{capacity}$$

**当包含代理时，对于代理商**
$$R_{capacity,agent}=\sum R_{capacity}*\gamma$$
**对于代理用户**
$$R_{capacity,user}=R_{capacity}*(1-\gamma)$$

### 3.2 实际备用容量确定

**情况1：未启动日前响应的地区(DrDay=0)**
$$Q_{actual,h} = Q_{capacity,h}$$

**情况2：启动日前响应的地区(DrDay=1)**
$$Q_{actual,h} = \min(Q_{capacity,h}, \overline{Q_{bidall}})$$

其中，$\overline{Q_{bidall}}$ 为参与了日前响应的容量平均值。

## 4. 日前响应电量收益


#### 有效响应容量计算（按小时）

设某小时h的实际响应负荷为：
$$Q_{actual,h} = \overline{Q_{baseline,h}} - \overline{Q_{output,h}}$$

#### **情况1：$Q_{actual,h} \leq Q_{bid,h} \times 1.1$**
$$Q_{effective,h} = Q_{actual,h}$$

#### **情况2：$Q_{actual,h} > Q_{bid,h} \times 1.1$**
$$Q_{effective,h} = Q_{bid,h} \times 1.1 + (Q_{actual,h} - Q_{bid,h} \times 1.1) \times 0.5$$
### 4.1 直接交易用户

#### 4.1.1 响应费用
$$F_{response} = \sum_{d} \sum_{h \in H_d} Q_{effective,h} \times P_{clear,h}$$
#### 4.1.2 考核费用
$$F_{assess} = \sum_{h \in H_d} \max\left(( Q_{bid,h} \times 0.9 -  Q_{effective,h}), 0\right) \times C_{assess,h}$$

其中，考核价格：
$$C_{assess,h} = P_{clear,h} \times 1.1$$

#### 4.1.3 直接用户净收益
$$R_{response,direct} = F_{response} - F_{assess}$$

### 4.2 代理用户与代理商
 
#### 4.2.1 日前响应费用

对于代理用户而言，有两种模式
##### "保底+分成"模式
**当 $P_{clear,h} \leq P_{floor}$ 时：**
$$F_{response,user,h} = Q_{effective,user,h} \times P_{floor}$$  
**当 $P_{clear,h} > P_{floor}$ 时：**
$$P_{response,user,h} = Q_{effective,user,h} \times [P_{floor} + (P_{clear,d} - P_{floor}) \times \alpha]$$


**当 $P_{clear,h} \leq P_{floor}$ 时：**
$$P_{user,h} =  P_{floor}$$  
**当 $P_{clear,h} > P_{floor}$ 时：**
$$P_{user,h} = P_{floor} + (P_{clear,h} - P_{floor}) \times \alpha$$

##### "固定价格"模式
$$F_{response,user,h} = Q_{effective,user,h} \times P_{fixed}$$
对于代理商，负荷响应费用为：
$$F_{response,agent,h}=Q_{effective,agent,h}*P_{clear,h}$$
$$Q_{effective,agent,h}=\sum_i Q_{effective,user,h}$$
其中$i$代表其代理的用户集合,$Q_{effective,agent,h}$代表代理商有效响应容量
#### 4.2.2 考核费用
##### 4.2.2.1预考核费用
代理商预考核费用：
$$F_{assess,agent,pre} = \sum_{d} \max\left(\sum_{h \in H_d} Q_{bid,agent,h} \times 0.9 - \sum_{h \in H_d} Q_{effective,agent,h}, 0\right) \times C_{assess,h}$$
代理用户预考核费用：
$$F_{assess,user,pre} = \sum_{d} \max\left(\sum_{h \in H_d} Q_{bid,user,h} \times 0.9 - \sum_{h \in H_d} Q_{effective,user,h}, 0\right) \times C_{assess,h}$$
##### 4.2.2.2实际考核费用
代理用户实际考核费用： 
$$F_{assess,user}=(F_{assess,agent,pre}*F_{assess,user,pre}*\theta)/F_{assess,userrelated,pre}$$
 $F_{assess,userrelated,pre}$代表代理商相关代理用户预考核费用  
代理商实际考核费用：
$$F_{assess,agent}=F_{assess,agent,pre}-\sum F_{assess,user,pre}$$
#### 4.2.3 净收益
代理用户净收益：$$R_{response,user} = \sum_{d} \sum_{h \in H_d}F_{response,user,h} - F_{assess,user}$$ 
代理商净收益：$$R_{response,operator} = \sum_{d} \sum_{h \in H_d} (F_{response,agent,h} - \sum_{i} F_{response,user,h}) - F_{assess,agent}$$


## 5. 应急响应电量收益

### 5.1 启动条件

应急响应在以下情况启动：
1. 日前响应出清结果未满足D日响应需求容量的1.1倍
2. 日内出现新增全网缺口时（预测5小时内出现新增缺口）

### 5.2 应急响应价格

$$P_{emergency,h} = P_{clear,h} \times 0.1$$

### 5.3 应急响应收益计算

#### 5.3.1 响应费用
$$R_{emergency} = \sum_{d} \sum_{h \in H_{emergency,d}} Q_{effective,emergency,h} \times P_{emergency,h}$$

其中，$H_{emergency,d}$ 为第d日的应急响应小时集合。

## 6. 特殊情况处理
民生保障等超过110%不算作有效容量且超出部分要考核




---

## 重要说明

### 收益构成
电力用户参与需求侧市场化响应的收益包括**三个组成部分**：
1. **备用容量收益**：基于中标容量的固定收益
2. **日前响应电量收益**：基于实际响应效果的变动收益（主要收益来源）
3. **应急响应电量收益**：在紧急情况下的响应收益（价格为日前价格的**10%**，收益较低）

### 时间层级处理
- **有效响应容量认定**：按小时进行，每小时独立判断是否满足响应条件
- **日收益计算**：将当日各响应小时的有效响应容量汇总后，按日出清价格结算



