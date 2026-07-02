from __future__ import annotations


FAQ_MENU_TRIGGERS = {
    "help",
    "/help",
    "faq",
    "menu",
    "tro giup",
    "trợ giúp",
    "\u5e2e\u52a9",
    "\u83dc\u5355",
}
FAQ_COMMAND_PREFIX = "CMD_"

PUBLIC_REPLY_FALLBACKS = {
    "en": "Sorry, we cannot answer automatically right now. A support agent will continue helping you.",
    "vi": "Xin lỗi, hiện tại chúng tôi chưa thể trả lời tự động. Nhân viên hỗ trợ sẽ tiếp tục xử lý cho bạn.",
}

FAQ_LOCALES = {
    "en": {
        "intro": "[Quick FAQ Menu] Select a question below to receive a preset answer. For other questions, type your question and the AI assistant will assist you.",
        "button_prompt": "Select a FAQ item (preset answer):",
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
        "intro": "[Menu câu hỏi thường gặp] Chọn câu hỏi bên dưới để nhận câu trả lời có sẵn. Nếu cần hỏi vấn đề khác, hãy nhập câu hỏi và trợ lý AI sẽ hỗ trợ bạn.",
        "button_prompt": "Chọn một câu hỏi thường gặp (câu trả lời có sẵn):",
        "items": [
            {
                "title": "Công ty\nSản phẩm",
                "value": "CMD_COMPANY_PRODUCT_INTRO",
                "answer": "Chúng tôi là đội ngũ dịch vụ địa phương hóa, tập trung vào người dùng có nhu cầu vốn thực tế và hành vi tín dụng tốt. So với các nền tảng cho vay đen thu hồi nợ bằng cách mạnh bạo, chúng tôi coi trọng mối quan hệ tín dụng lâu dài hơn. Người dùng có lịch sử tín dụng tốt có thể nhận hạn mức cao hơn và lãi suất thấp hơn theo thời gian. Chúng tôi sẽ không làm phiền gia đình hay bạn bè của người dùng.",
            },
            {
                "title": "Hạn mức\nVì sao thấp?",
                "value": "CMD_LOW_CREDIT_LIMIT",
                "answer": "Hạn mức ban đầu có thể chưa cao vì nền tảng cần kiểm soát rủi ro gian lận. Hiện có nhiều trường hợp dùng thông tin giả hoặc vay với mục đích xấu, nên hệ thống sẽ đánh giá thông tin người dùng, lịch sử trả nợ và quy tắc rủi ro trước khi cấp hạn mức. Với người dùng có tín dụng tốt và trả đúng hạn, hạn mức thường sẽ tăng đáng kể sau lần thứ ba trả nợ đúng hạn.",
            },
            {
                "title": "Đăng ký lại\nBị từ chối",
                "value": "CMD_REAPPLY_REJECTED",
                "answer": "Việc bị từ chối khi đăng ký lại sau khi trả nợ có thể đến từ nhiều lý do. Nền tảng sẽ đánh giá chính sách rủi ro theo thời gian thực, độ hoàn chỉnh của hồ sơ, lịch sử trả nợ và quy tắc cấp tín dụng hiện tại. Vì rủi ro gian lận cao, chính sách phê duyệt có thể thay đổi theo từng thời điểm. Cảm ơn sự tin tưởng của bạn, bạn có thể duy trì lịch sử tín dụng tốt và thử lại sau.",
            },
            {
                "title": "Lãi suất\nCách giảm",
                "value": "CMD_INTEREST_RATE",
                "answer": "Sản phẩm hiện vẫn trong giai đoạn thử nghiệm và tối ưu. Lãi suất ban đầu được xác định dựa trên mức độ rủi ro, hành vi tín dụng và chính sách của nền tảng. Với người dùng có lịch sử tín dụng tốt và trả nợ đúng hạn, hệ thống sẽ dần tăng mức độ tin cậy. Sau lần thứ ba trả nợ đúng hạn, lãi suất thường sẽ giảm đáng kể và hạn mức khả dụng cũng có thể tăng.",
            },
        ],
    },
}

LOW_VALUE_MESSAGES = {
    "zh": {
        "\u4f60\u597d",
        "\u60a8\u597d",
        "\u5728\u5417",
        "\u6709\u4eba\u5417",
        "\u55ef",
        "\u54e6",
        "\u54c8\u54c8",
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
        "xin chào",
        "alo",
        "test",
        "ok",
        "?",
        "??",
    },
}

LOW_VALUE_REPLIES = {
    "en": "Hi! The quick FAQ menu is shown below. Select a button for a preset answer, or type another question for AI assistance.",
    "vi": "Xin chào! Menu câu hỏi thường gặp ở bên dưới. Chọn nút để xem câu trả lời có sẵn, hoặc nhập câu hỏi khác để được trợ lý AI hỗ trợ.",
}

SENSITIVE_KEYWORDS = {
    "zh": {
        "\u6295\u8bc9",
        "\u62a5\u8b66",
        "\u8d77\u8bc9",
        "\u5f8b\u5e08",
        "\u8bc8\u9a97",
        "\u88ab\u9a97",
        "\u9ad8\u5229\u8d37",
        "\u9ed1\u7f51\u8d37",
        "\u66b4\u529b\u50ac\u6536",
        "\u5a01\u80c1",
        "\u6050\u5413",
        "\u9a9a\u6270\u5bb6\u4eba",
        "\u6cc4\u9732\u9690\u79c1",
        "\u780d\u5934\u606f",
        "\u81ea\u6740",
        "\u8f7b\u751f",
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
        "khiếu nại",
        "canh sat",
        "cảnh sát",
        "lua dao",
        "lừa đảo",
        "gian lan",
        "gian lận",
        "de doa",
        "đe dọa",
        "quay roi",
        "quấy rối",
        "tu tu",
        "tự tử",
    },
}

SENSITIVE_PUBLIC_REPLIES = {
    "en": "This issue needs to be reviewed by a human support agent. I have forwarded it to the team. Please wait a moment.",
    "vi": "Vấn đề này cần nhân viên hỗ trợ kiểm tra thêm. Tôi đã chuyển cho nhân viên, vui lòng đợi trong giây lát.",
}

PRIVACY_PATTERNS = [
    {"name": "phone", "pattern": r"(?<!\d)1[3-9]\d{9}(?!\d)", "mask": "[PHONE]"},
    {"name": "id_card", "pattern": r"(?<!\d)(\d{15}|\d{17}[\dXx])(?!\d)", "mask": "[ID_CARD]"},
    {"name": "bank_card", "pattern": r"(?<!\d)\d{12,19}(?!\d)", "mask": "[BANK_CARD]"},
    {
        "name": "verification_code",
        "pattern": r"(code|otp|ma|mã)\s*[:：]?\s*\d{4,6}",
        "mask": "[VERIFICATION_CODE]",
    },
    {"name": "email", "pattern": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "mask": "[EMAIL]"},
]

PRIVACY_PRIVATE_NOTE_PREFIX = "User message may contain private fields; masked before Agent processing"
