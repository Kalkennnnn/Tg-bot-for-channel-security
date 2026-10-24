import asyncio
import contextlib
import logging
import aiomysql
import datetime
from aiogram.types import ChatJoinRequest, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, F

BOT_TOKEN = "" # Ваш токен
CHANNEL_ID = # Айди канала

dp = Dispatcher()
bot: Bot = Bot(token=BOT_TOKEN)

DB_CONFIG = {
    'host': '',
    'user': '',
    'password': '',
    'db': '',
    'autocommit': True,
}


async def approve_request(chat_join: ChatJoinRequest, bot: Bot):
    msg = "Ваша заявка была одобрена."
    await bot.send_message(chat_id=chat_join.from_user.id, text=msg)
    await store_user_id(chat_join.from_user.id, chat_join.from_user.full_name)
    await chat_join.approve()


async def store_user_id(user_id, user_name):
    formatted_time = current_time()
    async with aiomysql.create_pool(**DB_CONFIG) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT INTO user_data (tg_id, tg_name) VALUES (%s, %s)", (user_id, user_name))
                await cur.execute(f'''CREATE TABLE IF NOT EXISTS d_{formatted_time} (
                                       row_id INT AUTO_INCREMENT PRIMARY KEY,
                                       User_id VARCHAR(255) NOT NULL,
                                       tg_name VARCHAR(255) NOT NULL)''')
                await cur.execute(f"INSERT INTO d_{formatted_time} (User_id, tg_name) VALUES (%s, %s)",
                                  (user_id, user_name))
                users_count = await cur.execute('''SELECT * FROM d_%s''' % formatted_time)
                print(users_count)
                if users_count >= 2:
                    await request_kick(bot)

    print("Данные успешно занесены")


async def request_kick(bot: Bot):
    aboba = current_time()
    msg_text = f'Фиксирована подозрительная активность. Хотите ли вы выгнать за {aboba} период времени?'
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data='kick_yes')],
        [InlineKeyboardButton(text="Нет", callback_data='kick_no')],
        [InlineKeyboardButton(text="Вывести пользователей за последний час", callback_data='users_list')]
    ])
    await bot.send_message(chat_id=908613106, text=msg_text, reply_markup=keyboard)



async def callback_kick(query):
    user_response = query.data
    user_id = query.from_user.id
    chat_id = CHANNEL_ID

    if user_response == 'users_list':
        users = await get_recently_joined_users()
        response_text = "Пользователи, которые присоединились за последний час:\n" + "\n".join(users)
        await bot.send_message(chat_id=user_id, text=response_text)

    elif user_response == 'kick_no':
        await bot.send_message(chat_id=user_id, text="Вы отменили действие.")

    elif user_response == 'kick_yes':
        users = await get_recently_joined_users()
        for user in users:
            user_id_to_kick = user.split(",")[0].split(":")[1].strip()
            try:
                admins = await bot.get_chat_administrators(chat_id)
                bot_admin = next((admin.user.id for admin in admins if admin.user.id == bot.id), None)
                if bot_admin:
                    await bot.ban_chat_member(chat_id, user_id_to_kick)
                    await bot.unban_chat_member(chat_id, user_id_to_kick)
                    await bot.send_message(chat_id=user_id, text=f"Пользователь {user} был кикнут.")
                else:
                    await bot.send_message(chat_id=user_id, text="Бот не является администратором чата.")
            except Exception as e:
                await bot.send_message(chat_id=user_id,
                                       text=f"Ошибка: {e}. Проверьте, что бот имеет необходимые права.")



async def get_recently_joined_users():
    formatted_time = current_time()
    async with aiomysql.create_pool(**DB_CONFIG) as pool:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT User_id, tg_name FROM d_{formatted_time} WHERE DATE_SUB(NOW(), INTERVAL 1 HOUR) <= NOW()")
                users = await cur.fetchall()
                return [f"Id: {user[0]}, Name: {user[1]}" for user in users]



def current_time():
    thishour = datetime.datetime.today()
    formatted_time = thishour.strftime("%H_%d_%m_%Y")
    return formatted_time


async def start():
    logging.basicConfig(level=logging.DEBUG)
    bot: Bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.chat_join_request.register(approve_request, F.chat.id == CHANNEL_ID)
    dp.callback_query.register(callback_kick)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as ex:
        logging.error(f'Ошибка {ex}', exc_info=True)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(start())