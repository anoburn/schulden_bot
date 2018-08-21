from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import verwalter
import user
import pickle
import os.path

# USER STATES:
# 0: initial
# 1: contact received. waiting for Betrag
# 2: Kontakte-Keyboard wird gezeigt. Wartet auf Auswahl oder neuen Kontakt

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

updater = Updater(token="")     # Insert bot token here
dispatcher = updater.dispatcher

folder = os.path.dirname(os.path.abspath(__file__)) + "/"

def save_users():
    datei = open(folder + "users.obj", "wb")
    pickle.dump(users,datei)


def save_verwalter():
    datei = open(folder + "schulden.obj", "wb")
    pickle.dump(schulden,datei)


def isfloat(value):
  try:
    float(value)
    return True
  except ValueError:
    return False



if os.path.isfile(folder + "users.obj"):
    file = open(folder + "users.obj", "rb")
    users = pickle.load(file)
else:
    users = {}

if os.path.isfile(folder + "schulden.obj"):
    file = open(folder + "schulden.obj", "rb")
    schulden = pickle.load(file)
else:
    schulden = verwalter.Verwalter()



base_markup = ReplyKeyboardMarkup([["Bilanz", "Schulden hinzufügen"]], resize_keyboard=True)


def start(bot, update):
    """ To do: erkennen wenn bot in einer Gruppe ist """
    user_id = update.message.from_user.id
    bot.send_message(chat_id=update.message.chat_id,
                     text="Hallo! Ich bin der Schulden_bot! Sende mir einen Kontakt um loszulegen",
                     reply_markup=base_markup)
    ensure_user(user_id, bot)
    users[user_id].available = True

dispatcher.add_handler(CommandHandler("start", start))


def query_function(bot, update):
    query = update.callback_query
    user_id = query.from_user.id
    ensure_user(user_id, bot)

    query_split = query.data.split(' ')
    if query_split[0] == 'accept':
        bot.editMessageReplyMarkup(chat_id=query.message.chat_id, message_id=query.message.message_id, reply_markup=None)
        return

    if query_split[0] == 'reject':
        debt_from = int(query_split[1])
        debt_to   = int(query_split[2])
        betrag    = float(query_split[3])
        add_debt(debt_from, debt_to, - betrag)
        logging.info('Rejected debt')
        text = "{} hat {}€ Schulden abgelehnt.".format(users[user_id].name, betrag)
        bot.send_message(chat_id=debt_to, text=text)
        text = "Du hast {}€ Schulden an {} abgelehnt".format(betrag, users[debt_to].name)
        bot.edit_message_text(text=text, chat_id=query.message.chat_id, message_id=query.message.message_id)
        return

    elif query.data.isdigit():
        target_id = int(query.data)
        ensure_user(target_id, bot)

        users[user_id].target_id = target_id
        users[user_id].state = 1

        text_old = query.message.text
        bot.edit_message_text(text=text_old + "\n%s"%users[ target_id ].name,
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id)

        input_betrag(bot, user_id)

dispatcher.add_handler(CallbackQueryHandler(query_function))


def find_id(username):
    for key in users.keys():
        if users[key].name == username:
            return key
    logging.error("Couldn't find id to username %s"%username)
    return -1



def ensure_user(user_id, bot):
    if user_id not in users.keys():
        users[user_id] = user.User(user_id, bot)
        schulden.ensure_user(user_id)
        logging.info("User %i, also known as %s, added to system"%(user_id, users[user_id].name))
        save_users()



def add_debt(von_id, an_id, betrag):
    if von_id == an_id:
        logging.debug("Given order to add debt to self")
        return

    schulden.add_debt(von_id, an_id, betrag)
    save_verwalter()


def input_contact(bot, update):
    logging.info("input_contact aufgerufen")
    user_id = update.message.from_user.id
    ensure_user(user_id, bot)

    keyboard = []
    for contact in users[user_id].contacts:
        name = users[contact].name
        button = InlineKeyboardButton(name, callback_data=contact)
        keyboard.append([button])
    contact_markup = InlineKeyboardMarkup(keyboard, resize_keyboard = True, one_time_keyboard = True)
    bot.send_message(chat_id=user_id, text="Um wen geht es? Bitte wähle einen Namen aus oder sende mir einen Kontakt", reply_markup=contact_markup)

