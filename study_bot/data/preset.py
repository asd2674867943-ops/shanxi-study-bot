"""
预置科目与章节数据
山西专升本 电气工程及其自动化
- 数学：行列式 + 概率 → 考研水平
- 电路分析：已完成一轮 → 考研强化水平
- 英语：零基础 → CET-4 水平
"""

# 科目定义
SUBJECTS = [
    {"name": "电路分析", "category": "professional", "max_score": 150},
    {"name": "英语",     "category": "public",       "max_score": 50},
    {"name": "高等数学", "category": "public",       "max_score": 100},
]

# ============================================================
# 各科目章节定义（含重要度、难度、考研/四级额外内容）
# ============================================================

CHAPTERS = {
    # ============================================================
    # 高等数学 — 考研水平
    # 用户现状：行列式 + 概率 未学，其他已完成
    # 目标：达到考研数学水平
    # ============================================================
    "高等数学": [
        # --- 已完成部分（复习+考研强化）---
        {"name": "函数、极限与连续",           "importance": 5, "difficulty": 3, "status": "review"},
        {"name": "导数与微分",                 "importance": 5, "difficulty": 3, "status": "review"},
        {"name": "微分中值定理与导数应用",     "importance": 5, "difficulty": 4, "status": "review"},
        {"name": "不定积分",                   "importance": 5, "difficulty": 3, "status": "review"},
        {"name": "定积分及其应用",             "importance": 5, "difficulty": 4, "status": "review"},
        {"name": "微分方程",                   "importance": 4, "difficulty": 4, "status": "review"},
        {"name": "向量代数与空间解析几何",     "importance": 3, "difficulty": 4, "status": "review"},
        {"name": "多元函数微分学",             "importance": 4, "difficulty": 4, "status": "review"},
        {"name": "重积分",                     "importance": 5, "difficulty": 5, "status": "review"},
        {"name": "曲线积分与曲面积分",         "importance": 3, "difficulty": 5, "status": "review"},
        {"name": "无穷级数",                   "importance": 3, "difficulty": 5, "status": "review"},
        # --- 未完成部分（新学+考研强化）---
        {"name": "行列式",                     "importance": 5, "difficulty": 3, "status": "learning",
         "sub_topics": [
             "行列式的定义与性质",
             "行列式按行（列）展开",
             "克拉默法则",
             "范德蒙行列式",
             "抽象行列式的计算",
         ],
         "kaoyan_focus": "行列式是线性代数的基石，考研中常与矩阵、方程组结合出题，需要熟练掌握计算方法"},
        {"name": "矩阵及其运算",               "importance": 5, "difficulty": 3, "status": "learning",
         "sub_topics": [
             "矩阵的概念与运算",
             "逆矩阵与伴随矩阵",
             "矩阵的秩",
             "分块矩阵",
         ],
         "kaoyan_focus": "矩阵运算是考研线代核心，重点：求逆矩阵、矩阵方程、秩的计算"},
        {"name": "向量组与线性方程组",         "importance": 5, "difficulty": 4, "status": "learning",
         "sub_topics": [
             "向量组的线性相关性",
             "极大线性无关组",
             "齐次与非齐次线性方程组",
             "基础解系与通解",
         ],
         "kaoyan_focus": "每年必考大题，重点：判断线性相关性、求基础解系"},
        {"name": "特征值与特征向量",           "importance": 5, "difficulty": 4, "status": "learning",
         "sub_topics": [
             "特征值与特征向量的定义与计算",
             "相似矩阵与对角化",
             "实对称矩阵的正交对角化",
         ],
         "kaoyan_focus": "考研线代压轴题常考，重点：对角化、实对称矩阵"},
        {"name": "二次型",                     "importance": 4, "difficulty": 4, "status": "learning",
         "sub_topics": [
             "二次型及其矩阵表示",
             "配方法与正交变换法",
             "正定二次型",
         ],
         "kaoyan_focus": "常与特征值结合考查，重点：正定性的判断"},
        {"name": "概率论基础",                 "importance": 5, "difficulty": 3, "status": "learning",
         "sub_topics": [
             "随机事件与概率",
             "条件概率与全概率公式",
             "贝叶斯公式",
             "事件的独立性",
         ],
         "kaoyan_focus": "概率论入门，理解基本概念，为后续打基础"},
        {"name": "随机变量及其分布",           "importance": 5, "difficulty": 3, "status": "learning",
         "sub_topics": [
             "离散型随机变量",
             "连续型随机变量",
             "分布函数",
             "常见分布（二项/泊松/均匀/指数/正态）",
         ],
         "kaoyan_focus": "考研概率核心章节，必须熟练掌握各分布的性质与应用"},
        {"name": "多维随机变量",               "importance": 4, "difficulty": 4, "status": "learning",
         "sub_topics": [
             "联合分布与边缘分布",
             "条件分布",
             "随机变量的独立性",
         ],
         "kaoyan_focus": "易考综合题，重点：联合分布→边缘分布"},
        {"name": "随机变量的数字特征",         "importance": 5, "difficulty": 3, "status": "learning",
         "sub_topics": [
             "数学期望",
             "方差与标准差",
             "协方差与相关系数",
         ],
         "kaoyan_focus": "每年必考，需要熟练掌握期望、方差的计算技巧"},
        {"name": "大数定律与中心极限定理",     "importance": 3, "difficulty": 4, "status": "learning",
         "sub_topics": [
             "切比雪夫不等式",
             "大数定律",
             "中心极限定理",
         ],
         "kaoyan_focus": "理解为主，会用中心极限定理做近似计算"},
        {"name": "数理统计基础",               "importance": 4, "difficulty": 3, "status": "learning",
         "sub_topics": [
             "样本与统计量",
             "抽样分布（卡方/t/F分布）",
             "参数估计（点估计/区间估计）",
             "假设检验",
         ],
         "kaoyan_focus": "考研常见题型：求矩估计和最大似然估计"},
    ],

    # ============================================================
    # 电路分析 — 考研强化水平（已一轮）
    # 用户现状：已完成一轮学习
    # 目标：达到考研（电气工程）电路水平
    # ============================================================
    "电路分析": [
        # 基础章节（巩固+深化）
        {"name": "电路的基本概念与基本定律", "importance": 4, "difficulty": 2, "status": "consolidate",
         "sub_topics": [
             "电压、电流参考方向",
             "电功率与能量",
             "电阻元件与欧姆定律",
             "独立源与受控源",
             "基尔霍夫定律（KCL/KVL）",
         ],
         "kaoyan_focus": "基础概念必须精准，KCL/KVL是后续所有分析的基础"},
        {"name": "电阻电路的等效变换",       "importance": 4, "difficulty": 3, "status": "consolidate",
         "sub_topics": [
             "电阻串联、并联与混联",
             "Y-△等效变换",
             "电源的等效变换（实际电源模型）",
             "输入电阻",
         ],
         "kaoyan_focus": "等效变换技巧在考研中非常实用，可简化复杂电路"},
        {"name": "电阻电路的一般分析方法",   "importance": 5, "difficulty": 3, "status": "consolidate",
         "sub_topics": [
             "支路电流法",
             "网孔电流法",
             "回路电流法",
             "节点电压法",
         ],
         "kaoyan_focus": "节点电压法是考研最常用方法，必须非常熟练"},
        {"name": "电路定理",                 "importance": 5, "difficulty": 4, "status": "strengthen",
         "sub_topics": [
             "叠加定理",
             "戴维南定理",
             "诺顿定理",
             "最大功率传输定理",
             "替代定理",
             "特勒根定理",
             "互易定理",
         ],
         "kaoyan_focus": "戴维南定理是考研必考重点！叠加定理也高频出现"},
        # 进阶章节（考研强化）
        {"name": "含有运算放大器的电阻电路", "importance": 2, "difficulty": 3, "status": "strengthen",
         "sub_topics": [
             "理想运放特性（虚短、虚断）",
             "反相/同相比例器",
             "加法器与减法器",
             "积分器与微分器",
         ],
         "kaoyan_focus": "掌握虚短虚断即可，考研命题频率不高"},
        {"name": "一阶电路的时域分析",       "importance": 5, "difficulty": 4, "status": "strengthen",
         "sub_topics": [
             "动态元件（电容、电感）的伏安特性",
             "初始条件的确定（换路定则）",
             "一阶电路的零输入响应",
             "一阶电路的零状态响应",
             "一阶电路的全响应（三要素法）",
             "阶跃响应与冲激响应",
         ],
         "kaoyan_focus": "三要素法是必考内容，需要熟练运用求解一阶电路"},
        {"name": "二阶电路的时域分析",       "importance": 3, "difficulty": 5, "status": "strengthen",
         "sub_topics": [
             "二阶电路微分方程的建立",
             "RLC串联电路的零输入响应",
             "过阻尼/临界阻尼/欠阻尼",
             "RLC串联电路的零状态响应",
         ],
         "kaoyan_focus": "理解三种阻尼状态的物理意义，掌握求解方法"},
        {"name": "正弦稳态电路的分析（相量法）", "importance": 5, "difficulty": 5, "status": "strengthen",
         "sub_topics": [
             "正弦量的相量表示",
             "电路定律的相量形式（相量形式的KCL/KVL）",
             "阻抗与导纳",
             "正弦稳态电路的相量分析法",
             "相量图",
         ],
         "kaoyan_focus": "正弦稳态分析是考研电路重中之重，每年必考大题"},
        {"name": "正弦稳态电路的功率",       "importance": 5, "difficulty": 4, "status": "strengthen",
         "sub_topics": [
             "瞬时功率、平均功率",
             "无功功率、视在功率",
             "复功率",
             "功率因数及其提高",
             "最大功率传输（共轭匹配）",
         ],
         "kaoyan_focus": "功率因数提高是常考点，复功率计算必须掌握"},
        {"name": "含有耦合电感的电路",       "importance": 4, "difficulty": 4, "status": "strengthen",
         "sub_topics": [
             "互感与同名端",
             "耦合电感的伏安关系",
             "去耦等效变换",
             "理想变压器",
             "空心变压器",
         ],
         "kaoyan_focus": "去耦等效变换是解题关键，理想变压器比例变换要熟"},
        {"name": "三相电路",                 "importance": 4, "difficulty": 4, "status": "strengthen",
         "sub_topics": [
             "三相电源",
             "对称三相电路的计算",
             "不对称三相电路的分析",
             "三相电路的功率及其测量",
         ],
         "kaoyan_focus": "对称三相电路化简为单相计算是最常用方法"},
        {"name": "非正弦周期电流电路",       "importance": 2, "difficulty": 3, "status": "review",
         "sub_topics": [
             "非正弦周期信号的傅里叶级数",
             "有效值、平均值和平均功率",
             "非正弦周期电流电路的计算（谐波分析法）",
         ],
         "kaoyan_focus": "会用叠加定理分别计算各次谐波响应再叠加"},
        {"name": "二端口网络",               "importance": 3, "difficulty": 4, "status": "strengthen",
         "sub_topics": [
             "二端口网络的Z/Y/T/H参数",
             "二端口网络的等效电路",
             "二端口网络的连接（级联/串联/并联）",
         ],
         "kaoyan_focus": "重点掌握Z/Y/T参数的计算和参数间的转换"},
        {"name": "动态电路的复频域分析",     "importance": 3, "difficulty": 5, "status": "strengthen",
         "sub_topics": [
             "拉普拉斯变换基础",
             "电路元件的s域模型",
             "基尔霍夫定律的s域形式",
             "用拉普拉斯变换分析动态电路",
             "网络函数",
         ],
         "kaoyan_focus": "拉氏变换法解动态电路比时域法更系统，考研常见"},
        # 考研额外内容
        {"name": "电路方程的矩阵形式",       "importance": 2, "difficulty": 4, "status": "advanced",
         "sub_topics": [
             "关联矩阵、回路矩阵、割集矩阵",
             "节点电压方程的矩阵形式",
             "回路电流方程的矩阵形式",
         ],
         "kaoyan_focus": "部分院校考研会涉及，了解为主"},
        {"name": "非线性电路",               "importance": 1, "difficulty": 5, "status": "advanced",
         "sub_topics": [
             "非线性电阻元件",
             "非线性电阻电路的分析",
             "小信号分析法",
         ],
         "kaoyan_focus": "考研中较少出现，了解小信号分析法即可"},
    ],

    # ============================================================
    # 英语 — 零基础 → CET-4 水平
    # 用户现状：零基础
    # 目标：每年3月前达到四级水平，专升本英语50分
    # ============================================================
    "英语": [
        # Phase 1: 基础阶段（0→初中水平）
        {"name": "英语基础：音标与拼读",       "importance": 3, "difficulty": 1, "status": "foundation",
         "sub_topics": [
             "48个国际音标认读",
             "自然拼读规则",
             "单词拼写规律",
         ],
         "cet4_focus": "基础中的基础，帮助正确朗读和记忆单词"},
        {"name": "基础词汇积累（初中1500词）", "importance": 5, "difficulty": 2, "status": "foundation",
         "sub_topics": [
             "日常高频词汇（600词）",
             "动词基础（be/do/have/go/come等）",
             "名词基础（时间/地点/人物/物品）",
             "形容词基础（大小/好坏/颜色等）",
         ],
         "cet4_focus": "先建立基础词汇量，为后续学习打基础"},
        {"name": "基础语法：句子成分与时态",   "importance": 5, "difficulty": 2, "status": "foundation",
         "sub_topics": [
             "五大基本句型",
             "一般现在时/一般过去时/一般将来时",
             "现在进行时/过去进行时",
             "现在完成时",
         ],
         "cet4_focus": "掌握基本句子结构，能读写简单句"},
        # Phase 2: 提升阶段（初中→高中水平）
        {"name": "核心词汇积累（高中2000词+四级高频词）", "importance": 5, "difficulty": 3, "status": "building",
         "sub_topics": [
             "四级高频词汇（按频率排序，前1000词）",
             "专升本英语核心800词",
             "动词短语（take/look/put/get/turn等）",
             "词根词缀法记单词",
         ],
         "cet4_focus": "词汇是英语学习的基石，坚持每日背词"},
        {"name": "语法强化：从句与非谓语",     "importance": 5, "difficulty": 3, "status": "building",
         "sub_topics": [
             "名词性从句（主语/宾语/表语/同位语从句）",
             "定语从句（关系代词/关系副词）",
             "状语从句（时间/原因/条件/让步等）",
             "非谓语动词（不定式/动名词/分词）",
         ],
         "cet4_focus": "从句是四级阅读长难句的基础，必须攻克"},
        {"name": "语法强化：虚拟语气与特殊句式", "importance": 4, "difficulty": 3, "status": "building",
         "sub_topics": [
             "虚拟语气（条件句/名词性从句中的虚拟）",
             "倒装句",
             "强调句",
             "省略句",
         ],
         "cet4_focus": "四级翻译和写作中会涉及，阅读中也常见"},
        # Phase 3: 四级冲刺阶段
        {"name": "阅读理解（事实细节题）",       "importance": 5, "difficulty": 2, "status": "practicing",
         "sub_topics": [
             "快速定位关键词",
             "同义替换识别",
             "数字/专有名词定位",
             "排除干扰项技巧",
         ],
         "cet4_focus": "阅读理解占分最大，事实细节题是基础分"},
        {"name": "阅读理解（推理判断+主旨大意）", "importance": 5, "difficulty": 3, "status": "practicing",
         "sub_topics": [
             "推理判断题",
             "主旨大意题",
             "作者态度题",
             "词义猜测题",
         ],
         "cet4_focus": "提高阅读速度和准确率，每天坚持精读+泛读"},
        {"name": "完形填空",                     "importance": 4, "difficulty": 4, "status": "practicing",
         "sub_topics": [
             "上下文逻辑衔接",
             "固定搭配",
             "词义辨析",
             "语法结构判断",
         ],
         "cet4_focus": "综合考察词汇和语法，多做真题熟悉套路"},
        {"name": "翻译（英译汉）",               "importance": 4, "difficulty": 3, "status": "practicing",
         "sub_topics": [
             "长难句拆分",
             "定语从句翻译技巧",
             "被动语态翻译",
             "文化背景词汇",
         ],
         "cet4_focus": "英译汉相对容易，注意汉语表达的流畅性"},
        {"name": "翻译（汉译英）",               "importance": 3, "difficulty": 4, "status": "practicing",
         "sub_topics": [
             "核心句型翻译",
             "中国文化词汇",
             "常见句式转换",
             "时态与语态选择",
         ],
         "cet4_focus": "四级翻译常考中国文化主题，需积累相关词汇"},
        {"name": "写作基础（应用文）",           "importance": 5, "difficulty": 3, "status": "practicing",
         "sub_topics": [
             "书信格式（建议信/感谢信/申请信/邀请信）",
             "通知/启事",
             "邮件写作",
             "开头结尾模板",
         ],
         "cet4_focus": "四级写作常考应用文，模板+灵活运用即可"},
        {"name": "写作进阶（议论文）",           "importance": 4, "difficulty": 4, "status": "practicing",
         "sub_topics": [
             "议论文结构（三段式）",
             "论点论据组织",
             "衔接词与过渡句",
             "常见话题素材积累",
         ],
         "cet4_focus": "议论文需要逻辑清晰，论据充分"},
        {"name": "听力基础训练",                 "importance": 4, "difficulty": 4, "status": "practicing",
         "sub_topics": [
             "四级听力题型分析",
             "短对话技巧",
             "长对话与短文理解",
             "听写训练",
         ],
         "cet4_focus": "听力需要长期积累，每天坚持15-30分钟"},
        {"name": "四级真题综合训练",             "importance": 5, "difficulty": 3, "status": "exam_prep",
         "sub_topics": [
             "限时模拟考试",
             "错题分析与归纳",
             "各题型时间分配",
             "考前冲刺策略",
         ],
         "cet4_focus": "考前一月开始刷真题，熟悉考试节奏"},
        {"name": "专升本英语真题训练",           "importance": 5, "difficulty": 3, "status": "exam_prep",
         "sub_topics": [
             "山西专升本英语历年真题",
             "50分题型分布与策略",
             "专升本与四级差异分析",
             "高频考点总结",
         ],
         "cet4_focus": "专升本英语难度低于四级，但题型有差异，需要针对性训练"},
    ],
}


