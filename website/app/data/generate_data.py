"""
生成 800+ 条电商评论测试数据 + Few-shot 样本库 + Golden 数据集。
运行: python3 generate_data.py
输出: test_reviews_800.csv, fewshot_library.json, golden_dataset.json
"""
import csv, json, random, os
from datetime import datetime, timedelta

random.seed(42)

# ============================================================
# 商品池
# ============================================================
PRODUCTS = [
    {"id": "P001", "name": "运动跑鞋 Air-Max", "cat": "运动鞋", "price": 299},
    {"id": "P002", "name": "经典休闲板鞋", "cat": "休闲鞋", "price": 199},
    {"id": "P003", "name": "专业篮球鞋 Pro", "cat": "运动鞋", "price": 599},
    {"id": "P004", "name": "轻量登山徒步鞋", "cat": "户外鞋", "price": 399},
    {"id": "P005", "name": "商务正装皮鞋", "cat": "皮鞋", "price": 459},
    {"id": "P006", "name": "夏季透气网面鞋", "cat": "运动鞋", "price": 179},
    {"id": "P007", "name": "儿童卡通运动鞋", "cat": "童鞋", "price": 149},
    {"id": "P008", "name": "防滑老人健步鞋", "cat": "老年鞋", "price": 259},
]

USERS = [
    {"id": "U{:03d}", "tier": "Plus会员", "ratio": 0.15},
    {"id": "U{:03d}", "tier": "普通会员", "ratio": 0.55},
    {"id": "U{:03d}", "tier": "新用户", "ratio": 0.25},
    {"id": "U{:03d}", "tier": "Plus会员", "ratio": 0.05},
]

# ============================================================
# 评论模板库（按情感+分类组织）
# ============================================================

POSITIVE_TEMPLATES = {
    "产品质量": [
        "质量很好，穿着很舒服，透气性也不错",
        "做工精细，没有线头，材质手感很好",
        "穿过一周了没有任何问题，质量杠杠的",
        "鞋底很软，走路不累，非常满意",
        "颜色很正，跟图片一模一样，很喜欢",
        "第二次回购了，品质一如既往的好",
        "细节处理得很好，大品牌就是不一样",
        "穿了一个月了还没变形，质量确实不错",
        "材质柔软，贴合脚型，超出预期",
        "鞋子很轻，跑步穿特别合适",
        "做工扎实，耐磨性很好",
        "外观设计很时尚，朋友们都问在哪买的",
        "包裹性很好，运动时穿着很稳定",
        "内衬很舒服，光脚穿也不磨",
        "抓地力强，下雨天也不滑",
    ],
    "物流配送": [
        "快递很快，第二天就收到了",
        "包装完好，每只鞋都有独立包装",
        "物流速度很快，下单到收货只用了两天",
        "包装很用心，鞋盒外面还套了保护箱",
        "顺丰发货，隔天就到了，非常快",
        "快递员态度很好，送货上门",
    ],
    "服务态度": [
        "客服态度很好，耐心解答了我的问题",
        "售后处理很快，有问题马上解决了",
        "客服回复很快，帮我查了物流信息",
        "服务很到位，主动打电话确认尺码",
    ],
    "价格争议": [
        "性价比很高，这个价格买到真的很划算",
        "比实体店便宜多了，质量一样好",
        "赶上活动买的，超级划算",
        "这个价位能买到这种品质，很值",
    ],
}