input_contact_handler = CommandHandler("input_contact", input_contact)
dispatcher.add_handler(input_contact_handler)



def input_betrag(bot, user_id):
    logging.info("input_betrag aufgerufen")

    ensure_user(user_id, bot)

    if not users[ users[user_id].target_id ].available:
        users[user_id].state = 0
        bot.send_message(chat_id=user_id, text="Dein Ziel hat mich noch nicht hinzugefügt. Vorgang kann nicht durchgeführt werden.")
        return

    users[user_id].state = 1

    text = "Wie viel schuldet %s dir? (Optional: Warum?)\n"%users[ users[user_id].target_id ].name
    bot.send_message(chat_id=user_id, text=text)



def contact(bot, update):
    logging.info("contact aufgerufen")
    target = update.message.contact
    user_id = update.message.from_user.id
    ensure_user(user_id, bot)
    ensure_user(target.user_id, bot)

    users[user_id].add_contact(target.user_id)
    users[target.user_id].add_contact(user_id)
    users[user_id].target_id = target.user_id
    save_users()

    input_betrag(bot, user_id)
   

contact_handler = MessageHandler(Filters.contact, contact)
dispatcher.add_handler(contact_handler)


def show_bilanz(bot, update):
    logging.info("show_bilanz aufgerufen")
    user_id = update.message.from_user.id
    ensure_user(user_id, bot)

    bilanz = schulden.get_balance(user_id)
    text = "Du schuldest \n"
    for id, betrag in bilanz:
        name = users[id].name
        text += "%s noch %.2f€\n"%(name, betrag)
    bot.send_message(chat_id=user_id, text=text, reply_markup=base_markup)

bilanz_handler = CommandHandler("bilanz", show_bilanz)
dispatcher.add_handler(bilanz_handler)




def message(bot, update):
    logging.info("message aufgerufen")
    user_id = update.message.chat_id
    ensure_user(user_id, bot)
    text = update.message.text

    if text == "Bilanz":
        show_bilanz(bot, update)
        return

    elif text == "Schulden hinzufügen":
        users[user_id].state = 2
        input_contact(bot, update)
        return


    if users[user_id].state == 1:
        inhalt = text.split(' ', 1)
        if isfloat(inhalt[0]):
            betrag = float(inhalt[0])
            target_id = users[user_id].target_id
            add_debt(target_id, user_id, betrag)
            target_text = "{} hat dir Schulden in Höhe von {} eingetragen".format(users[user_id].name, betrag)
            if len(inhalt) == 2:
                target_text += " für {}".format(inhalt[1])
            accept_button = InlineKeyboardButton("Accept", callback_data = 'accept')
            reject_button = InlineKeyboardButton("Reject", callback_data='reject {} {} {}'.format(target_id, user_id, betrag))
            target_markup = InlineKeyboardMarkup([[accept_button, reject_button]], resize_keyboard=True, one_time_keyboard=True)
            bot.send_message(chat_id=user_id, text="Schulden hinzugefügt")
            bot.send_message(chat_id=target_id, text=target_text, reply_markup=target_markup)
            users[user_id].state = 0
            save_users()
        return

    if users[user_id].state == 2:
        target_id = find_id(text)
        if not target_id == -1:
            users[user_id].target_id = target_id
            input_betrag(bot, user_id)
        return

    logging.info("Bis zum Ende")
    bot.editMessageReplyMarkup(chat_id=user_id, message_id=update.message.message_id, reply_markup=base_markup)


def return_state(bot, update):
    user_id = update.message.from_user.id
    ensure_user(user_id, bot)

    state = users[user_id].state
    bot.send_message(chat_id=user_id, text="Du bist im state %i"%state)

dispatcher.add_handler(CommandHandler("state", return_state))



message_handler = MessageHandler(Filters.text, message)
dispatcher.add_handler(message_handler)









logging.info("Starting bot")
updater.start_polling()
updater.idle()


logging.info("Bot has stopped polling")