# ============================================================
# 学习阶段定义
# ============================================================

# 英语学习路径（零基础→四级）
ENGLISH_LEARNING_PATH = {
    "phase1_foundation": {
        "name": "基础入门（0→初中水平）",
        "duration_weeks": 8,
        "weekly_hours": 10,  # 每天约1.5小时
        "milestones": [
            "掌握48个音标，能正确拼读单词",
            "掌握初中1500核心词汇",
            "掌握5种基本时态",
            "能读懂简单对话和短文",
        ],
        "chapters": [
            "英语基础：音标与拼读",
            "基础词汇积累（初中1500词）",
            "基础语法：句子成分与时态",
        ],
    },
    "phase2_building": {
        "name": "能力提升（初中→高中水平）",
        "duration_weeks": 12,
        "weekly_hours": 12,
        "milestones": [
            "词汇量达到3500+（覆盖四级高频词）",
            "掌握从句和非谓语动词",
            "能读懂高中难度文章",
            "能写简单的应用文",
        ],
        "chapters": [
            "核心词汇积累（高中2000词+四级高频词）",
            "语法强化：从句与非谓语",
            "语法强化：虚拟语气与特殊句式",
        ],
    },
    "phase3_practice": {
        "name": "四级冲刺（达到CET-4水平）",
        "duration_weeks": 16,
        "weekly_hours": 14,
        "milestones": [
            "词汇量达到4500+",
            "四级阅读正确率70%+",
            "能写规范的四级作文",
            "专升本英语能达到40+/50",
        ],
        "chapters": [
            "所有 reading/writing/translation 章节",
            "专升本英语真题训练",
        ],
    },
}

