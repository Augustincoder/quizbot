"""
Telegram Quiz Bot - QuizBot-style exam preparation.
Uses native Telegram quiz polls for instant feedback.
"""
import asyncio
import time
from typing import Optional
from datetime import datetime
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, PollAnswer,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

from config import BOT_TOKEN
from storage import get_storage, initialize_storage

logger = logging.getLogger(__name__)

# Router for handling updates
router = Router()


class QuizState(StatesGroup):
    """FSM states for quiz flow."""
    selecting_test = State()
    in_quiz = State()


class UserSession:
    """Stores quiz session data for a user."""
    
    def __init__(self):
        self.current_test: Optional[int] = None
        self.current_question_index: int = 0
        self.correct_count: int = 0
        self.wrong_count: int = 0
        self.start_time: Optional[float] = None
        self.last_poll_message_id: Optional[int] = None
        self.last_poll_id: Optional[str] = None
    
    def reset(self, test_id: int):
        """Reset session for a new test."""
        self.current_test = test_id
        self.current_question_index = 0
        self.correct_count = 0
        self.wrong_count = 0
        self.start_time = time.time()
        self.last_poll_message_id = None
        self.last_poll_id = None
    
    def record_answer(self, is_correct: bool):
        """Record an answer result."""
        if is_correct:
            self.correct_count += 1
        else:
            self.wrong_count += 1
        self.current_question_index += 1
    
    def get_elapsed_time(self) -> str:
        """Get formatted elapsed time."""
        if self.start_time is None:
            return "00:00"
        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return f"{minutes:02d}:{seconds:02d}"


# In-memory user sessions
user_sessions: dict[int, UserSession] = {}


def get_user_session(user_id: int) -> UserSession:
    """Get or create user session."""
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession()
    return user_sessions[user_id]


