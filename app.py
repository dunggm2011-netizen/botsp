import os
import json
import time
import threading
from flask import Flask
import telebot
from telebot import types

# ==========================================
# 1. CẤU HÌNH THÔNG SỐ
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8077955829:AAHHkj9UfheUOx19dfQU-KCaXvSkJz7m92A")
SUPPORT_GROUP_ID = int(os.environ.get("SUPPORT_GROUP_ID", "-1004383006384"))

ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "8183105705")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

COMMUNITY_GROUP_URL = os.environ.get("COMMUNITY_GROUP_URL", "https://t.me/danhsachdenxamat1")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Lưu trạng thái Admin đang chọn trả lời User nào: {admin_id: target_user_id}
admin_reply_state = {}

# Lưu trạng thái Admin đang chờ gửi nội dung Broadcast: set(admin_id)
admin_broadcast_state = set()

# ==========================================
# 2. QUẢN LÝ DANH SÁCH USER ĐÃ /START
# ==========================================
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(users), f)
        except Exception as e:
            print(f"Lỗi lưu file users: {e}")

# ==========================================
# 3. MINI WEB SERVER CHO RENDER
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot CSKH is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# 4. XỬ LÝ LỆNH /START TỪ USER
# ==========================================
@bot.message_handler(commands=['start'], chat_types=['private'])
def handle_start(message):
    user = message.from_user
    save_user(user.id)  # Lưu ID user vào danh sách broadcast

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else "Không có"

    markup = types.InlineKeyboardMarkup()
    btn_community = types.InlineKeyboardButton("👥 Tham gia Nhóm Cộng Đồng", url=COMMUNITY_GROUP_URL)
    markup.add(btn_community)

    welcome_text = (
        f"Xin chào <b>{full_name}</b>! 👋\n\n"
        "Chào mừng bạn đến với kênh Hỗ trợ Khách hàng.\n"
        "Bạn cần hỗ trợ vấn đề gì hãy nhắn trực tiếp tại đây, đội ngũ Admin sẽ phản hồi sớm nhất!\n\n"
        "👉 Đừng quên tham gia nhóm cộng đồng bên dưới để cập nhật tin tức mới nhất nhé:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

    notify_admin_text = (
        "🆕 <b>CÓ NGƯỜI DÙNG MỚI KHỞI ĐỘNG BOT</b>\n"
        f"• <b>Tên:</b> {full_name}\n"
        f"• <b>Username:</b> {username}\n"
        f"• <b>ID:</b> <code>{user.id}</code>\n"
        f"• <b>Tổng user hiện tại:</b> {len(load_users())}"
    )
    try:
        bot.send_message(SUPPORT_GROUP_ID, notify_admin_text)
    except Exception as e:
        print(f"Lỗi gửi thông báo vào nhóm: {e}")

# ==========================================
# 5. LỆNH /BROADCAST TRONG NHÓM RIÊNG CỦA ADMIN
# ==========================================
@bot.message_handler(commands=['broadcast'], func=lambda m: m.chat.id == SUPPORT_GROUP_ID)
def handle_broadcast_command(message):
    admin_id = message.from_user.id

    # Kiểm tra quyền Admin
    if admin_id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Bạn không có quyền Admin để sử dụng lệnh này!")
        return

    # Hủy trạng thái reply cá nhân nếu đang bật
    admin_reply_state.pop(admin_id, None)
    admin_broadcast_state.add(admin_id)

    total_users = len(load_users())
    force_reply = types.ForceReply(selective=True)
    bot.reply_to(
        message,
        f"📢 <b>CHẾ ĐỘ GỬI THÔNG BÁO HÀNG LOẠT (BROADCAST)</b>\n"
        f"• Số lượng khách hàng sẽ nhận tin: <b>{total_users}</b> người.\n\n"
        "👉 Hãy gửi <b>tin nhắn, ảnh, video hoặc file</b> ngay dưới đây để bot chuyển nguyên vẹn tới tất cả mọi người.\n"
        "<i>(Gửi /cancel để hủy)</i>",
        reply_markup=force_reply
    )

# ==========================================
# 6. XỬ LÝ KHI ADMIN BẤM NÚT "TRẢ LỜI" TỪNG USER
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_"))
def handle_reply_button(call):
    admin_id = call.from_user.id

    if admin_id not in ADMIN_IDS:
        bot.answer_callback_query(
            call.id,
            "⛔ Bạn không có quyền Admin để thực hiện thao tác này!",
            show_alert=True
        )
        return

    # Hủy trạng thái broadcast nếu đang bật
    admin_broadcast_state.discard(admin_id)

    target_user_id = int(call.data.split("_")[1])
    admin_reply_state[admin_id] = target_user_id

    bot.answer_callback_query(call.id, "✅ Đã chọn khách hàng. Hãy nhập nội dung phản hồi!")
    
    force_reply = types.ForceReply(selective=True)
    bot.send_message(
        call.message.chat.id,
        f"✍️ <b>{call.from_user.first_name}</b>, vui lòng nhập nội dung phản hồi cho khách hàng (ID: <code>{target_user_id}</code>):\n"
        "<i>(Gửi /cancel để hủy)</i>",
        reply_to_message_id=call.message.message_id,
        reply_markup=force_reply
    )

# ==========================================
# 7. XỬ LÝ TIN NHẮN TRONG NHÓM HỖ TRỢ (BROADCAST HOẶC REPLY USER)
# ==========================================
@bot.message_handler(
    func=lambda m: m.chat.id == SUPPORT_GROUP_ID and (
        m.from_user.id in admin_broadcast_state or m.from_user.id in admin_reply_state
    ),
    content_types=['text', 'photo', 'video', 'document', 'voice', 'sticker', 'audio']
)
def handle_admin_group_actions(message):
    admin_id = message.from_user.id

    # Lệnh hủy chung cho cả 2 chế độ
    if message.text and message.text.strip().lower() == "/cancel":
        admin_broadcast_state.discard(admin_id)
        admin_reply_state.pop(admin_id, None)
        bot.reply_to(message, "❌ Đã hủy thao tác hiện tại.")
        return

    # --- TRƯỜNG HỢP A: ADMIN ĐANG GỬI BROADCAST ---
    if admin_id in admin_broadcast_state:
        admin_broadcast_state.discard(admin_id)
        users = load_users()

        if not users:
            bot.reply_to(message, "⚠️ Chưa có người dùng nào trong danh sách để gửi thông báo.")
            return

        status_msg = bot.reply_to(message, f"⏳ Đang tiến hành gửi thông báo cho <b>{len(users)}</b> người dùng...")

        success_count = 0
        fail_count = 0

        for uid in users:
            try:
                # copy_message giữ nguyên văn bản, ảnh, caption, video, file... mà không dính tag "Forwarded from"
                bot.copy_message(
                    chat_id=uid,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                success_count += 1
                time.sleep(0.05)  # Nghỉ 50ms giữa mỗi tin để tránh bị Telegram giới hạn tốc độ (Rate Limit)
            except Exception as e:
                fail_count += 1
                print(f"Không thể gửi broadcast cho {uid}: {e}")

        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text=(
                "✅ <b>HOÀN TẤT GỬI THÔNG BÁO HÀNG LOẠT!</b>\n"
                f"• Thành công: <b>{success_count}</b> người\n"
                f"• Thất bại (đã chặn bot): <b>{fail_count}</b> người"
            )
        )
        return

    # --- TRƯỜNG HỢP B: ADMIN ĐANG TRẢ LỜI RIÊNG 1 USER ---
    if admin_id in admin_reply_state:
        target_user_id = admin_reply_state.get(admin_id)
        try:
            if message.content_type == 'text':
                bot.send_message(
                    target_user_id,
                    f"👨‍💻 <b>Phản hồi từ đội ngũ hỗ trợ:</b>\n\n{message.text}"
                )
            else:
                bot.send_message(target_user_id, "👨‍💻 <b>Phản hồi từ đội ngũ hỗ trợ:</b>")
                bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )

            bot.reply_to(message, f"✅ Đã gửi phản hồi thành công tới khách hàng (ID: <code>{target_user_id}</code>)!")
            del admin_reply_state[admin_id]

        except Exception as e:
            bot.reply_to(message, f"⚠️ Không thể gửi tin cho khách hàng này (có thể họ đã chặn bot).\nLỗi: <code>{e}</code>")
            del admin_reply_state[admin_id]

