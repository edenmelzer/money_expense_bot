import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import os


# ------------------ CONFIG ------------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ------------------ DATABASE ------------------
conn = sqlite3.connect("expenses.db", check_same_thread=False)
cursor = conn.cursor()

# יצירת טבלה חדשה עם עמודת type
cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    category TEXT,
    type TEXT NOT NULL,  -- "expense" או "income"
    date TEXT NOT NULL
)
""")
conn.commit()


# ------------------ HELPERS ------------------
def add_entry(amount: float, category: str, entry_type: str):
    cursor.execute(
        "INSERT INTO expenses (amount, category, type, date) VALUES (?, ?, ?, ?)",
        (amount, category, entry_type, datetime.now().isoformat())
    )
    conn.commit()


def get_week_total() -> (float, float):
    week_ago = datetime.now() - timedelta(days=7)
    cursor.execute(
        "SELECT type, SUM(amount) FROM expenses WHERE date >= ? GROUP BY type",
        (week_ago.isoformat(),)
    )
    results = cursor.fetchall()
    income = sum(total for t, total in results if t == "income")
    expense = sum(total for t, total in results if t == "expense")
    return income, expense


def get_month_total() -> (float, float):
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    cursor.execute(
        "SELECT type, SUM(amount) FROM expenses WHERE date >= ? GROUP BY type",
        (start_of_month.isoformat(),)
    )
    results = cursor.fetchall()
    income = sum(total for t, total in results if t == "income")
    expense = sum(total for t, total in results if t == "expense")
    return income, expense


def get_week_totals_by_category() -> dict:
    week_ago = datetime.now() - timedelta(days=7)
    cursor.execute(
        "SELECT category, type, SUM(amount) FROM expenses WHERE date >= ? GROUP BY category, type",
        (week_ago.isoformat(),)
    )
    results = cursor.fetchall()
    data = {"income": {}, "expense": {}}
    for cat, t, total in results:
        data[t][cat] = total
    return data


def get_month_totals_by_category() -> dict:
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    cursor.execute(
        "SELECT category, type, SUM(amount) FROM expenses WHERE date >= ? GROUP BY category, type",
        (start_of_month.isoformat(),)
    )
    results = cursor.fetchall()
    data = {"income": {}, "expense": {}}
    for cat, t, total in results:
        data[t][cat] = total
    return data


# ------------------ BOT LOGIC ------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        await update.message.reply_text(
            "❌ פורמט שגוי\nשלח: קטגוריה סכום (עם + בסוף אם זו הכנסה)\nלדוגמה: אוכל 50\nמשכורת 1500 +"
        )
        return

    # בדיקה אם זו הכנסה או הוצאה
    if parts[-1] == "+":
        entry_type = "income"
        try:
            amount = float(parts[-2])
        except ValueError:
            await update.message.reply_text("❌ הסכום חייב להיות מספר")
            return
        category = " ".join(parts[:-2])
    else:
        entry_type = "expense"
        try:
            amount = float(parts[-1])
        except ValueError:
            await update.message.reply_text("❌ הסכום חייב להיות מספר")
            return
        category = " ".join(parts[:-1])

    add_entry(amount, category, entry_type)

    # חיווי רגיל: סה"כ שבועי + חודשי ללא קטגוריות
    week_income, week_expense = get_week_total()
    month_income, month_expense = get_month_total()

    reply = (
        "✅ נרשם בהצלחה\n\n"
        f"📆 סה״כ השבוע:\nהכנסות: {week_income:.0f} ₪\nהוצאות: {week_expense:.0f} ₪\n\n"
        f"🗓️ סה״כ החודש:\nהכנסות: {month_income:.0f} ₪\nהוצאות: {month_expense:.0f} ₪"
    )
    await update.message.reply_text(reply)


# ------------------ COMMANDS ------------------
async def week_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_week_totals_by_category()
    if not data["income"] and not data["expense"]:
        await update.message.reply_text("📆 אין הוצאות או הכנסות השבוע")
        return

    income_text = "\n".join(f"{cat}: {total:.0f} ₪" for cat, total in data["income"].items()) or "אין הכנסות"
    expense_text = "\n".join(f"{cat}: {total:.0f} ₪" for cat, total in data["expense"].items()) or "אין הוצאות"

    total_income = sum(data["income"].values())
    total_expense = sum(data["expense"].values())

    await update.message.reply_text(
        f"📆 סה״כ השבוע לפי קטגוריות:\n"
        f"הכנסות:\n{income_text}\nסה״כ: {total_income:.0f} ₪\n\n"
        f"הוצאות:\n{expense_text}\nסה״כ: {total_expense:.0f} ₪"
    )


async def month_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_month_totals_by_category()
    if not data["income"] and not data["expense"]:
        await update.message.reply_text("🗓️ אין הוצאות או הכנסות החודש")
        return

    income_text = "\n".join(f"{cat}: {total:.0f} ₪" for cat, total in data["income"].items()) or "אין הכנסות"
    expense_text = "\n".join(f"{cat}: {total:.0f} ₪" for cat, total in data["expense"].items()) or "אין הוצאות"

    total_income = sum(data["income"].values())
    total_expense = sum(data["expense"].values())

    await update.message.reply_text(
        f"🗓️ סה״כ החודש לפי קטגוריות:\n"
        f"הכנסות:\n{income_text}\nסה״כ: {total_income:.0f} ₪\n\n"
        f"הוצאות:\n{expense_text}\nסה״כ: {total_expense:.0f} ₪"
    )


async def undo_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT id, category, amount, type FROM expenses ORDER BY id DESC LIMIT 1")
    last = cursor.fetchone()
    if not last:
        await update.message.reply_text("❌ אין רשומות למחוק")
        return
    last_id, last_category, last_amount, last_type = last
    cursor.execute("DELETE FROM expenses WHERE id = ?", (last_id,))
    conn.commit()
    await update.message.reply_text(f"✅ נמחקה הרשומה האחרונה: {last_category} {last_amount:.0f} ₪ ({last_type})")


async def delete_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ שלח את הפקודה כך: /delete dd/mm/yyyy")
        return

    date_str = context.args[0]
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        await update.message.reply_text("❌ תאריך לא תקין. השתמש בפורמט dd/mm/yyyy")
        return

    start = dt.replace(hour=0, minute=0, second=0)
    end = dt.replace(hour=23, minute=59, second=59)

    cursor.execute(
        "DELETE FROM expenses WHERE date BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat())
    )
    conn.commit()
    await update.message.reply_text(f"✅ נמחקו כל ההכנסות וההוצאות מתאריך {date_str}")


# ------------------ token ------------------
#if not TOKEN:
#      raise ValueError("TELEGRAM_BOT_TOKEN is not set")

# ------------------ MAIN ------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("week", week_summary))
    app.add_handler(CommandHandler("month", month_summary))
    app.add_handler(CommandHandler("undo", undo_last))
    app.add_handler(CommandHandler("delete", delete_by_date))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