# 数学学习路径（行列式+概率 → 考研水平）
MATH_LEARNING_PATH = {
    "phase1_determinant": {
        "name": "线性代数：行列式→矩阵→方程组",
        "duration_weeks": 6,
        "weekly_hours": 8,
        "chapters_order": [
            "行列式",
            "矩阵及其运算",
            "向量组与线性方程组",
        ],
        "milestones": [
            "掌握行列式计算方法",
            "熟练矩阵运算",
            "能解各类线性方程组",
        ],
    },
    "phase2_eigenvalue": {
        "name": "线性代数：特征值→二次型",
        "duration_weeks": 4,
        "weekly_hours": 8,
        "chapters_order": [
            "特征值与特征向量",
            "二次型",
        ],
        "milestones": [
            "掌握特征值与特征向量的计算",
            "会判断二次型的正定性",
        ],
    },
    "phase3_probability": {
        "name": "概率论与数理统计",
        "duration_weeks": 8,
        "weekly_hours": 8,
        "chapters_order": [
            "概率论基础",
            "随机变量及其分布",
            "多维随机变量",
            "随机变量的数字特征",
            "大数定律与中心极限定理",
            "数理统计基础",
        ],
        "milestones": [
            "掌握常见分布及其性质",
            "熟练计算期望、方差",
            "掌握参数估计方法",
        ],
    },
}

