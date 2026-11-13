import os
import telebot
from telebot import types
from flask import Flask, request

# ==================== CẤU HÌNH ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8077955829:AAHHkj9UfheUOx19dfQU-KCaXvSkJz7m92A')
SUPPORT_GROUP_ID = int(os.environ.get('SUPPORT_GROUP_ID', '-1004383006384'))
SUPPORT_LINK = os.environ.get('SUPPORT_LINK', 'https://t.me/danhsachdenxamat1')

# ==================== GẮN ID ADMIN ====================
ADMIN_IDS = {
    int(x) for x in os.environ.get('ADMIN_IDS', '8183105705').split(',') if x.strip()
}
# ===================================================

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)  # threaded=False cho Render Free
app = Flask(__name__)

reply_map = {}
pending_reply = {}


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ==================== /start ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 Nhóm hỗ trợ", url=SUPPORT_LINK))

    text = (
        f"Chào {user.first_name},\n"
        f"Bạn có thể nhắn tin tại khung chat này để liên hệ nhóm hỗ trợ.\n"
        f"bấm nút bên dưới để vào nhóm:"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

    admin_text = (
        f"🔔 **User cần hỗ trợ**\n"
        f"Tên: {user.first_name} {user.last_name or ''}\n"
        f"ID: `{user.id}`\n"
        f"Username: @{user.username if user.username else 'Không có'}"
    )
    bot.send_message(SUPPORT_GROUP_ID, admin_text, parse_mode='Markdown')


# ==================== USER NHẮN RIÊNG ====================
@bot.message_handler(
    content_types=['text', 'photo', 'document', 'video', 'voice', 'audio', 'sticker'],
    func=lambda msg: msg.chat.type == 'private' and not is_admin(msg.from_user.id)
)
def forward_to_support(message):
    user = message.from_user
    try:
        forwarded = bot.forward_message(SUPPORT_GROUP_ID, message.chat.id, message.message_id)
        reply_map[forwarded.message_id] = message.chat.id

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            f"💬 Trả lời {user.first_name}",
            callback_data=f"reply_{user.id}"
        ))

        info_text = (
            f"👤 User: {user.first_name} (ID: `{user.id}`)\n"
            f"👉 Bấm nút bên dưới để trả lời user này."
        )
        bot.send_message(
            SUPPORT_GROUP_ID, info_text,
            parse_mode='Markdown',
            reply_markup=markup,
            reply_to_message_id=forwarded.message_id
        )
    except Exception as e:
        bot.reply_to(message, "Có lỗi xảy ra khi gửi đến hỗ trợ.")
        print(f"Lỗi forward: {e}")


# ==================== ADMIN BẤM NÚT TRẢ LỜI ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def on_reply_button(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Bạn không có quyền.", show_alert=True)
        return

    target_user_id = int(call.data.split('_')[1])
    pending_reply[call.from_user.id] = target_user_id

    try:
        target = bot.get_chat(target_user_id)
        name = target.first_name or str(target_user_id)
    except:
        name = str(target_user_id)

    bot.answer_callback_query(call.id, "Đã chọn user. Giờ nhắn nội dung trả lời.")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Huỷ", callback_data="cancel_reply"))
    bot.send_message(
        call.from_user.id,
        f"✍️ Bạn đang trả lời **{name}** (ID: `{target_user_id}`).\n"
        f"Nhắn nội dung tiếp theo để gửi cho user này.",
        parse_mode='Markdown',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_reply')
def on_cancel_reply(call):
    pending_reply.pop(call.from_user.id, None)
    bot.answer_callback_query(call.id, "Đã huỷ.")
    bot.edit_message_text("❌ Đã huỷ trả lời.", call.message.chat.id, call.message.message_id)


# ==================== ADMIN NHẮN NỘI DUNG TRẢ LỜI ====================
@bot.message_handler(
    content_types=['text', 'photo', 'document', 'video', 'voice', 'audio', 'sticker'],
    func=lambda msg: msg.chat.type == 'private'
                     and is_admin(msg.from_user.id)
                     and msg.from_user.id in pending_reply
)
def send_reply_to_user(message):
    target_user_id = pending_reply.pop(message.from_user.id)
    try:
        if message.text:
            bot.send_message(target_user_id, f"📩 **Phản hồi từ hỗ trợ:**\n{message.text}", parse_mode='Markdown')
        elif message.photo:
            bot.send_photo(target_user_id, message.photo[-1].file_id, caption="📩 Phản hồi từ hỗ trợ")
        elif message.document:
            bot.send_document(target_user_id, message.document.file_id, caption="📩 Phản hồi từ hỗ trợ")
        elif message.video:
            bot.send_video(target_user_id, message.video.file_id, caption="📩 Phản hồi từ hỗ trợ")
        elif message.voice:
            bot.send_voice(target_user_id, message.voice.file_id, caption="📩 Phản hồi từ hỗ trợ")
        elif message.audio:
            bot.send_audio(target_user_id, message.audio.file_id, caption="📩 Phản hồi từ hỗ trợ")
        elif message.sticker:
            bot.send_sticker(target_user_id, message.sticker.file_id)

        bot.reply_to(message, "✅ Đã gửi phản hồi đến user.")
    except Exception as e:
        bot.reply_to(message, f"❌ Không thể gửi: {e}")


# ==================== REPLY VUỐT (DỰ PHÒNG) ====================
@bot.message_handler(
    content_types=['text', 'photo', 'document', 'video', 'voice', 'audio', 'sticker'],
    func=lambda msg: msg.chat.id == SUPPORT_GROUP_ID and msg.reply_to_message is not None
)
def handle_support_reply_swipe(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Bạn không có quyền trả lời user.")
        return

    replied_msg = message.reply_to_message
    if replied_msg.message_id not in reply_map:
        bot.reply_to(message, "⚠️ Không tìm thấy user tương ứng.")
        return

    target_user_id = reply_map[replied_msg.message_id]
    try:
        if message.text:
            bot.send_message(target_user_id, f"📩 **Phản hồi từ hỗ trợ:**\n{message.text}", parse_mode='Markdown')
        elif message.photo:
            bot.send_photo(target_user_id, message.photo[-1].file_id, caption="📩 Phản hồi từ hỗ trợ")
        bot.reply_to(message, "✅ Đã gửi phản hồi đến user.")
    except Exception as e:
        bot.reply_to(message, f"❌ Không thể gửi: {e}")


# ==================== FLASK: HEALTH CHECK + WEBHOOK ====================
@app.route('/')
def health():
    return "OK", 200


@app.route('/' + BOT_TOKEN, methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    return "Forbidden", 403


# ==================== KHỞI ĐỘNG ====================
if __name__ == '__main__':
    # Khi chạy local hoặc Render, set webhook nếu có URL công khai
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')
    if RENDER_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
        print(f"Webhook set: {RENDER_URL}/{BOT_TOKEN}")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
