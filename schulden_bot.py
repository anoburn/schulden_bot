from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError
import logging
import verwaltung
import pickle
import os.path

# USER STATES:
# 0: initial
# 1: contact received. waiting for Betrag
# 2: Kontakte-Keyboard wird gezeigt. Wartet auf Auswahl oder neuen Kontakt
# 3: Gruppenzahlung. Kontakte-Keyboard wird gezeigt. Wartet auf Kontakte oder Betrag

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)


folder = os.path.dirname(os.path.abspath(__file__)) + "/"

with open(folder + "token.txt", "r") as token_file:
    token = token_file.readline()
updater = Updater(token=token)     # Insert bot token here
dispatcher = updater.dispatcher


def save_verwalter():
    with open(folder + "verwalter.obj", "wb") as verwalter_datei:
        pickle.dump(verwalter, verwalter_datei)


def isfloat(value):
  try:
    float(value)
    return True
  except ValueError:
    return False


if os.path.isfile(folder + "verwalter.obj"):
    with open(folder + "verwalter.obj", "rb") as verwalter_datei:
        verwalter = pickle.load(verwalter_datei)
else:
    verwalter = verwaltung.Verwalter()


base_markup = ReplyKeyboardMarkup([["Bilanz", "Schulden hinzufügen"], ["Abbrechen", "Gruppenzahlung"]],
                                  resize_keyboard=True)


def start(bot, update):
    """ To do: erkennen wenn bot in einer Gruppe ist """
    user_id = update.message.from_user.id
    bot.send_message(chat_id=update.message.chat_id,
                     text="Hallo! Ich bin der Schulden_bot!\n Sende mir einen Kontakt um loszulegen",
                     reply_markup=base_markup)
    ensure_user(user_id, bot)
    verwalter.users[user_id].available = True

dispatcher.add_handler(CommandHandler("start", start))


def cancel(bot, update):
    user_id = get_id_from_update(update)
    verwalter.users[user_id].state = 0
    verwalter.users[user_id].targets = []
    query = update.callback_query
    if not query is None:
        bot.edit_message_text(chat_id=query.message.chat_id, message_id=query.message.message_id,
                                text=query.message.text + "\nVorgang abgebrochen" ,reply_markup=None)
    else:
        bot.send_message(chat_id=user_id, text="Vorgang abgebrochen")

dispatcher.add_handler(CommandHandler("cancel", cancel))


def query_function(bot, update):
    query = update.callback_query
    user_id = query.from_user.id
    ensure_user(user_id, bot)
    text_old = query.message.text

    query_split = query.data.split(' ')
    if query_split[0] == 'accept':
        bot.editMessageReplyMarkup(chat_id=query.message.chat_id, message_id=query.message.message_id, reply_markup=None)
        return

    if query_split[0] == 'reject':
        debt_from = int(query_split[1])
        debt_to   = int(query_split[2])
        betrag    = float(query_split[3])
        add_debt_intern(debt_from, debt_to, - betrag)
        logging.info('Rejected debt')
        text = "{} hat {}€ Schulden abgelehnt.".format(verwalter.users[user_id].name, betrag)
        bot.send_message(chat_id=debt_to, text=text)
        text = "Du hast {}€ Schulden an {} abgelehnt".format(betrag, verwalter.users[debt_to].name)
        bot.edit_message_text(text=text, chat_id=query.message.chat_id, message_id=query.message.message_id)
        return

    if query_split[0] == "cancel":
        cancel(bot, update)
        return

    if query_split[0] == "add_all":
        for contact in verwalter.users[user_id].contacts:
            name = verwalter.users[contact].name
            if verwalter.users[contact].available:
                if not contact in verwalter.users[user_id].targets:
                    verwalter.users[user_id].targets.append(contact)
        bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        input_contact(bot, update)
        return

    if query.data.isdigit():
        target_id = int(query.data)
        ensure_user(target_id, bot)

        verwalter.users[user_id].targets.append(target_id)
        if verwalter.users[user_id].state == 2:
            verwalter.users[user_id].state = 1
            input_betrag(bot, user_id)

            bot.edit_message_text(text=text_old + "\nAusgewählt: %s"%verwalter.users[target_id].name,
                                  chat_id=query.message.chat_id,
                                  message_id=query.message.message_id)
            return
        elif verwalter.users[user_id].state == 3:
            bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
            input_contact(bot, update)
            return
    bot.editMessageReplyMarkup(chat_id=query.message.chat_id, message_id=query.message.message_id, reply_markup=None)
    bot.edit_message_text(text=text_old + "\nVorgang abgebrochen, Zustand nicht mehr aktuell",
                          chat_id=query.message.chat_id, message_id=query.message.message_id)
    return