NEGATIVE_TEMPLATES = {
    "产品质量": [
        "穿了一周鞋底就开胶了，质量太差",
        "掉色严重，把袜子都染红了",
        "鞋面破了，才穿了两次",
        "有刺鼻气味，晾了三天还有味道",
        "尺码偏小，按正常码买根本穿不了",
        "鞋底太硬了，走路脚疼",
        "穿了几天鞋垫就塌了",
        "线头很多，感觉像残次品",
        "磨脚后跟，每次穿都起泡",
        "鞋面起球了，质量堪忧",
        "防水效果很差，下雨天穿一次就进水",
        "鞋带很容易松，走路经常要重新系",
        "鞋舌老是歪到一边，设计有缺陷",
        "内衬掉色，把脚都染了",
        "穿了一个月鞋底就磨平了",
        "接缝处开裂了，做工太粗糙",
        "鞋子异味严重，放了活性炭也没用",
        "表面的涂层掉了一快，很难看",
    ],
    "物流配送": [
        "发货太慢了，等了十天才收到",
        "物流暴力运输，鞋盒都压扁了",
        "快递把包裹弄丢了，又重新补发",
        "承诺48小时发货结果拖了5天",
        "包装太简陋，鞋子直接放在快递袋里",
        "快递员把包裹扔在门口就走了",
        "发的根本不是我要的颜色",
        "漏发了一双，联系客服还没回复",
    ],
    "服务态度": [
        "客服态度特别差，问什么都不耐烦",
        "售后推脱责任，不给处理退换货",
        "客服一直不回消息，态度恶劣",
        "退换货流程太麻烦了，客服还推脱",
        "答应了退款却一直不处理",
        "客服说补偿优惠券结果根本没收到",
    ],
    "价格争议": [
        "价格降太快了，买完三天就降价50块",
        "太贵了，不值这个价",
        "双十一买的比现在还便宜，被坑了",
        "同样的鞋子别的店便宜很多",
    ],
}

MIXED_TEMPLATES = [
    ("质量不错穿着舒服但价格有点贵性价比不高", "价格争议", 1),
    ("鞋子好看但磨脚穿着不太舒服", "产品质量", 2),
    ("款式很好但是尺码严重偏小建议买大两码", "产品质量", 2),
    ("颜色好看质量可以就是发货实在太慢了", "物流配送", 2),
    ("舒适度不错但鞋底不太耐磨穿了一个月就磨平了", "产品质量", 2),
    ("质量对得起价格但是包装太简陋了", "物流配送", 1),
    ("款式很满意面料也不错就是有点异味", "产品质量", 2),
    ("整体还行物流快但客服态度需要改善", "服务态度", 2),
    ("做工精细穿着舒服就是款式选择太少", "产品质量", 1),
    ("买给老公的他说还行就是颜色跟图片有点差距", "产品质量", 1),
]

NEUTRAL_TEMPLATES = [
    "还行吧，一般般",
    "凑合穿吧，没什么特别",
    "刚收到还没穿，看起来还行",
    "不是我想象的颜色，但也能接受",
    "帮同事买的，他说还行",
    "还没穿，先评价一下",
]

SARCASTIC_TEMPLATES = [
    ("真是买了个祖宗回来，穿两次就坏了", "产品质量", 2),
    ("太浮夸了，不过本仙女就是喜欢这种全场焦点的感觉", "产品质量", 1),
    ("呵呵，就当买个教训吧", "产品质量", 2),
    ("这质量绝了，穿了三天比我穿了三年还旧", "产品质量", 2),
    ("买了个活爹回来，供着吧不能穿", "产品质量", 2),
]

MEANINGLESS_TEMPLATES = [
    "111111",
    "好",
    "不错",
    "好评",
    "默认好评",
    "😂😂😂",
    "还行",
    "嗯",
    "。。。。。。",
    "好評好評好評",
]

# ============================================================
# 生成 800+ 条评论
# ============================================================

