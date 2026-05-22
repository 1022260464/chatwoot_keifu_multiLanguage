from __future__ import annotations


FAQ_MENU_TRIGGERS = {"帮助", "菜单", "help", "/help", "faq"}
FAQ_COMMAND_PREFIX = "CMD_"

FAQ_LOCALES = {
    "zh": {
        "intro": "您好！我是智能助手，请问有什么可以帮您？您可以直接点击下方问题快速获取答案：",
        "button_prompt": "请选择一个常见问题：",
        "items": [
            {
                "title": "公司介绍\n产品优势",
                "value": "CMD_COMPANY_PRODUCT_INTRO",
                "answer": "我们是本土化运营的正规服务团队，产品主要面向有真实资金需求、信用记录良好的用户。相比暴力催收的黑网贷，我们更重视长期信用关系：信用表现越好，后续可获得的额度会更高，利率也会更低。我们不会骚扰用户的家属和朋友，也不会采用不合规的催收方式。",
            },
            {
                "title": "额度问题\n为什么不高",
                "value": "CMD_LOW_CREDIT_LIMIT",
                "answer": "初始额度不高，主要是因为平台需要控制欺诈风险。当前市场中虚假资料、恶意借款等情况较多，所以系统会先根据用户资料、还款记录和风险策略给出较保守的额度。对于信用好的用户，只要保持按时还款，通常在第三次按时还款之后，额度会有明显提升。",
            },
            {
                "title": "复借问题\n再次被拒",
                "value": "CMD_REAPPLY_REJECTED",
                "answer": "还款后再次申请被拒，通常不是单一原因导致的。平台会根据实时风控策略、用户资料完整度、历史还款表现、当前授信政策等因素综合判断。由于欺诈风险较高，审核政策也会不定时调整。感谢您的理解和信任，建议后续保持良好信用记录，并在一段时间后再尝试申请。",
            },
            {
                "title": "利率问题\n如何降低",
                "value": "CMD_INTEREST_RATE",
                "answer": "目前产品仍处于测试和优化阶段，初期利率会根据用户风险等级、信用表现和平台策略综合确定。对于信用记录良好、能够按时还款的用户，系统会逐步提高信任等级。通常在第三次按时还款之后，平台会明显降低利率，并可能同步提升可用额度。",
            },
        ],
    },
    "en": {
        "intro": "Hi! I am the smart assistant. You can choose a common question below for a quick answer.",
        "button_prompt": "Please select a question:",
        "items": [
            {
                "title": "Company\nProduct",
                "value": "CMD_COMPANY_PRODUCT_INTRO",
                "answer": "We are a localized service team focused on users with real funding needs and good credit behavior. Compared with illegal loan platforms that use aggressive collection methods, we care more about long-term credit relationships. Users with better credit performance may receive higher limits and lower interest rates over time. We will not harass users' family members or friends, and we do not use non-compliant collection methods.",
            },
            {
                "title": "Credit Limit\nWhy Low?",
                "value": "CMD_LOW_CREDIT_LIMIT",
                "answer": "The initial credit limit may be conservative because the platform needs to control fraud risk. There are many cases of false information and malicious borrowing, so the system first evaluates user information, repayment behavior, and risk rules before setting the limit. For users with good credit and on-time repayments, the limit usually increases significantly after the third on-time repayment.",
            },
            {
                "title": "Reapply\nRejected",
                "value": "CMD_REAPPLY_REJECTED",
                "answer": "A reapplication may be rejected after repayment for several reasons. The platform reviews real-time risk policies, profile completeness, repayment history, and current credit rules together. Because fraud risk is high, approval policies may be adjusted from time to time. Thank you for your trust. We recommend maintaining a good credit record and trying again later.",
            },
            {
                "title": "Interest Rate\nHow Lower?",
                "value": "CMD_INTEREST_RATE",
                "answer": "The product is still in the testing and optimization stage. The initial interest rate is determined by the user's risk level, credit behavior, and platform policy. For users with good credit records and on-time repayments, the system will gradually increase the trust level. After the third on-time repayment, the interest rate is usually reduced significantly, and the available limit may also increase.",
            },
        ],
    },
    "vi": {
        "intro": "Xin chao! Toi la tro ly thong minh. Ban co the chon cau hoi thuong gap ben duoi de nhan cau tra loi nhanh.",
        "button_prompt": "Vui long chon mot cau hoi:",
        "items": [
            {
                "title": "Cong ty\nSan pham",
                "value": "CMD_COMPANY_PRODUCT_INTRO",
                "answer": "Chung toi la doi ngu dich vu dia phuong hoa, tap trung vao nguoi dung co nhu cau von thuc te va hanh vi tin dung tot. So voi cac nen tang cho vay den thu hoi no bang cach manh bao, chung toi coi trong moi quan he tin dung lau dai hon. Nguoi dung co lich su tin dung tot co the nhan han muc cao hon va lai suat thap hon theo thoi gian. Chung toi se khong lam phien gia dinh hay ban be cua nguoi dung.",
            },
            {
                "title": "Han muc\nVi sao thap?",
                "value": "CMD_LOW_CREDIT_LIMIT",
                "answer": "Han muc ban dau co the khong cao vi nen tang can kiem soat rui ro gian lan. Hien co nhieu truong hop dung thong tin gia hoac vay voi muc dich xau, nen he thong se danh gia thong tin nguoi dung, lich su tra no va quy tac rui ro truoc khi cap han muc. Voi nguoi dung co tin dung tot va tra dung han, han muc thuong se tang dang ke sau lan thu ba tra no dung han.",
            },
            {
                "title": "Dang ky lai\nBi tu choi",
                "value": "CMD_REAPPLY_REJECTED",
                "answer": "Viec bi tu choi khi dang ky lai sau khi tra no co the den tu nhieu ly do. Nen tang se danh gia chinh sach rui ro theo thoi gian thuc, do hoan chinh cua ho so, lich su tra no va quy tac cap tin dung hien tai. Vi rui ro gian lan cao, chinh sach phe duyet co the thay doi theo tung thoi diem. Cam on su tin tuong cua ban, ban co the duy tri lich su tin dung tot va thu lai sau.",
            },
            {
                "title": "Lai suat\nCach giam",
                "value": "CMD_INTEREST_RATE",
                "answer": "San pham hien van trong giai doan thu nghiem va toi uu. Lai suat ban dau duoc xac dinh dua tren muc do rui ro, hanh vi tin dung va chinh sach cua nen tang. Voi nguoi dung co lich su tin dung tot va tra no dung han, he thong se dan tang muc do tin cay. Sau lan thu ba tra no dung han, lai suat thuong se giam dang ke va han muc kha dung cung co the duoc tang.",
            },
        ],
    },
}