dispatcher.add_handler(CallbackQueryHandler(query_function))


def find_id(username):
    for key in verwalter.users.keys():
        if verwalter.users[key].name == username:
            return key
    logging.error("Couldn't find id to username %s"%username)
    return -1


def get_id_from_update(update):
    if not update.message is None:
        return update.message.from_user.id
    elif not update.callback_query is None:
        return update.callback_query.from_user.id
    else:
        logging.error("No user id found, strange update")
        return None


def ensure_user(user_id, bot):
    if user_id not in verwalter.users.keys():
        verwalter.ensure_user(user_id, bot)
        logging.info("User %i, also known as %s, added to system"%(user_id, verwalter.users[user_id].name))
        save_verwalter()


def add_debt_intern(von_id, an_id, betrag):
    if von_id == an_id:
        logging.debug("Given order to add debt to self")
        return

    verwalter.add_debt(von_id, an_id, betrag)
    save_verwalter()


def add_debt(bot, user_id, target_id, betrag, reason_text=None):
    add_debt_intern(target_id, user_id, betrag)
    if not user_id in verwalter.users[target_id].contacts:
        verwalter.users[target_id].add_contact(user_id)
    betrag = round(betrag, 2)
    target_text = "{} hat dir Schulden in Höhe von {} eingetragen".format(verwalter.users[user_id].name, betrag)
    user_text = "Du hast {} Schulden in Höhe von {} eingetragen".format(verwalter.users[target_id].name, betrag)
    if not reason_text is None:
        target_text += " für {}".format(reason_text)
        user_text   += " für {}".format(reason_text)
    accept_button = InlineKeyboardButton("Accept", callback_data='accept')
    reject_button = InlineKeyboardButton("Reject", callback_data='reject {} {} {}'.format(target_id, user_id, betrag))
    target_markup = InlineKeyboardMarkup([[accept_button, reject_button]], resize_keyboard=True, one_time_keyboard=True)
    bot.send_message(chat_id=user_id, text=user_text)
    bot.send_message(chat_id=target_id, text=target_text, reply_markup=target_markup)
    verwalter.users[user_id].state = 0
    save_verwalter()


def input_contact(bot, update):
    logging.info("input_contact aufgerufen")
    user_id = get_id_from_update(update)
    ensure_user(user_id, bot)

    keyboard = []
    cancel_button = InlineKeyboardButton("Aktion abbrechen", callback_data="cancel")
    not_availables = ""
    for contact in verwalter.users[user_id].contacts:
        name = verwalter.users[contact].name
        if verwalter.users[contact].available:
            if not contact in verwalter.users[user_id].targets:
                button = InlineKeyboardButton(name, callback_data=contact)
                keyboard.append([button])
        else:
            not_availables += name + " "
    if not not_availables == "":
        not_availables = "\n(" + not_availables +  "noch nicht verfügbar)"

    if verwalter.users[user_id].state == 2:
        text = "Um wen geht es? Bitte wähle einen Namen aus oder sende mir einen Kontakt"
        targets = ""
        keyboard.append([cancel_button])
    else:   # state == 3
        text = "Wer beteiligt sich an den Kosten? Wähle alle aus die dazugehören und sende mir dann den Gesamtbetrag (Optional: Mit Begründung)"
        targets = ""
        for target_id in verwalter.users[user_id].targets:
            targets += verwalter.users[target_id].name + "  "
        targets = "\nMomentan ausgewählt: " + targets
        all_button = InlineKeyboardButton("Alle", callback_data="add_all")
        keyboard.insert(0, [all_button, cancel_button])
    contact_markup = InlineKeyboardMarkup(keyboard, resize_keyboard = True)
    bot.send_message(chat_id=user_id, text=text + not_availables + targets, reply_markup=contact_markup)

input_contact_handler = CommandHandler("input_contact", input_contact)
dispatcher.add_handler(input_contact_handler)


def input_betrag(bot, user_id):
    logging.info("input_betrag aufgerufen")

    ensure_user(user_id, bot)

    for target_id in verwalter.users[user_id].targets:
        if not verwalter.users[target_id].available:
            verwalter.users[user_id].state = 0
            bot.send_message(chat_id=user_id,
                    text="{} hat mich noch nicht hinzugefügt. Vorgang kann nicht durchgeführt werden.".format(verwalter.users[target_id].name))
            return

    verwalter.users[user_id].state = 1

    text = "Wie viel schuldet %s dir? (Optional: Warum?)\n"%verwalter.users[ verwalter.users[user_id].targets[0] ].name
    bot.send_message(chat_id=user_id, text=text)