def generate_reviews(n=820):
    reviews = []
    used_ids = set()
    review_id = 1
    base_date = datetime(2024, 6, 1)

    # 用户池
    user_pool = []
    uid = 1
    for u_template in USERS:
        count = int(u_template["ratio"] * 150)
        for _ in range(count):
            user_pool.append({"id": u_template["id"].format(uid), "tier": u_template["tier"]})
            uid += 1

    # 分配策略：55%正面, 22%负面, 10%混合, 8%中性, 5%反讽/无意义
    distribution = (
        [("positive",)] * 450 +
        [("negative",)] * 180 +
        [("mixed",)] * 80 +
        [("neutral",)] * 65 +
        [("sarcastic",)] * 25 +
        [("meaningless",)] * 20
    )
    random.shuffle(distribution)

    for i, dist in enumerate(distribution):
        if i >= n:
            break

        product = random.choice(PRODUCTS)
        user = random.choice(user_pool)
        has_image = random.random() < 0.15
        days_offset = random.randint(0, 365)
        review_date = base_date + timedelta(days=days_offset)
        rating = 5  # default

        review_type = dist[0]

        if review_type == "positive":
            cat = random.choice(list(POSITIVE_TEMPLATES.keys()))
            content = random.choice(POSITIVE_TEMPLATES[cat])
            rating = random.choice([4, 5])
        elif review_type == "negative":
            cat = random.choice(list(NEGATIVE_TEMPLATES.keys()))
            content = random.choice(NEGATIVE_TEMPLATES[cat])
            rating = random.choice([1, 2])
        elif review_type == "mixed":
            content, cat, _ = random.choice(MIXED_TEMPLATES)
            rating = random.choice([2, 3, 4])
        elif review_type == "neutral":
            content = random.choice(NEUTRAL_TEMPLATES)
            rating = random.choice([3, 4])
        elif review_type == "sarcastic":
            content, cat, _ = random.choice(SARCASTIC_TEMPLATES)
            rating = random.choice([1, 2, 5])  # 5星反讽常见
        else:  # meaningless
            content = random.choice(MEANINGLESS_TEMPLATES)
            rating = random.randint(1, 5)

        rid = f"T{review_id:04d}"
        reviews.append({
            "review_id": rid,
            "review_content": content,
            "rating": rating,
            "has_image_or_video": has_image,
            "user_id": user["id"],
            "user_tier": user["tier"],
            "review_timestamp": review_date.strftime("%Y-%m-%d"),
            "product_id": product["id"],
            "product_name": product["name"],
            "product_category": product["cat"],
            "order_price": product["price"] + random.choice([-20, 0, 0, 0, 20, 50]),
        })
        review_id += 1

    return reviews


def save_csv(reviews, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=reviews[0].keys())
        w.writeheader()
        w.writerows(reviews)
    print(f"CSV saved: {path} ({len(reviews)} rows)")


# ============================================================
# Few-shot 样本库
# ============================================================