LOW_VALUE_MESSAGES = {
    "zh": {
        "你好",
        "您好",
        "在吗",
        "有人吗",
        "哈",
        "哈哈",
        "嗯",
        "哦",
        "？",
        "？？",
        "。",
    },
    "en": {
        "hi",
        "hello",
        "hey",
        "test",
        "ok",
        "okay",
        "?",
        "??",
        "yes",
        "no",
    },
    "vi": {
        "xin chao",
        "alo",
        "test",
        "ok",
        "?",
        "??",
    },
}

LOW_VALUE_REPLIES = {
    "zh": "您好，请问您想咨询公司产品、额度、复借还是利率问题？您也可以点击下方常见问题快速了解。",
    "en": "Hi, what would you like to know about: company/product, credit limit, reapplication, or interest rate?",
    "vi": "Xin chao, ban muon hoi ve cong ty/san pham, han muc, dang ky lai hay lai suat?",
}

SENSITIVE_KEYWORDS = {
    "zh": {
        "投诉",
        "报警",
        "起诉",
        "律师",
        "诈骗",
        "被骗",
        "高利贷",
        "黑网贷",
        "暴力催收",
        "威胁",
        "恐吓",
        "骚扰家人",
        "泄露隐私",
        "砍头息",
        "自杀",
        "轻生",
    },
    "en": {
        "complaint",
        "police",
        "lawsuit",
        "lawyer",
        "scam",
        "fraud",
        "threat",
        "harass",
        "privacy leak",
        "suicide",
    },
    "vi": {
        "khieu nai",
        "canh sat",
        "lua dao",
        "gian lan",
        "de doa",
        "quay roi",
        "tu tu",
    },
}

SENSITIVE_PUBLIC_REPLIES = {
    "zh": "这个问题需要人工客服进一步核实，我已经帮您转接人工处理，请稍等。",
    "en": "This issue needs to be reviewed by a human support agent. I have forwarded it to the team. Please wait a moment.",
    "vi": "Van de nay can nhan vien ho tro kiem tra them. Toi da chuyen cho nhan vien, vui long doi trong giay lat.",
}

PRIVACY_PATTERNS = [
    {"name": "phone", "pattern": r"(?<!\d)1[3-9]\d{9}(?!\d)", "mask": "[PHONE]"},
    {"name": "id_card", "pattern": r"(?<!\d)(\d{15}|\d{17}[\dXx])(?!\d)", "mask": "[ID_CARD]"},
    {"name": "bank_card", "pattern": r"(?<!\d)\d{12,19}(?!\d)", "mask": "[BANK_CARD]"},
    {
        "name": "verification_code",
        "pattern": r"(验证码|code|otp|ma|mã)\s*[:：]?\s*\d{4,6}",
        "mask": "[VERIFICATION_CODE]",
    },
    {"name": "email", "pattern": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "mask": "[EMAIL]"},
]

PRIVACY_PRIVATE_NOTE_PREFIX = "用户消息包含可能的隐私字段，传入 Agent 前已脱敏"