def contact(bot, update):
    logging.info("contact aufgerufen")
    target = update.message.contact
    user_id = update.message.from_user.id
    ensure_user(user_id, bot)
    ensure_user(target.user_id, bot)

    verwalter.users[user_id].add_contact(target.user_id)
    save_verwalter()

contact_handler = MessageHandler(Filters.contact, contact)
dispatcher.add_handler(contact_handler)


def show_bilanz(bot, update):
    logging.info("show_bilanz aufgerufen")
    user_id = update.message.from_user.id
    ensure_user(user_id, bot)

    bilanz = verwalter.get_balance(user_id)
    if len(bilanz) == 0:
        text = "Du hast derzeit keine Schulden offen"
    else:
        text = "Du schuldest \n"
        for name, betrag in bilanz:
            text += "%s noch %.2f€\n"%(name, betrag)
    bot.send_message(chat_id=user_id, text=text, reply_markup=base_markup)

bilanz_handler = CommandHandler("bilanz", show_bilanz)
dispatcher.add_handler(bilanz_handler)


def scan_group(bot, update):
    chat = update.message.chat
    logging.info("Scanning group {}".format(chat.id))
    total_members = chat.get_members_count()
    found_members = 0
    for user_id in verwalter.users.keys():
        try:
            _ = chat.get_member(user_id)
            found_members += 1      # only done if user is found
        except TelegramError:
            pass
    if found_members < total_members - 1:   # subtract bot itself
        chat.send_message("Not all members have activated the bot")
        logging.info("Not all members have activated the bot")
    else:
        chat.send_message("Yay, everyone has activated the bot")
        logging.info("Everyone has activated the bot")

dispatcher.add_handler(CommandHandler("scan_group", scan_group))


def add_gruppenzahlung(bot, update):
    logging.info("add_gruppen_schulden aufgerufen")
    user_id = update.message.from_user.id
    print(dir(update.message.chat))

dispatcher.add_handler(CommandHandler("gruppenzahlung", add_gruppenzahlung))


def message(bot, update):
    logging.info("message aufgerufen")
    user_id = update.message.chat_id
    ensure_user(user_id, bot)
    text = update.message.text

    if text == "Bilanz":
        show_bilanz(bot, update)
        return

    elif text == "Schulden hinzufügen":
        verwalter.users[user_id].state = 2
        verwalter.users[user_id].targets = []
        input_contact(bot, update)
        return

    elif text == "Gruppenzahlung":
        verwalter.users[user_id].state = 3
        verwalter.users[user_id].targets = []
        input_contact(bot, update)
        return

    elif text == "Abbrechen":
        cancel(bot, update)
        return

    if verwalter.users[user_id].state == 1:
        inhalt = text.split(' ', 1)
        if isfloat(inhalt[0]):
            betrag = float(inhalt[0])
            target_id = verwalter.users[user_id].targets[0]
            if len(inhalt) == 2:
                add_debt(bot, user_id, target_id, betrag, inhalt[1])
            else:
                add_debt(bot, user_id, target_id, betrag)
        return
    elif verwalter.users[user_id].state == 3:
        inhalt = text.split(' ', 1)
        if isfloat(inhalt[0]):
            targets = verwalter.users[user_id].targets
            if len(targets) == 0:
                bot.send_message(chat_id=user_id, text="Du musst erst Personen auswählen, DANN den Betrag senden")
                return
            betrag = float(inhalt[0])
            betrag_each = betrag / (len(targets) + 1)
            for target_id in targets:
                if len(inhalt) == 2:
                    add_debt(bot, user_id, target_id, betrag_each, inhalt[1])
                else:
                    add_debt(bot, user_id, target_id, betrag_each)
            return

    logging.info("Bis zum Ende")
    bot.editMessageReplyMarkup(chat_id=user_id, message_id=update.message.message_id, reply_markup=base_markup)

message_handler = MessageHandler(Filters.text, message)
dispatcher.add_handler(message_handler)


def return_state(bot, update):
    user_id = update.message.from_user.id
    ensure_user(user_id, bot)

    state = verwalter.users[user_id].state
    bot.send_message(chat_id=user_id, text="Du bist im state %i"%state)

dispatcher.add_handler(CommandHandler("state", return_state))


logging.info("Starting bot")
updater.start_polling()
updater.idle()

logging.info("Bot has stopped polling")