# 电路学习路径（考研强化）
CIRCUIT_LEARNING_PATH = {
    "phase1_consolidate": {
        "name": "基础巩固（重温核心定理与方法）",
        "duration_weeks": 3,
        "weekly_hours": 8,
        "focus": "确保直流电路分析零盲区",
        "chapters": [
            "电路的基本概念与基本定律",
            "电阻电路的等效变换",
            "电阻电路的一般分析方法",
            "电路定理",
        ],
    },
    "phase2_dynamic": {
        "name": "动态电路强化",
        "duration_weeks": 4,
        "weekly_hours": 8,
        "focus": "一阶/二阶电路 + 复频域分析",
        "chapters": [
            "一阶电路的时域分析",
            "二阶电路的时域分析",
            "动态电路的复频域分析",
        ],
    },
    "phase3_sinusoidal": {
        "name": "正弦稳态电路强化",
        "duration_weeks": 4,
        "weekly_hours": 8,
        "focus": "相量法 + 功率 + 三相电路",
        "chapters": [
            "正弦稳态电路的分析（相量法）",
            "正弦稳态电路的功率",
            "含有耦合电感的电路",
            "三相电路",
        ],
    },
    "phase4_advanced": {
        "name": "综合提升与考研真题",
        "duration_weeks": 3,
        "weekly_hours": 8,
        "focus": "二端口/非正弦 + 真题训练",
        "chapters": [
            "二端口网络",
            "非正弦周期电流电路",
            "含有运算放大器的电阻电路",
        ],
    },
}


# ============================================================
# 每日时间分配建议
# ============================================================

# 上课日时间分配（3小时 = 180分钟）
CLASS_DAY_ALLOCATION = {
    "电路分析": 75,   # 75分钟（专业课，150分）
    "高等数学": 60,   # 60分钟（公共课，100分）
    "英语":     45,   # 45分钟（公共课，50分，但需补基础阶段加时间）
}

# 空闲日时间分配（6小时 = 360分钟）
FREE_DAY_ALLOCATION = {
    "电路分析": 120,  # 2小时
    "高等数学": 120,  # 2小时
    "英语":     90,   # 1.5小时
    "测试/复习": 30,  # 0.5小时（错题回顾等）
}

# 周六测试日时间分配（4小时 = 240分钟）
SATURDAY_ALLOCATION = {
    "周测做题":   120,  # 2小时做题
    "批改复盘":   60,   # 1小时对答案+分析
    "错题整理":   60,   # 1小时整理错题+薄弱点复习
}
