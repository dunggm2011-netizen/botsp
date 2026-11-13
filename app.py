import os
import threading
from flask import Flask
import telebot
from telebot import types

# ==========================================
# 1. CẤU HÌNH THÔNG SỐ (Lấy từ biến môi trường trên Render hoặc điền trực tiếp)
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8077955829:AAHHkj9UfheUOx19dfQU-KCaXvSkJz7m92A")

# ID nhóm riêng nhận tin nhắn CSKH (Lưu ý: ID nhóm thường bắt đầu bằng -100...)
SUPPORT_GROUP_ID = int(os.environ.get("SUPPORT_GROUP_ID", "-1004383006384"))

# Danh sách ID của các Admin được phép bấm nút trả lời (cách nhau bởi dấu phẩy)
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "8183105705")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

# Link nhóm cộng đồng hiển thị ở nút bấm khi /start
COMMUNITY_GROUP_URL = os.environ.get("COMMUNITY_GROUP_URL", "https://t.me/danhsachdenxamat1")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Lưu trạng thái Admin đang chọn trả lời User nào: {admin_id: target_user_id}
admin_reply_state = {}

# ==========================================
# 2. MINI WEB SERVER CHO RENDER (Giữ cổng Port luôn mở)
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot CSKH is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# 3. XỬ LÝ LỆNH /START TỪ USER
# ==========================================
@bot.message_handler(commands=['start'], chat_types=['private'])
def handle_start(message):
    user = message.from_user
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else "Không có"

    # Tạo nút bấm dẫn tới nhóm cộng đồng
    markup = types.InlineKeyboardMarkup()
    btn_community = types.InlineKeyboardButton("👥 Tham gia Nhóm Cộng Đồng", url=COMMUNITY_GROUP_URL)
    markup.add(btn_community)

    # Chào user
    welcome_text = (
        f"Xin chào <b>{full_name}</b>! 👋\n\n"
        "Chào mừng bạn đến với kênh Hỗ trợ Khách hàng.\n"
        "Bạn cần hỗ trợ vấn đề gì hãy nhắn trực tiếp tại đây, đội ngũ Admin sẽ phản hồi sớm nhất!\n\n"
        "👉 Đừng quên tham gia nhóm cộng đồng bên dưới để cập nhật tin tức mới nhất nhé:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

    # Báo lên nhóm riêng có người mới /start
    notify_admin_text = (
        "🆕 <b>CÓ NGƯỜI DÙNG MỚI KHỞI ĐỘNG BOT</b>\n"
        f"• <b>Tên:</b> {full_name}\n"
        f"• <b>Username:</b> {username}\n"
        f"• <b>ID:</b> <code>{user.id}</code>"
    )
    try:
        bot.send_message(SUPPORT_GROUP_ID, notify_admin_text)
    except Exception as e:
        print(f"Lỗi gửi thông báo vào nhóm: {e}")

# ==========================================
# 4. XỬ LÝ KHI ADMIN BẤM NÚT "TRẢ LỜI" TRONG NHÓM
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_"))
def handle_reply_button(call):
    admin_id = call.from_user.id

    # Kiểm tra phân quyền Admin
    if admin_id not in ADMIN_IDS:
        bot.answer_callback_query(
            call.id,
            "⛔ Bạn không có quyền Admin để thực hiện thao tác này!",
            show_alert=True
        )
        return

    # Lấy ID của User cần trả lời từ callback_data (ví dụ: reply_123456789)
    target_user_id = int(call.data.split("_")[1])
    admin_reply_state[admin_id] = target_user_id

    bot.answer_callback_query(call.id, "✅ Đã chọn khách hàng. Hãy nhập nội dung phản hồi!")
    
    # Nhắn thông báo trong nhóm để Admin nhập tin (dùng ForceReply cho tiện thao tác)
    force_reply = types.ForceReply(selective=True)
    bot.send_message(
        call.message.chat.id,
        f"✍️ <b>{call.from_user.first_name}</b>, vui lòng nhập nội dung phản hồi cho khách hàng (ID: <code>{target_user_id}</code>):\n"
        "<i>(Gửi /cancel để hủy)</i>",
        reply_to_message_id=call.message.message_id,
        reply_markup=force_reply
    )

# ==========================================
# 5. XỬ LÝ TIN NHẮN TRONG NHÓM HỖ TRỢ (ADMIN PHẢN HỒI USER)
# ==========================================
@bot.message_handler(
    func=lambda m: m.chat.id == SUPPORT_GROUP_ID and m.from_user.id in admin_reply_state,
    content_types=['text', 'photo', 'video', 'document', 'voice', 'sticker']
)
def handle_admin_reply_message(message):
    admin_id = message.from_user.id
    target_user_id = admin_reply_state.get(admin_id)

    # Hủy thao tác trả lời
    if message.text and message.text.strip().lower() == "/cancel":
        del admin_reply_state[admin_id]
        bot.reply_to(message, "❌ Đã hủy thao tác phản hồi.")
        return

    try:
        # Gửi tin nhắn phản hồi tới đúng User
        if message.content_type == 'text':
            bot.send_message(
                target_user_id,
                f"👨‍💻 <b>Phản hồi từ đội ngũ hỗ trợ:</b>\n\n{message.text}"
            )
        else:
            # Nếu Admin gửi ảnh, file, video... thì dùng copy_message để gửi nguyên vẹn
            bot.send_message(target_user_id, "👨‍💻 <b>Phản hồi từ đội ngũ hỗ trợ:</b>")
            bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

        # Báo lại trong nhóm là đã gửi thành công và xóa trạng thái chờ
        bot.reply_to(message, f"✅ Đã gửi phản hồi thành công tới khách hàng (ID: <code>{target_user_id}</code>)!")
        del admin_reply_state[admin_id]

    except Exception as e:
        bot.reply_to(message, f"⚠️ Không thể gửi tin cho khách hàng này (có thể họ đã chặn bot).\nLỗi: <code>{e}</code>")
        del admin_reply_state[admin_id]

# ==========================================
# 6. XỬ LÝ TIN NHẮN TỪ USER GỬI ĐẾN BOT (FORWARD VÀO NHÓM)
# ==========================================
@bot.message_handler(
    chat_types=['private'],
    content_types=['text', 'photo', 'video', 'document', 'voice', 'sticker', 'audio']
)
def handle_user_message(message):
    user = message.from_user
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else "Không có"

    # Tạo nút bấm "Trả lời" gắn kèm ID của user này
    markup = types.InlineKeyboardMarkup()
    btn_reply = types.InlineKeyboardButton(
        text=f"💬 Trả lời {user.first_name}",
        callback_data=f"reply_{user.id}"
    )
    markup.add(btn_reply)

    try:
        # 1. Forward tin nhắn gốc của user vào nhóm hỗ trợ (để giữ nguyên định dạng/media)
        forwarded_msg = bot.forward_message(
            chat_id=SUPPORT_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        # 2. Gửi kèm thẻ thông tin + nút bấm "Trả lời" reply vào tin nhắn vừa forward
        info_text = (
            f"📩 <b>Tin nhắn mới từ khách hàng</b>\n"
            f"• <b>Tên:</b> {full_name} ({username})\n"
            f"• <b>ID:</b> <code>{user.id}</code>"
        )
        bot.send_message(
            chat_id=SUPPORT_GROUP_ID,
            text=info_text,
            reply_to_message_id=forwarded_msg.message_id,
            reply_markup=markup
        )

        # 3. Xác nhận lại cho User biết tin nhắn đã được chuyển đi
        bot.reply_to(
            message,
            "✅ <b>Tin nhắn của bạn đã được gửi đến đội ngũ hỗ trợ.</b>\n"
            "Vui lòng chờ trong giây lát, Admin sẽ phản hồi lại bạn ngay!"
        )

    except Exception as e:
        print(f"Lỗi khi forward tin nhắn: {e}")
        bot.reply_to(message, "⚠️ Hệ thống đang bận, vui lòng thử lại sau ít phút.")

# ==========================================
# 7. CHẠY SONG SONG WEB SERVER VÀ BOT POLLING
# ==========================================
if __name__ == "__main__":
    # Chạy Flask trên một luồng riêng
    threading.Thread(target=run_web, daemon=True).start()
    
    print("Bot đang chạy...")
    bot.infinity_polling(skip_pending=True)
