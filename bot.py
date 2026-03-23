import time
from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

router = Router()

# In-Memory State Management
# Format: { user_id: { "test_id": int, "q_idx": int, "correct": int, "wrong": int, "start_time": float, "poll_id": str, "msg_id": int, "chat_id": int } }
user_sessions = {}
# Reverse mapping to match incoming PollAnswers to users
poll_user_map = {} 

# Memory DB populated at startup
memory_db = {}

def truncate_text(text: str, limit: int) -> str:
    """Telegram restricts poll questions to 300 chars and options to 100 chars."""
    return text if len(text) <= limit else text[:limit-3] + "..."

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Shows available tests."""
    buttons = []
    for test_id, data in sorted(memory_db.items()):
        btn = InlineKeyboardButton(
            text=f"Test {test_id} (Q: {data['range']})", 
            callback_data=f"start_test_{test_id}"
        )
        buttons.append([btn])
        
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("📚 *Select an Exam Block to start:*", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("start_test_"))
async def start_test_handler(callback: CallbackQuery, bot: Bot):
    test_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    if test_id not in memory_db:
        await callback.answer("Test not found!", show_alert=True)
        return

    # Initialize Session
    user_sessions[user_id] = {
        "test_id": test_id,
        "q_idx": 0,
        "correct": 0,
        "wrong": 0,
        "start_time": time.time(),
        "poll_id": None,
        "msg_id": None,
        "chat_id": callback.message.chat.id
    }
    
    await callback.message.delete() # Clean up menu
    await send_next_question(user_id, bot)

async def send_next_question(user_id: int, bot: Bot):
    session = user_sessions.get(user_id)
    if not session: return

    test_data = memory_db[session["test_id"]]
    q_idx = session["q_idx"]

    # End Test Check
    if q_idx >= len(test_data["questions"]):
        await finish_test(user_id, bot)
        return

    q = test_data["questions"][q_idx]
    
    # Format according to Telegram limits
    question_text = truncate_text(f"[{q_idx + 1}/{len(test_data['questions'])}] {q['question']}", 300)
    options = [truncate_text(opt, 100) for opt in q["options"]]

    msg = await bot.send_poll(
        chat_id=session["chat_id"],
        question=question_text,
        options=options,
        type="quiz",
        correct_option_id=q["correct_index"],
        is_anonymous=False
    )

    # Save mapping and state
    session["poll_id"] = msg.poll.id
    session["msg_id"] = msg.message_id
    poll_user_map[msg.poll.id] = user_id

@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, bot: Bot):
    user_id = poll_user_map.get(poll_answer.poll_id)
    if not user_id or user_id not in user_sessions:
        return

    session = user_sessions[user_id]
    
    # Ensure this is the active poll
    if session["poll_id"] != poll_answer.poll_id:
        return

    # 1. Stop the previous poll visually to prevent scrolling back
    try:
        await bot.stop_poll(chat_id=session["chat_id"], message_id=session["msg_id"])
    except Exception:
        pass # Ignore if already closed

    # 2. Score the answer (option_ids[0] contains user selection in Quizzes)
    test_id = session["test_id"]
    q_idx = session["q_idx"]
    correct_idx = memory_db[test_id]["questions"][q_idx]["correct_index"]

    if poll_answer.option_ids[0] == correct_idx:
        session["correct"] += 1
    else:
        session["wrong"] += 1

    # 3. Advance to next question instantly
    session["q_idx"] += 1
    await send_next_question(user_id, bot)

async def finish_test(user_id: int, bot: Bot):
    session = user_sessions[user_id]
    
    # Calculate Time
    elapsed = int(time.time() - session["start_time"])
    mins, secs = divmod(elapsed, 60)
    
    text = (
        f"🏁 *Test {session['test_id']} Completed!*\n\n"
        f"✅ Correct: {session['correct']}\n"
        f"❌ Wrong: {session['wrong']}\n"
        f"⏱ Time: {mins:02d}:{secs:02d}"
    )

    # REPEAT SYSTEM buttons
    next_test_id = session['test_id'] + 1
    buttons = [
        [InlineKeyboardButton(text="🔁 Repeat Test", callback_data=f"start_test_{session['test_id']}")]
    ]
    if next_test_id in memory_db:
        buttons.append([InlineKeyboardButton(text="➡️ Next Test", callback_data=f"start_test_{next_test_id}")])
    buttons.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_to_main")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(session["chat_id"], text, reply_markup=kb, parse_mode="Markdown")
    
    # Clean up memory mapping to prevent bloat
    if session["poll_id"] in poll_user_map:
        del poll_user_map[session["poll_id"]]

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)