def build_test_selection_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard with available tests."""
    storage = get_storage()
    test_ids = storage.get_test_ids()
    
    buttons = []
    row = []
    
    for test_id in test_ids:
        info = storage.get_test_info(test_id)
        if info:
            btn = InlineKeyboardButton(
                text=f"📝 Test {test_id} ({info['range']})",
                callback_data=f"start_test:{test_id}"
            )
            row.append(btn)
            
            # 2 buttons per row
            if len(row) == 2:
                buttons.append(row)
                row = []
    
    # Add remaining buttons
    if row:
        buttons.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_post_test_keyboard(current_test_id: int) -> InlineKeyboardMarkup:
    """Build keyboard for post-test options."""
    storage = get_storage()
    test_ids = storage.get_test_ids()
    
    buttons = [
        [InlineKeyboardButton(
            text="🔁 Repeat Test",
            callback_data=f"start_test:{current_test_id}"
        )]
    ]
    
    # Add next test button if available
    current_idx = test_ids.index(current_test_id) if current_test_id in test_ids else -1
    if current_idx >= 0 and current_idx < len(test_ids) - 1:
        next_test_id = test_ids[current_idx + 1]
        next_info = storage.get_test_info(next_test_id)
        if next_info:
            buttons.append([InlineKeyboardButton(
                text=f"➡️ Next Test ({next_info['range']})",
                callback_data=f"start_test:{next_test_id}"
            )])
    
    # Add back to menu button
    buttons.append([InlineKeyboardButton(
        text="📋 All Tests",
        callback_data="show_tests"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command - show available tests."""
    storage = get_storage()
    
    total_tests = storage.get_test_count()
    total_questions = storage.get_total_questions()
    
    welcome_text = (
        "🎓 <b>Exam Preparation Bot</b>\n\n"
        f"📚 Available: <b>{total_tests}</b> tests with <b>{total_questions}</b> questions\n"
        f"📝 Each test contains up to 25 questions\n\n"
        "Select a test to begin:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=build_test_selection_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(QuizState.selecting_test)


@router.message(Command("tests"))
async def cmd_tests(message: Message, state: FSMContext):
    """Show available tests."""
    await message.answer(
        "📋 <b>Available Tests</b>\n\nSelect a test:",
        reply_markup=build_test_selection_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(QuizState.selecting_test)


@router.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext):
    """Stop current quiz and return to test selection."""
    user_id = message.from_user.id
    session = get_user_session(user_id)
    
    if session.current_test:
        # Try to stop the last poll
        if session.last_poll_message_id:
            try:
                await message.bot.stop_poll(
                    chat_id=message.chat.id,
                    message_id=session.last_poll_message_id
                )
            except TelegramBadRequest:
                pass
        
        await message.answer(
            "⏹ Quiz stopped.\n\n"
            f"Progress: {session.correct_count}✅ {session.wrong_count}❌\n"
            f"Time: {session.get_elapsed_time()}",
            reply_markup=build_post_test_keyboard(session.current_test),
            parse_mode="HTML"
        )
        session.current_test = None
    else:
        await message.answer(
            "No active quiz. Select a test to begin:",
            reply_markup=build_test_selection_keyboard()
        )
    
    await state.set_state(QuizState.selecting_test)


@router.callback_query(F.data == "show_tests")
async def callback_show_tests(callback: CallbackQuery, state: FSMContext):
    """Show test selection menu."""
    await callback.message.edit_text(
        "📋 <b>Available Tests</b>\n\nSelect a test:",
        reply_markup=build_test_selection_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(QuizState.selecting_test)
    await callback.answer()


@router.callback_query(F.data.startswith("start_test:"))
async def callback_start_test(callback: CallbackQuery, state: FSMContext):
    """Start a specific test."""
    test_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    storage = get_storage()
    test_info = storage.get_test_info(test_id)
    
    if not test_info:
        await callback.answer("Test not found!", show_alert=True)
        return
    
    # Initialize user session
    session = get_user_session(user_id)
    session.reset(test_id)
    
    # Notify test start
    await callback.message.edit_text(
        f"📝 <b>Test {test_id}</b> ({test_info['range']})\n"
        f"Questions: {test_info['question_count']}\n\n"
        "Starting now...",
        parse_mode="HTML"
    )
    
    await state.set_state(QuizState.in_quiz)
    await callback.answer()
    
    # Send first question
    await send_question(callback.message.chat.id, callback.bot, user_id)


async def send_question(chat_id: int, bot: Bot, user_id: int):
    """Send the current question as a quiz poll."""
    session = get_user_session(user_id)
    storage = get_storage()
    
    if session.current_test is None:
        return
    
    test = storage.get_test(session.current_test)
    if test is None:
        return
    
    # Check if test is complete
    if session.current_question_index >= len(test):
        await show_results(chat_id, bot, user_id)
        return
    
    question_data = test[session.current_question_index]
    question_num = session.current_question_index + 1
    total_questions = len(test)
    
    # Stop previous poll if exists
    if session.last_poll_message_id:
        try:
            await bot.stop_poll(
                chat_id=chat_id,
                message_id=session.last_poll_message_id
            )
        except TelegramBadRequest:
            # Poll already closed or message deleted
            pass
    
    # Format question text with progress
    question_text = f"❓ {question_num}/{total_questions}\n\n{question_data['question']}"
    
    # Truncate if too long (Telegram limit is 300 chars for poll question)
    if len(question_text) > 295:
        question_text = question_text[:292] + "..."
    
    # Send quiz poll
    poll_message = await bot.send_poll(
        chat_id=chat_id,
        question=question_text,
        options=question_data["options"],
        type="quiz",
        correct_option_id=question_data["correct_index"],
        is_anonymous=False,
        open_period=None  # No time limit
    )
    
    # Store poll info for tracking
    session.last_poll_message_id = poll_message.message_id
    session.last_poll_id = poll_message.poll.id


async def show_results(chat_id: int, bot: Bot, user_id: int):
    """Display final quiz results."""
    session = get_user_session(user_id)
    
    if session.current_test is None:
        return
    
    storage = get_storage()
    test_info = storage.get_test_info(session.current_test)
    total = session.correct_count + session.wrong_count
    
    # Calculate percentage
    percentage = (session.correct_count / total * 100) if total > 0 else 0
    
    # Choose emoji based on score
    if percentage >= 90:
        grade_emoji = "🏆"
        grade_text = "Excellent!"
    elif percentage >= 70:
        grade_emoji = "👍"
        grade_text = "Good job!"
    elif percentage >= 50:
        grade_emoji = "📚"
        grade_text = "Keep practicing!"
    else:
        grade_emoji = "💪"
        grade_text = "Don't give up!"
    
    result_text = (
        f"{grade_emoji} <b>Test {session.current_test} Complete!</b>\n\n"
        f"✅ Correct: <b>{session.correct_count}</b>\n"
        f"❌ Wrong: <b>{session.wrong_count}</b>\n"
        f"📊 Score: <b>{percentage:.1f}%</b>\n"
        f"⏱ Time: <b>{session.get_elapsed_time()}</b>\n\n"
        f"{grade_text}"
    )
    
    current_test = session.current_test
    session.current_test = None  # Mark quiz as complete
    
    await bot.send_message(
        chat_id=chat_id,
        text=result_text,
        reply_markup=build_post_test_keyboard(current_test),
        parse_mode="HTML"
    )


@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, state: FSMContext, bot: Bot):
    """
    Handle user's poll answer.
    Automatically sends the next question.
    """
    user_id = poll_answer.user.id
    session = get_user_session(user_id)
    
    # Verify this is for the current quiz
    if session.current_test is None:
        return
    
    if session.last_poll_id != poll_answer.poll_id:
        # Answer to an old poll, ignore
        return
    
    storage = get_storage()
    test = storage.get_test(session.current_test)
    
    if test is None or session.current_question_index >= len(test):
        return
    
    question_data = test[session.current_question_index]
    correct_index = question_data["correct_index"]
    
    # Check if answer is correct
    user_answer = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    is_correct = user_answer == correct_index
    
    # Record the answer
    session.record_answer(is_correct)
    
    # Small delay before next question (for better UX)
    await asyncio.sleep(0.5)
    
    # Get chat_id - we need to find it from stored context
    # For private chats, chat_id equals user_id
    chat_id = user_id
    
    # Send next question or results
    await send_question(chat_id, bot, user_id)


@router.message(QuizState.in_quiz)
async def handle_message_during_quiz(message: Message):
    """Handle messages during active quiz."""
    await message.answer(
        "⚠️ Quiz in progress!\n\n"
        "Answer the poll above or use /stop to end the quiz."
    )


async def create_bot() -> tuple[Bot, Dispatcher]:
    """Create and configure bot and dispatcher."""
    bot = Bot(token=BOT_TOKEN)
    
    # Use memory storage for FSM
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register router
    dp.include_router(router)
    
    return bot, dp


async def run_bot():
    """Initialize storage and run the bot."""
    logger.info("Initializing storage...")
    
    # Initialize storage (will scrape if needed)
    await initialize_storage()
    
    storage = get_storage()
    logger.info(f"Loaded {storage.get_test_count()} tests with {storage.get_total_questions()} questions")
    
    # Create and run bot
    bot, dp = await create_bot()
    
    logger.info("Starting bot...")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
