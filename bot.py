import telebot, os
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import csv
import datetime

load_dotenv()

def save_order_to_file(user_id, username, orders, status):
    filename = 'orders.csv'
    try:
        with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['user_id', 'username', 'product_name', 'quantity', 'status']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            for product_id, order in orders.items():
                if product_id == 'comment':  # Пропускаємо коментарі
                    continue
                product = order.get('product')
                if product:
                    writer.writerow({
                        'user_id': user_id,
                        'username': username,
                        'product_name': product['name'],
                        'quantity': order['quantity'],
                        'status': status
                    })
    except Exception as e:
        print(f"Помилка при збереженні замовлення у файл: {e}")

admins = os.getenv('admins').split(',')
API_KEY = os.getenv('API_KEY')
bot = telebot.TeleBot(API_KEY)

user_orders = {}
pending_orders = {}  # Для зберігання очікуваних замовлень

# Функція для зчитування продуктів з CSV
def get_products():
    products = []
    try:
        with open('products.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for idx, row in enumerate(reader, start=1):
                products.append({
                    'id': idx,
                    'name': row['name'].strip(),
                    'count': int(row['count'].strip()),
                    'price': float(row['price'].strip())
                })
    except Exception as e:
        print(f"Помилка зчитування продуктів: {e}")
    return products

# Функція для збереження продуктів у CSV
def save_products(products):
    try:
        with open('products.csv', 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['name', 'count', 'price']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for product in products:
                writer.writerow({
                    'name': product['name'],
                    'count': product['count'],
                    'price': product['price']
                })
    except Exception as e:
        print(f"Помилка збереження продуктів: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    btn_products = InlineKeyboardButton("Переглянути продукти", callback_data='view_products')
    markup.add(btn_products)
    bot.send_message(message.chat.id, 'Привіт! Оберіть одну з опцій:', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'view_products')
def handle_view_products_callback(call):
    products = get_products()
    if not products:
        bot.answer_callback_query(call.id, "Немає доступних продуктів.")
        return

    markup = InlineKeyboardMarkup()
    for product in products:
        button = InlineKeyboardButton(f"{product['name']}:  {product['price']} грн", callback_data=f"select_{product['id']}_1")
        markup.add(button)

    btn_cart = InlineKeyboardButton("Переглянути кошик", callback_data='view_cart')
    markup.add(btn_cart)

    bot.edit_message_text("Оберіть товар:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def handle_quantity_selection(call):
    try:
        _, product_id, quantity = call.data.split('_')
        product_id = int(product_id)
        quantity = int(quantity)

        products = get_products()
        product = next((p for p in products if p['id'] == product_id), None)
        if not product:
            bot.answer_callback_query(call.id, "Продукт не знайдено.")
            return

        if quantity > product['count']:
            bot.answer_callback_query(call.id, f"Доступно тільки {product['count']} шт.")
            return

        markup = InlineKeyboardMarkup()
        btn_increase = InlineKeyboardButton("+1", callback_data=f"select_{product_id}_{quantity + 1}")
        btn_decrease = InlineKeyboardButton("-1", callback_data=f"select_{product_id}_{max(0, quantity - 1)}")
        btn_addToCart = InlineKeyboardButton("Додати до кошику", callback_data=f"addToCart_{product_id}_{quantity}")
        btn_back = InlineKeyboardButton("Повернутися до продуктів", callback_data="view_products")
        markup.add(btn_increase, btn_decrease)
        markup.add(btn_addToCart)
        markup.add(btn_back)

        if quantity == 0:
            bot.answer_callback_query(call.id, "Ви не можете вибрати 0 товарів.")
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"Ви обрали {product['name']} у кількості: {quantity}",
                reply_markup=markup
            )
    except Exception as e:
        print(f"Помилка при виборі кількості: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка при виборі товару.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('addToCart'))
def handle_addToCart(call):
    try:
        data_parts = call.data.split('_')
        if len(data_parts) != 3:
            print(data_parts)
            bot.answer_callback_query(call.id, "Неправильний формат даних. Спробуйте ще раз.")
            return
        
        _, product_id, quantity = data_parts
        product_id = int(product_id)
        quantity = int(quantity)

        products = get_products()
        product = next((p for p in products if p['id'] == product_id), None)
        if not product:
            bot.answer_callback_query(call.id, "Продукт не знайдено.")
            return

        if quantity > product['count']:
            bot.answer_callback_query(call.id, f"Недостатньо товару на складі. Доступно {product['count']} шт.")
            return

        if call.from_user.id not in user_orders:
            user_orders[call.from_user.id] = {}

        if product_id in user_orders[call.from_user.id]:
            current_quantity = user_orders[call.from_user.id][product_id]['quantity']
            new_quantity = current_quantity + quantity

            if new_quantity > product['count']:
                bot.answer_callback_query(call.id, f"Загальна кількість товару не може перевищувати {product['count']} шт.")
                return

            user_orders[call.from_user.id][product_id]['quantity'] = new_quantity
        else:
            user_orders[call.from_user.id][product_id] = {'product': product, 'quantity': quantity}

        bot.answer_callback_query(call.id, f"{product['name']} додано до кошика в кількості {quantity} шт.")
    except Exception as e:
        print(f"Помилка при додаванні до кошика: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка. Спробуйте ще раз пізніше.")

@bot.callback_query_handler(func=lambda call: call.data == 'view_cart')
def view_cart(call):
    orders = user_orders.get(call.from_user.id, {})
    if orders:
        text = "Ваш кошик:\n"
        total_price = 0
        for product_id, order in orders.items():
            if product_id == 'comment':  # Пропускаємо коментарі при формуванні тексту
                continue
            product = order['product']
            quantity = order['quantity']
            price = product['price'] * quantity
            total_price += price
            text += f"{product['name']} - {quantity} шт. на {price} грн\n"

        text += f"\nЗагальна вартість: {total_price} грн"

        markup = InlineKeyboardMarkup()
        btn_confirm = InlineKeyboardButton("Зробити замовлення", callback_data="confirm_order")
        btn_back = InlineKeyboardButton("До продуктів", callback_data="view_products")
        btn_remove = InlineKeyboardButton("Видалити товар", callback_data="remove_product")
        btn_comment = InlineKeyboardButton("Введіть вашу кімнату і побажання в коментарі!", callback_data="add_comment")
        markup.add(btn_confirm, btn_back, btn_remove, btn_comment)

        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup)
    else:
        markup = InlineKeyboardMarkup()
        btn_back = InlineKeyboardButton("Повернутися до продуктів", callback_data="view_products")
        markup.add(btn_back)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Ваш кошик порожній.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'remove_product')
def remove_product(call):
    orders = user_orders.get(call.from_user.id, {})
    if orders:
        markup = InlineKeyboardMarkup()
        for product_id, order in orders.items():
            if isinstance(order, dict):  # Переконайтеся, що order є словником
                product = order.get('product')
                if product:
                    btn_remove = InlineKeyboardButton(f"Видалити {product['name']}", callback_data=f"remove_{product_id}")
                    markup.add(btn_remove)

        if markup.keyboard:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Оберіть товар для видалення:", reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "Ваш кошик порожній.")
    else:
        bot.answer_callback_query(call.id, "Ваш кошик порожній.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
def handle_remove_from_cart(call):
    try:
        product_id = int(call.data.split('_')[1])
        if call.from_user.id in user_orders and product_id in user_orders[call.from_user.id]:
            removed_product = user_orders[call.from_user.id].pop(product_id)
            # Повернення кількості продукту назад у CSV
            products = get_products()
            product = next((p for p in products if p['id'] == product_id), None)
            if product:
                product['count'] += removed_product['quantity']
                save_products(products)

            bot.answer_callback_query(call.id, f"{removed_product['product']['name']} видалено з кошика.")
            if not user_orders[call.from_user.id]:
                del user_orders[call.from_user.id]
            view_cart(call)
        else:
            bot.answer_callback_query(call.id, "Товар не знайдено в кошику.")
    except Exception as e:
        print(f"Помилка при видаленні товару: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка. Спробуйте ще раз.")

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_order')
def handle_confirm_order(call):
    try:
        orders = user_orders.get(call.from_user.id, {})
        if not orders or all(key == 'comment' for key in orders.keys()):
            bot.answer_callback_query(call.id, "Ваш кошик порожній або не містить товарів для замовлення.")
            return

        # Зберігаємо замовлення як очікуюче
        pending_orders[call.from_user.id] = orders

        text = f"Замовлення від {call.from_user.username if call.from_user.username else 'Без імені'}:\n\n"
        total_price = 0
        for product_id, order in orders.items():
            if product_id == 'comment':  # Пропускаємо коментарі при формуванні тексту
                continue
            product = order.get('product')
            if product:
                quantity = order.get('quantity', 0)
                price = product['price'] * quantity
                total_price += price
                text += f"{product['name']} - {quantity} шт. на {price} грн\n"

        text += f"\nЗагальна вартість: {total_price} грн\n\nКоментар: {orders.get('comment', 'Без коментарів')}"

        markup = InlineKeyboardMarkup()
        btn_confirm = InlineKeyboardButton("Підтвердити замовлення ✅", callback_data=f"approve_order_{call.from_user.id}")
        btn_reject = InlineKeyboardButton("Відхилити замовлення ❌", callback_data=f"reject_order_{call.from_user.id}")
        markup.add(btn_confirm, btn_reject)

        for admin in admins:
            bot.send_message(admin, text, reply_markup=markup)

        bot.answer_callback_query(call.id, "Ваше замовлення було надіслане адміністраторам для підтвердження.")
        bot.send_message(call.from_user.id, "Очікуйте, адміністратор обробляє ваше замовлення.")
        del user_orders[call.from_user.id]
        view_cart(call)
    except Exception as e:
        print(f"Помилка при підтвердженні замовлення: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка при підтвердженні замовлення.")

# Функція для відображення головного меню
def show_main_menu(user_id):
    markup = InlineKeyboardMarkup()
    btn_products = InlineKeyboardButton("Переглянути продукти", callback_data='view_products')
    markup.add(btn_products)
    bot.send_message(user_id, 'Привіт! Оберіть одну з опцій:', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_order_'))
def handle_approve_order(call):
    try:
        user_id = int(call.data.split('_')[2])
        orders = pending_orders.get(user_id, {})

        if not orders:
            bot.answer_callback_query(call.id, "Замовлення не знайдено.")
            return

        products = get_products()

        for product_id, order in orders.items():
            if product_id == 'comment':  # Пропускаємо коментарі
                continue
            product = next((p for p in products if p['id'] == product_id), None)
            if product:
                product['count'] -= order['quantity']

        save_products(products)
        del pending_orders[user_id]

        # Сповіщення адміністратора про підтвердження
        for admin in admins:
            bot.send_message(admin, f"Замовлення підтверджено адміністратором @{call.from_user.username}")

        # Збереження замовлення у файл
        save_order_to_file(user_id, f"@{call.from_user.username}", orders, 'confirmed')

        # Оновлення кнопок
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Замовлення підтверджено ✅", callback_data='no_action'))
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Замовлення підтверджено. Дякуємо!",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Помилка при підтвердженні замовлення адміністратором: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка при підтвердженні замовлення.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_order_'))
def handle_reject_order(call):
    try:
        user_id = int(call.data.split('_')[2])
        if user_id in pending_orders:
            # Сповіщення користувача про відхилення
            bot.send_message(
                user_id,
                "Ваше замовлення було відхилене адміністратором."
            )
            
            # Запит коментаря
            bot.send_message(call.message.chat.id, "Введіть причину відхилення замовлення:")
            bot.register_next_step_handler(call.message, process_rejection_comment, user_id)
        else:
            bot.answer_callback_query(call.id, "Замовлення не знайдено.")
    except Exception as e:
        print(f"Помилка при відхиленні замовлення адміністратором: {e}")
        bot.answer_callback_query(call.id, "Виникла помилка при відхиленні замовлення.")

def process_rejection_comment(message, user_id):
    comment = message.text
    # Сповіщення адміністратора про відхилення
    for admin in admins:
        bot.send_message(admin, f"Замовлення було відхилене адміністратором @{message.from_user.username}. Причина: {comment}")

    # Збереження замовлення у файл
    if user_id in pending_orders:
        save_order_to_file(user_id, f"@{message.from_user.username}", pending_orders[user_id], 'rejected')

    # Оновлення кнопок
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Замовлення відхилено ❌", callback_data='no_action'))
    
    # Використовуйте правильний метод для оновлення повідомлення
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,  # Замість message.message.message_id використовуйте message.message_id
        text="Замовлення відхилене. Дякуємо!",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'add_comment')
def add_comment(call):
    bot.send_message(call.message.chat.id, "Введіть ваш коментар:")
    bot.register_next_step_handler(call.message, process_comment)

def process_comment(message):
    user_id = message.from_user.id
    comment = message.text
    
    # Додаємо коментар до замовлення
    if user_id in user_orders:
        user_orders[user_id]['comment'] = comment
        bot.send_message(message.chat.id, "Ваш коментар був доданий до замовлення.")
    else:
        bot.send_message(message.chat.id, "Ваш кошик порожній. Не вдалося додати коментар.")

def bot_start():
    for admin in admins:
        try:
            bot.send_message(admin, 'Бот запущений')
        except telebot.apihelper.ApiTelegramException as e:
            print(f"Не вдалося надіслати повідомлення адміну {admin}: {e}")

bot_start()
bot.polling()