# ==========================================
# 8. XỬ LÝ TIN NHẮN TỪ USER GỬI ĐẾN BOT (FORWARD VÀO NHÓM)
# ==========================================
@bot.message_handler(
    chat_types=['private'],
    content_types=['text', 'photo', 'video', 'document', 'voice', 'sticker', 'audio']
)
def handle_user_message(message):
    user = message.from_user
    save_user(user.id)  # Tự động cập nhật lại ID user nếu file bị reset sau khi restart

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else "Không có"

    markup = types.InlineKeyboardMarkup()
    btn_reply = types.InlineKeyboardButton(
        text=f"💬 Trả lời {user.first_name}",
        callback_data=f"reply_{user.id}"
    )
    markup.add(btn_reply)

    try:
        forwarded_msg = bot.forward_message(
            chat_id=SUPPORT_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

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

        bot.reply_to(
            message,
            "✅ <b>Tin nhắn của bạn đã được gửi đến đội ngũ hỗ trợ.</b>\n"
            "Vui lòng chờ trong giây lát, Admin sẽ phản hồi lại bạn ngay!"
        )

    except Exception as e:
        print(f"Lỗi khi forward tin nhắn: {e}")
        bot.reply_to(message, "⚠️ Hệ thống đang bận, vui lòng thử lại sau ít phút.")

# ==========================================
# 9. CHẠY SONG SONG WEB SERVER VÀ BOT POLLING
# ==========================================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Không thể xóa webhook: {e}")

    print("Bot đang chạy...")
    bot.infinity_polling(skip_pending=True)