FEWSHOT_LIBRARY = [
    {
        "id": "FS001",
        "category": "反讽识别",
        "pattern": "表面用词负面/戏谑，实为极度差评",
        "difficulty": "hard",
        "review": "真是买了个活爹回来，供着吧不能穿",
        "extraction": {
            "sentiment": "负面", "primary_category": "产品质量", "urgency_level": 2,
            "core_issue_summary": "鞋子质量极差无法穿着",
            "extracted_keywords": ["质量差", "无法穿"], "confidence": 0.75
        },
        "notes": "\"活爹\"\"供着\"是反讽表达，真实意思是鞋子完全不能穿。LLM 需要绕过字面意思，理解语气反转。"
    },
    {
        "id": "FS002",
        "category": "无意义内容",
        "pattern": "纯数字/纯表情/无实质评价",
        "difficulty": "easy",
        "review": "111111",
        "extraction": {
            "sentiment": "中性", "primary_category": "无效评论", "urgency_level": 1,
            "core_issue_summary": "无实质内容",
            "extracted_keywords": ["无意义"], "confidence": 0.98
        },
        "notes": "键盘连击式评论，不包含任何有用信息。应标记为无效评论并给高置信度。"
    },
    {
        "id": "FS003",
        "category": "明贬暗褒",
        "pattern": "看似抱怨实则炫耀/满意",
        "difficulty": "hard",
        "review": "太浮夸了，不过本仙女就是喜欢这种全场焦点的感觉！",
        "extraction": {
            "sentiment": "正面", "primary_category": "产品质量", "urgency_level": 1,
            "core_issue_summary": "外观设计出众用户满意",
            "extracted_keywords": ["外观", "设计感", "满意"], "confidence": 0.80
        },
        "notes": "\"太浮夸\"表面是批评，但\"本仙女喜欢\"\"全场焦点\"揭示真实情感为正面。需要结合上下文理解。"
    },
    {
        "id": "FS004",
        "category": "混合情感",
        "pattern": "同时包含正面和负面评价",
        "difficulty": "medium",
        "review": "质量不错穿着舒服但价格有点贵性价比不高",
        "extraction": {
            "sentiment": "混合", "primary_category": "价格争议", "urgency_level": 1,
            "core_issue_summary": "质量好但价格偏贵",
            "extracted_keywords": ["质量好", "价格贵", "性价比低"], "confidence": 0.92
        },
        "notes": "评论同时包含正面（质量不错）和负面（价格贵），应标为'混合'而非单选一面。"
    },
    {
        "id": "FS005",
        "category": "纯正面",
        "pattern": "标准好评，无负面信号",
        "difficulty": "easy",
        "review": "鞋子质量很好穿着很舒服透气性也不错",
        "extraction": {
            "sentiment": "正面", "primary_category": "产品质量", "urgency_level": 1,
            "core_issue_summary": "质量好做工扎实透气",
            "extracted_keywords": ["质量好", "舒适", "透气"], "confidence": 0.95
        },
        "notes": "标准正面评价，无歧义，应给高置信度。关键词应从具体描述中提取。"
    },
    {
        "id": "FS006",
        "category": "反讽识别",
        "pattern": "五星好评但文字全在抱怨",
        "difficulty": "hard",
        "review": "五星好评！穿了三天鞋底掉了，客服已读不回，太棒了👍",
        "extraction": {
            "sentiment": "负面", "primary_category": "产品质量", "urgency_level": 3,
            "core_issue_summary": "鞋底脱落客服不理",
            "extracted_keywords": ["鞋底脱落", "客服不理", "质量差"], "confidence": 0.70
        },
        "notes": "典型反讽：开头'五星好评'是反语，后文揭示严重质量问题+客服失联。需降低置信度。"
    },
    {
        "id": "FS007",
        "category": "无意义内容",
        "pattern": "默认评价/系统自动填充",
        "difficulty": "easy",
        "review": "默认好评",
        "extraction": {
            "sentiment": "中性", "primary_category": "无效评论", "urgency_level": 1,
            "core_issue_summary": "系统默认评价",
            "extracted_keywords": ["默认评价"], "confidence": 0.98
        },
        "notes": "平台系统自动填充的默认好评，不代表用户真实评价。"
    },
    {
        "id": "FS008",
        "category": "安全红线",
        "pattern": "涉及安全/健康问题的高优评论",
        "difficulty": "hard",
        "review": "鞋子有刺鼻气味穿着后头晕恶心怀疑有毒物质超标",
        "extraction": {
            "sentiment": "负面", "primary_category": "产品质量", "urgency_level": 3,
            "core_issue_summary": "有害物质致身体不适",
            "extracted_keywords": ["刺鼻气味", "头晕", "有毒物质", "安全性"], "confidence": 0.85
        },
        "notes": "涉及健康安全问题的评论应标记为最高紧急度（3），需要立即响应。"
    },
    {
        "id": "FS009",
        "category": "混合情感",
        "pattern": "快递好但产品差",
        "difficulty": "medium",
        "review": "发货很快物流很棒但鞋子质量真的很一般穿几次就变形了",
        "extraction": {
            "sentiment": "混合", "primary_category": "产品质量", "urgency_level": 2,
            "core_issue_summary": "物流好但质量一般易变形",
            "extracted_keywords": ["物流快", "质量一般", "变形"], "confidence": 0.90
        },
        "notes": "跨维度混合：物流（正面）+ 产品质量（负面），应标为混合。"
    },
    {
        "id": "FS010",
        "category": "纯负面",
        "pattern": "明确的多维度差评",
        "difficulty": "easy",
        "review": "千万不要买质量差到离谱穿一次就开胶了找客服还态度恶劣",
        "extraction": {
            "sentiment": "负面", "primary_category": "产品质量", "urgency_level": 2,
            "core_issue_summary": "质量差开胶客服恶劣",
            "extracted_keywords": ["开胶", "质量差", "客服恶劣"], "confidence": 0.93
        },
        "notes": "明确负面，多个维度的不满。关键词应覆盖产品和客服两个维度。"
    },
    {
        "id": "FS011",
        "category": "价格争议",
        "pattern": "对降价不满",
        "difficulty": "medium",
        "review": "昨天刚买今天就降了50块这谁遭得住以后再也不买了",
        "extraction": {
            "sentiment": "负面", "primary_category": "价格争议", "urgency_level": 2,
            "core_issue_summary": "购买后立即降价不满",
            "extracted_keywords": ["降价", "50块", "不满"], "confidence": 0.90
        },
        "notes": "价格保护问题是电商常见投诉，虽不涉及产品本身但影响复购意愿。"
    },
    {
        "id": "FS012",
        "category": "物流投诉",
        "pattern": "暴力运输导致损坏",
        "difficulty": "medium",
        "review": "物流太暴力了鞋盒压成纸片鞋子表面都有压痕了",
        "extraction": {
            "sentiment": "负面", "primary_category": "物流配送", "urgency_level": 2,
            "core_issue_summary": "暴力运输致鞋盒鞋子损坏",
            "extracted_keywords": ["暴力运输", "鞋盒压坏", "鞋子有压痕"], "confidence": 0.92
        },
        "notes": "物流问题导致商品损坏，需要同时关注物流服务商和包装保护。"
    },
    {
        "id": "FS013",
        "category": "客服投诉",
        "pattern": "退换货被推脱",
        "difficulty": "medium",
        "review": "申请退货被拒了三次每次都说照片不清楚分明是故意刁难",
        "extraction": {
            "sentiment": "负面", "primary_category": "服务态度", "urgency_level": 2,
            "core_issue_summary": "退货申请被多次拒绝刁难",
            "extracted_keywords": ["退货被拒", "故意刁难", "客服"], "confidence": 0.88
        },
        "notes": "客服退换货流程中的推脱行为，属于服务态度问题。"
    },
    {
        "id": "FS014",
        "category": "无意义内容",
        "pattern": "纯 Emoji 表情",
        "difficulty": "easy",
        "review": "😂😂😂👍👍👍",
        "extraction": {
            "sentiment": "中性", "primary_category": "无效评论", "urgency_level": 1,
            "core_issue_summary": "纯表情无实质内容",
            "extracted_keywords": ["表情符号"], "confidence": 0.97
        },
        "notes": "纯 Emoji 评论不含可提取的文本信息，应标记为无效。"
    },
    {
        "id": "FS015",
        "category": "隐含好评",
        "pattern": "通过比较/行为暗示满意",
        "difficulty": "medium",
        "review": "回购的第二双了给家里老人也买了一双",
        "extraction": {
            "sentiment": "正面", "primary_category": "产品质量", "urgency_level": 1,
            "core_issue_summary": "再次购买并推荐家人使用",
            "extracted_keywords": ["回购", "推荐家人", "满意"], "confidence": 0.88
        },
        "notes": "用户行为（回购+给家人买）比口头好评更有说服力，应识别为正面。"
    },
    {
        "id": "FS016",
        "category": "尺码问题",
        "pattern": "尺码偏差导致的负面体验",
        "difficulty": "medium",
        "review": "按正常码数买的根本穿不了小了整整一码退货还要自己出运费",
        "extraction": {
            "sentiment": "负面", "primary_category": "产品质量", "urgency_level": 2,
            "core_issue_summary": "尺码严重偏小退货自付运费",
            "extracted_keywords": ["尺码偏小", "小一码", "退货运费"], "confidence": 0.90
        },
        "notes": "尺码问题是鞋类高频投诉，需要关注具体偏差幅度和退货体验。"
    },
    {
        "id": "FS017",
        "category": "混合情感",
        "pattern": "产品好但价格波动不满",
        "difficulty": "medium",
        "review": "鞋子本身质量没毛病但是刚买就参加活动直接便宜了80块",
        "extraction": {
            "sentiment": "混合", "primary_category": "价格争议", "urgency_level": 2,
            "core_issue_summary": "产品满意但降价太快",
            "extracted_keywords": ["质量好", "降价80", "不满"], "confidence": 0.87
        },
        "notes": "典型混合评价：产品 OK 但价格体验差。"
    },
    {
        "id": "FS018",
        "category": "安全红线",
        "pattern": "涉及虚假宣传/欺诈",
        "difficulty": "hard",
        "review": "说是真皮的其实是人造革的完全虚假宣传欺骗消费者",
        "extraction": {
            "sentiment": "负面", "primary_category": "产品质量", "urgency_level": 3,
            "core_issue_summary": "材质虚假宣传欺诈",
            "extracted_keywords": ["真皮", "人造革", "虚假宣传", "欺诈"], "confidence": 0.85
        },
        "notes": "涉及虚假宣传/消费欺诈的评论应提升为最高紧急度。"
    },
    {
        "id": "FS019",
        "category": "中性评价",
        "pattern": "刚收到未使用，无法判断",
        "difficulty": "easy",
        "review": "刚收到还没穿过看起来还行希望耐穿吧",
        "extraction": {
            "sentiment": "中性", "primary_category": "产品质量", "urgency_level": 1,
            "core_issue_summary": "刚收到尚未使用观望中",
            "extracted_keywords": ["新收到", "未使用", "观望"], "confidence": 0.82
        },
        "notes": "刚收到商品尚未形成明确判断，应标为中性。置信度应适度降低。"
    },
    {
        "id": "FS020",
        "category": "反讽识别",
        "pattern": "以感谢形式表达极端不满",
        "difficulty": "hard",
        "review": "谢谢商家让我体验了一次什么叫花钱买教训祝生意兴隆",
        "extraction": {
            "sentiment": "负面", "primary_category": "产品质量", "urgency_level": 2,
            "core_issue_summary": "质量差花钱买教训不满",
            "extracted_keywords": ["花钱买教训", "不满", "质量差"], "confidence": 0.72
        },
        "notes": "表面礼貌的感谢实则表达极度不满。\"祝生意兴隆\"在语境中是讽刺。"
    },
]


def save_fewshot(path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(FEWSHOT_LIBRARY, f, ensure_ascii=False, indent=2)
    print(f"Few-shot library saved: {path} ({len(FEWSHOT_LIBRARY)} examples)")


# ============================================================
# Golden 数据集
# ============================================================

def generate_golden(n=200):
    """生成带预期标签的黄金验证集。"""
    golden = []
    gid = 1

    # 精心构造：确保覆盖所有情感类型、所有分类、3级紧急度
    test_cases = [
        # (content, expected_sentiment, expected_category, expected_urgency, note)
        # ---- 正面 ----
        ("鞋子质量很好穿着很舒服透气性也不错", "正面", "产品质量", 1, "标准正面评价"),
        ("快递很快第二天就收到了包装也很完整", "正面", "物流配送", 1, "物流正面"),
        ("客服态度很好耐心解答了我的问题", "正面", "服务态度", 1, "客服正面"),
        ("性价比很高这个价格买到这个品质很值", "正面", "价格争议", 1, "性价比正面"),
        ("回购的第二双了给家里老人也买了一双", "正面", "产品质量", 1, "行为暗示满意（回购）"),
        ("做工精细没有线头材质手感很好", "正面", "产品质量", 1, "细节好评"),
        ("颜色很正跟图片一模一样很喜欢", "正面", "产品质量", 1, "色差无/满意"),
        ("鞋子很轻跑步穿特别合适透气好", "正面", "产品质量", 1, "功能性好评"),
        ("顺丰发货隔天就到了快递员态度很好", "正面", "物流配送", 1, "快递速度好评"),
        ("售后处理很快有问题马上就解决了", "正面", "服务态度", 1, "售后效率好评"),

        # ---- 负面-产品质量 ----
        ("穿了一周鞋底就开胶了质量太差", "负面", "产品质量", 2, "开胶-中优"),
        ("鞋子有刺鼻气味闻着头晕", "负面", "产品质量", 3, "有害气味-高优/红线"),
        ("掉色严重把袜子都染红了", "负面", "产品质量", 2, "掉色-中优"),
        ("鞋面破了才穿了两次", "负面", "产品质量", 2, "破损-中优"),
        ("鞋底太硬了走路脚疼不舒适", "负面", "产品质量", 2, "舒适度差-中优"),
        ("尺码严重偏小按正常码买根本穿不了", "负面", "产品质量", 2, "尺码偏差"),
        ("穿了几天鞋垫就塌了质量堪忧", "负面", "产品质量", 2, "鞋垫塌陷"),
        ("线头很多感觉像残次品做工太粗糙", "负面", "产品质量", 2, "做工粗糙"),
        ("磨脚后跟每次穿都起泡设计缺陷", "负面", "产品质量", 2, "磨脚"),
        ("说是真皮其实是人造革虚假宣传欺骗消费者", "负面", "产品质量", 3, "虚假宣传-高优"),

        # ---- 负面-物流 ----
        ("发货太慢了等了十天才收到", "负面", "物流配送", 2, "发货慢"),
        ("物流暴力运输鞋盒都压扁了", "负面", "物流配送", 2, "暴力运输"),
        ("快递把包裹弄丢了又重新补发等了一周", "负面", "物流配送", 2, "丢件"),
        ("承诺48小时发货结果拖了5天", "负面", "物流配送", 2, "承诺未兑现"),
        ("包装太简陋鞋子直接放快递袋里都变形了", "负面", "物流配送", 2, "包装不当"),
        ("发的根本不是我要的颜色发错货了", "负面", "物流配送", 2, "发错货"),

        # ---- 负面-客服 ----
        ("客服态度特别差问什么都是自动回复", "负面", "服务态度", 2, "客服态度差"),
        ("退换货流程太麻烦了客服推脱不给处理", "负面", "服务态度", 2, "退换货推脱"),
        ("申请退货被拒了三次每次都说照片不清楚", "负面", "服务态度", 2, "退货刁难"),
        ("客服一直不回消息态度恶劣", "负面", "服务态度", 2, "客服失联"),
        ("答应了退款却一直不处理拖了两周", "负面", "服务态度", 2, "退款拖延"),

        # ---- 负面-价格 ----
        ("价格降太快了买完三天就降价50块", "负面", "价格争议", 2, "短期降价"),
        ("太贵了不值这个价同样的东西别家便宜一半", "负面", "价格争议", 2, "性价比低"),
        ("双十一买的比现在还便宜被坑了", "负面", "价格争议", 2, "大促差价"),
        ("昨天刚买今天活动就降价了80块太坑了", "负面", "价格争议", 2, "活动降价"),

        # ---- 混合 ----
        ("质量不错穿着舒服但价格有点贵性价比不高", "混合", "价格争议", 1, "质好价贵"),
        ("鞋子好看但磨脚穿着不太舒服", "混合", "产品质量", 2, "好看但磨脚"),
        ("款式很好但是尺码严重偏小建议买大两码", "混合", "产品质量", 2, "款好码小"),
        ("颜色好看质量可以就是发货实在太慢了", "混合", "物流配送", 2, "产品好物流慢"),
        ("整体还行物流快但客服态度需要改善", "混合", "服务态度", 2, "物流好客服差"),
        ("鞋子本身质量没毛病但是刚买就参加活动降了80", "混合", "价格争议", 2, "产品好降价快"),
        ("做工精细穿着舒服就是款式选择太少", "混合", "产品质量", 1, "做工好款式少"),
        ("发货很快物流很棒但鞋子质量真的很一般穿几次就变形了", "混合", "产品质量", 2, "物流好质量差"),

        # ---- 中性 ----
        ("还行吧一般般没什么特别的", "中性", "产品质量", 1, "一般评价"),
        ("刚收到还没穿过看起来还行希望耐穿吧", "中性", "产品质量", 1, "未使用"),
        ("帮同事买的他说还行我也不清楚", "中性", "产品质量", 1, "代买不知情"),
        ("还没穿先评价一下过几天追评", "中性", "产品质量", 1, "待追评"),
        ("凑合穿吧没有太好也没有太差", "中性", "产品质量", 1, "凑合"),

        # ---- 反讽 ----
        ("真是买了个活爹回来供着吧不能穿", "负面", "产品质量", 2, "反讽-活爹"),
        ("五星好评穿了三天鞋底掉了客服已读不回太棒了", "负面", "产品质量", 3, "反讽-五星差评"),
        ("太浮夸了不过本仙女就是喜欢这种全场焦点的感觉", "正面", "产品质量", 1, "明贬暗褒"),
        ("谢谢商家让我体验了一次什么叫花钱买教训", "负面", "产品质量", 2, "反讽-感谢体"),
        ("呵呵就当买个教训吧", "负面", "产品质量", 2, "反讽-呵呵体"),
        ("这质量绝了穿三天比我穿三年还旧", "负面", "产品质量", 2, "反讽-绝了"),

        # ---- 无意义 ----
        ("好", "中性", "无效评论", 1, "单字评价"),
        ("不错", "中性", "无效评论", 1, "模糊好评"),
        ("111111", "中性", "无效评论", 1, "连击数字"),
        ("😂😂😂👍👍👍", "中性", "无效评论", 1, "纯表情"),
        ("默认好评", "中性", "无效评论", 1, "系统默认"),
        ("好評好評好評", "中性", "无效评论", 1, "繁体重复"),
        ("。。。。。。", "中性", "无效评论", 1, "纯符号"),

        # ---- 安全红线追加 ----
        ("穿了这个鞋子跑步扭伤了脚踝设计有安全隐患", "负面", "产品质量", 3, "安全伤害-高优"),
        ("鞋底防滑太差了雨天摔了一跤", "负面", "产品质量", 3, "防滑安全-高优"),
        ("孩子穿了脚上起了红疹怀疑材料过敏", "负面", "产品质量", 3, "材质过敏-高优"),

        # ---- 边缘场景 ----
        ("物流很快鞋子也很好客服也很耐心完美的一次购物", "正面", "产品质量", 1, "多维度全正面"),
        ("物流慢客服差鞋子还有质量问题三重打击", "负面", "产品质量", 2, "多维度全负面"),
        ("穿了一个月了来追评质量确实不错很耐穿", "正面", "产品质量", 1, "追评正面"),
        ("活动价买的很划算但发货等太久了", "混合", "物流配送", 2, "价格满意物流不满"),
        ("给爸爸买的他说很舒服走路不累了", "正面", "产品质量", 1, "送礼满意"),
    ]

    for content, sentiment, category, urgency, note in test_cases:
        golden.append({
            "review_id": f"G{gid:04d}",
            "review_content": content,
            "expected_sentiment": sentiment,
            "expected_category": category,
            "expected_urgency": urgency,
            "note": note,
        })
        gid += 1

    # 补充变体以凑满 200
    base_templates = list(test_cases)
    while len(golden) < n:
        base = random.choice(base_templates)
        content, sentiment, category, urgency, note = base
        # 微调
        variants = [
            content + "。",
            content + "！",
            "说一下，" + content,
            content + "，就这样",
        ]
        variant = random.choice(variants)
        golden.append({
            "review_id": f"G{gid:04d}",
            "review_content": variant,
            "expected_sentiment": sentiment,
            "expected_category": category,
            "expected_urgency": urgency,
            "note": f"变体: {note}",
        })
        gid += 1

    return golden[:n]


def save_golden(golden, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(golden, f, ensure_ascii=False, indent=2)
    # Also save as CSV for tool compatibility
    csv_path = path.replace(".json", ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["review_id", "review_content", "expected_sentiment", "expected_category", "expected_urgency", "note"])
        w.writeheader()
        w.writerows(golden)
    print(f"Golden dataset saved: {path} ({len(golden)} entries)")
    print(f"Golden CSV saved: {csv_path}")

    # 统计分布
    s_dist = {}
    c_dist = {}
    u_dist = {}
    for g in golden:
        s_dist[g["expected_sentiment"]] = s_dist.get(g["expected_sentiment"], 0) + 1
        c_dist[g["expected_category"]] = c_dist.get(g["expected_category"], 0) + 1
        u_dist[g["expected_urgency"]] = u_dist.get(g["expected_urgency"], 0) + 1
    print(f"  情感分布: {s_dist}")
    print(f"  分类分布: {c_dist}")
    print(f"  紧急度分布: {u_dist}")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=== 生成 820 条测试评论 CSV ===")
    reviews = generate_reviews(820)
    save_csv(reviews, "test_reviews_820.csv")

    print("\n=== 生成 Few-shot 样本库 ===")
    save_fewshot("fewshot_library.json")

    print("\n=== 生成 Golden 数据集 (200条) ===")
    golden = generate_golden(200)
    save_golden(golden, "golden_dataset.json")

    print("\n✅ 所有数据文件生成完毕！")
