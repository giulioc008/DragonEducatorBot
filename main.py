from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
import datetime
import functools
import logging as logger
import math
import os
import pymysql
from pyrogram import CallbackQuery, Client, Emoji, Filters, InlineKeyboardButton, InlineKeyboardMarkup, InlineQuery, InlineQueryResultArticle, Message
from pyrogram.api import functions
from pyrogram.errors import ChannelInvalid, FloodWait
import re
import requests
import res
from res import Configurations
from string import Template
from telegraph import Telegraph

backpack_update = {
	"time": None,
	"threshold": 5
}

configurations_map = {
	"commands": "commands",
	"database": "database",
	"logger": "logger"
}

loop = asyncio.get_event_loop()

config = Configurations("config/config.json", configurations_map)
loop.run_until_complete(config.parse())
config.set("app_hash", os.environ.pop("app_hash", None))
config.set("app_id", int(os.environ.pop("app_id", None)))
config.set("bot_token", os.environ.pop("bot_token", None))
config.set("bot_username", os.environ.pop("bot_username", None))

connection = pymysql.connect(
	host=config.get("database")["host"],
	user=os.environ.pop("database_username", config.get("database")["username"]),
	password=os.environ.pop("database_password", config.get("database")["password"]),
	database=config.get("bot_username"),
	port=int(config.get("database")["port"]),
	charset="utf8",
	cursorclass=pymysql.cursors.DictCursor,
	autocommit=False)

logger.basicConfig(
	filename=config.get("logger")["path"],
	datefmt="%d/%m/%Y %H:%M:%S",
	format=config.get("logger")["format"],
	level=config.get("logger").pop("level", logger.INFO))

nest_pinned_message = None
scheduler = AsyncIOScheduler()
statistics = {
	"ability": {
		"id": 0,
		"quantity": 0
	},
	"craft_points": {
		"id": 0,
		"quantity": 0
	},
	"dragon": {
		"id": 0,
		"quantity": 0
	},
	"experience": {
		"id": 0,
		"quantity": 0
	},
	"rank": {
		"id": 0,
		"quantity": 0
	},
	"weekly_craft_points": {
		"id": 0,
		"quantity": 0
	}
}

with connection.cursor() as cursor:
	logger.info("Setting the Loot Bot API token list ...")
	cursor.execute("SELECT `value` FROM `info` WHERE `key`=%(key)s;", {
		"key": "loot_bot_API_token"
	})
	config.set("loot_bot_API_token", cursor.fetchone()["value"])

	logger.info("Token setted\nSetting the id list ...")
	cursor.execute("SELECT `id` FROM `Players` WHERE `domain`=\'creator\';")
	config.set("creator", int(cursor.fetchone()["id"]))

	cursor.execute("SELECT `id` FROM `Chats` WHERE `username`=%(user)s AND `type`=\'bot\';", {
		"user": "lootgamebot"
	})
	config.set("loot_bot", int(cursor.fetchone()["id"]))

	cursor.execute("SELECT `id` FROM `Chats` WHERE `username`=%(user)s AND `type`=\'bot\';", {
		"user": "lootplusbot"
	})
	config.set("loot_plus_bot", int(cursor.fetchone()["id"]))

	cursor.execute("SELECT `id` FROM `Chats` WHERE `type`!=\'bot\';")
	chats_list = list(map(lambda n: int(n["id"]), cursor.fetchall()))

	cursor.execute("SELECT `id` FROM `Chats` WHERE `title` COLLATE utf8_general_ci LIKE \'%ARTEFICI%\' AND `type` LIKE \'%group\';")
	makers_chat = int(cursor.fetchone()["id"])

	cursor.execute("SELECT `id` FROM `Chats` WHERE `title` COLLATE utf8_general_ci LIKE \'%NIDO%\' AND `type` LIKE \'%group\';")
	nest_chat = int(cursor.fetchone()["id"])

	logger.info("Id setted\nSetting the admins list ...")
	cursor.execute("SELECT `id` FROM `Players` WHERE `domain`!=\'all\';")
	admins_list = list(map(lambda n: int(n["id"]), cursor.fetchall()))

	logger.info("Admins setted\nSetting the players list ...")
	cursor.execute("SELECT `id` FROM `Players`;")
	players_allowed_list = list(map(lambda n: int(n["id"]), cursor.fetchall()))

logger.info("Chats initializated\nInitializing the Client ...")
app = Client(session_name=config.get("bot_username"), api_id=config.get("app_id"), api_hash=config.get("app_hash"), bot_token=config.get("bot_token"), lang_code="it", workdir=".")


@app.on_message(Filters.command("add", prefixes="/") & (Filters.user(admins_list) | Filters.channel))
async def add_to_the_database(client: Client, message: Message):
	# /add [domain] [type_into_guild]
	global admins_list, chats_list, config, connection, players_allowed_list

	message.command.pop(0)

	# Checking if the message arrive from a channel and, if not, checking if the user that runs the command is allowed
	with connection.cursor() as cursor:
		if message.from_user is not None and cursor.execute("SELECT NULL FROM `Players` WHERE `id`=%(id)s AND (`domain`=\'creator\' OR `domain`==\'princeps\');", {
			"id": message.from_user.id
		}) == 0:
			await res.split_reply_text(config, message, "You can\'t use this command.", quote=False)
			logger.info("{} have sent an incorrect /add request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
			return

	# Checking if the data are of a chat or of a user
	if message.reply_to_message is not None:
		# Checking if the user is authorized
		if message.reply_to_message.from_user.id not in players_allowed_list:
			await res.split_reply_text(config, message, "You can\'t do admin a user external to the Dragon Guild.", quote=False)
			logger.info("{} have sent an incorrect /add request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
			return

		# Checking if the user is in the admins list
		if message.reply_to_message.from_user.id in admins_list:
			await res.split_reply_text(config, message, "The user @{} is already an admin.".format(message.reply_to_message.from_user.username), quote=False)
			logger.info("{} have sent an incorrect /add request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
			return

		# Retrieving the data of the new admin
		chat = {
			"id": message.reply_to_message.from_user.id
		}

		# Adding the new admin to the list
		admins_list.append(chat["id"])
	else:
		# Checking if the chat is in the list
		if message.chat.id in chats_list:
			await res.split_reply_text(config, message, "The chat {} is already present in the list of allowed chat.".format(message.chat.title), quote=False)
			logger.info("{} have sent an incorrect /add request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
			return

		# Retrieving the data of the chat
		chat = message.chat
		chat = chat.__dict__

		# Deleting the message
		await message.delete(revoke=True)

		chat["welcome"] = None
		chat["type_into_guild"] = message.command.pop(1) if len(message.command) == 2 else "other"

		# Adding the chat to the list
		chats_list.append(chat["id"])

	chat["domain"] = message.command.pop(0) if message.command is True else "exarch"

	# Removing inutil informations
	chat.pop("_client", None)
	chat.pop("_", None)
	chat.pop("photo", None)
	chat.pop("description", None)
	chat.pop("pinned_message", None)
	chat.pop("sticker_set_name", None)
	chat.pop("can_set_sticker_set", None)
	chat.pop("members_count", None)
	chat.pop("restrictions", None)
	chat.pop("permissions", None)
	chat.pop("distance", None)
	chat.pop("status", None)
	chat.pop("last_online_date", None)
	chat.pop("next_offline_date", None)
	chat.pop("dc_id", None)
	chat.pop("is_self", None)
	chat.pop("is_contact", None)
	chat.pop("is_mutual_contact", None)
	chat.pop("is_deleted", None)
	chat.pop("is_bot", None)
	chat.pop("is_verified", None)
	chat.pop("is_restricted", None)
	chat.pop("is_scam", None)
	chat.pop("is_support", None)
	chat.pop("language_code", None)

	with connection.cursor() as cursor:
		if chat.get("type", None) is None:
			# Updating the players database
			cursor.execute("UPDATE `Players` SET `domain`=%(domain)s WHERE `id`=%(id)s;", chat)

			if cursor.execute("SELECT `id` FROM `Chats` WHERE `type`!=\'bot\' AND (`domain`=\'exarch\' OR `type_into_guild`=\'utility\' OR `type_into_guild`=\'team\');") != 0:
				chats = list(map(lambda n: int(n["id"]), cursor.fetchall()))

				for i in chats:
					# Checking if the user is in the chat
					try:
						await client.get_chat_member(i, chat["id"])
					except ChannelInvalid:
						# Adding the user to the chat
						await client.add_chat_members(i, chat["id"])

			if cursor.execute("SELECT `id` FROM `Chats` WHERE `type`!=\'bot\' AND `domain`=\'all\' AND `type_into_guild`=\'utility\';") != 0:
				chats = list(map(lambda n: int(n["id"]), cursor.fetchall()))

				for i in chats:
					# Checking if the user is in the chat
					try:
						await client.get_chat_member(i, chat["id"])
					except ChannelInvalid:
						# Updating the player's privilege
						await client.promote_chat_member(i, chat["id"], can_change_info=True, can_post_messages=True, can_edit_messages=False, can_delete_messages=True, can_restrict_members=True, can_invite_users=True, can_pin_messages=True, can_promote_members=False)

			text = "Admin added to the database."
		else:
			# Adding the chats to the database
			cursor.execute("INSERT INTO `Chats` (`id`, `type`, `title`, `username`, `first_name`, `last_name`, `invite_link`, `welcome`, `domain`) VALUES (%(id)s, %(type)s, %(title)s, %(username)s, %(first_name)s, %(last_name)s, %(invite_link)s,  %(welcome)s, %(domain)s);", chat)

			text = "Chat added to the database."
	connection.commit()

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /add because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("addnest", prefixes="/") & Filters.user(admins_list) & Filters.private)
async def add_to_the_database_nest(client: Client, message: Message):
	# /addnest <username> <objective_level>
	global config, connection

	message.command.pop(0)

	# Checking if the command is correct
	if len(message.command) != 2:
		await res.split_reply_text(config, message, "The syntax is: <code>/addnest &lt;username&gt; &lt;objective_level&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /addnest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the user's data
	user = await client.get_users(message.command.pop(0))

	# Retrieving the objective
	try:
		objective = int(message.command.pop(0))
	except ValueError:
		await res.split_reply_text(config, message, "The syntax is: <code>/addnest &lt;username&gt; &lt;objective_level&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /addnest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Converting the objective
	if objective > 300:
		objective = 300

	# Adding the objective to the database
	with connection.cursor() as cursor:
		cursor.execute("INSERT INTO `Nest` (`id`, `level`, `missing_points`, `objective`) VALUES (%(id)s, %(level)s, %(missing_points)s, %(objective)s);", {
			"id": user.id,
			"level": 0,
			"missing_points": 21000,
			"objective": objective
		})
	connection.commit()

	await res.split_reply_text(config, message, "Player added to the Nest database.", quote=False)
	logger.info("I\'ve answered to /addnest because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("ads", prefixes="/") & Filters.user(admins_list) & Filters.private)
async def announces(client: Client, message: Message):
	# /ads <text>
	global config

	message.command.pop(0)

	# Checking if the command is correct
	if message.command is False:
		await res.split_reply_text(config, message, "The syntax is: <code>/ads &lt;text&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /announces request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the chats' list
	with connection.cursor() as cursor:
		cursor.execute("SELECT `id` FROM `Chats` WHERE `type` LIKE \'%group\';")
		chats = list(map(lambda n: int(n["id"]), cursor.fetchall()))

	# Retrieving the ad
	text = " ".join(message.command)

	for i in chats:
		await client.send_message(i, text)

	logger.info("I\'ve answered to /ads because of {}.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))


@app.on_callback_query(Filters.user(players_allowed_list) & (Filters.chat(chats_list) | Filters.private))
async def answer_inline_button(client: Client, callback_query: CallbackQuery):
	global config, connection

	# Retrieving the data of the CallbackQuery
	data = callback_query.data.split("!")

	"""
		data[0] is the text of the button
		data[1] is the id of the user that do the request for the Smuggler or the flag that manage the craft or the items list
		data[2] is the items list
	"""

	# Retrieving the keyboard of the CallbackQuery
	if len(data) != 1:
		keyboard = callback_query.message.reply_markup.inline_keyboard
	else:
		keyboard = list()

	# Retrieving the text of the CallbackQuery
	text = callback_query.message.text

	# Checking if the CallbackQuery have the correct syntax
	if data[0] == "Booked":
		# Booking the Smuggler's offert
		with connection.cursor() as cursor:
			cursor.execute("UPDATE `Smuggler` SET `booked_from`=%(booked_from)s WHERE `id`=%(id)s;", {
				"id": int(data[1]),
				"booked_from": callback_query.from_user.id
			})
		connection.commit()

		# Restructuring the InlineKeyboard
		data[0] = "Cancel the reservation"
		keyboard[0] = [
			InlineKeyboardButton(data[0], callback_data="!".join(data))
		]

		text += "\n\nThe request is booked from @{}".format(callback_query.from_user.username)
	elif data[0] == "Free":
		# Checking if the user that press the button is authorized
		if data[1] != callback_query.from_user.id:
			await callback_query.answer("You aren\'t to use this button", show_alert=True)
			logger.info("I have answered to an Inline button.")
			return

		# Free the Smuggler's offert
		with connection.cursor() as cursor:
			cursor.execute("UPDATE `Smuggler` SET `free`=%(free)s WHERE `id`=%(id)s;", {
				"id": int(data[1]),
				"free": 1
			})
		connection.commit()

		# Restructuring the InlineKeyboard
		data[0] = "Not free"
		keyboard[1] = [
			InlineKeyboardButton(data[0], callback_data="!".join(data))
		]

		text += "\n\nThe request is <i>Free</i>"
	elif data[0] == "Private":
		# Checking if the user that press the button is authorized
		if data[1] != callback_query.from_user.id:
			await callback_query.answer("You aren\'t to use this button", show_alert=True)
			logger.info("I have answered to an Inline button.")
			return

		# Privatizing the Smuggler's offert
		with connection.cursor() as cursor:
			cursor.execute("UPDATE `Smuggler` SET `private`=%(private)s WHERE `id`=%(id)s;", {
				"id": int(data[1]),
				"private": 1
			})
		connection.commit()

		# Restructuring the InlineKeyboard
		data[0] = "Not private"
		keyboard[2] = [
			InlineKeyboardButton(data[0], callback_data="!".join(data))
		]

		text += "\n\nThe request is <i>Private</i>"
	elif data[0] == "Close":
		# Checking if the user that press the button is authorized
		if data[1] != callback_query.from_user.id:
			await callback_query.answer("You aren\'t to use this button", show_alert=True)
			logger.info("I have answered to an Inline button.")
			return

		# Closing the Smuggler's offert
		with connection.cursor() as cursor:
			cursor.execute("DELETE FROM `Smuggler` WHERE `id`=%(id)s;", {
				"id": int(data[1])
			})
		connection.commit()

		# Restructuring the InlineKeyboard
		keyboard = None

		text += "\n\n<b>Request closed</b>"
	elif data[0] == "Cancel the reservation":
		# Checking if the user that press the button is authorized
		with connection.cursor() as cursor:
			if cursor.execute("SELECT NULL FROM `Smuggler` WHERE `id`=%(id)s AND `booked_from`=%(booked_from)s;", {
				"id": int(data[1]),
				"booked_from": callback_query.from_user.id
			}) == 0:
				await callback_query.answer("You aren\'t to use this button", show_alert=True)
				logger.info("I have answered to an Inline button.")
				return

		# Unbooking the Smuggler's offert
		with connection.cursor() as cursor:
			cursor.execute("UPDATE `Smuggler` SET `booked_from`=%(booked_from)s WHERE `id`=%(id)s;", {
				"id": int(data[1]),
				"booked_from": None
			})
		connection.commit()

		# Restructuring the InlineKeyboard
		data[0] = "Booked"
		keyboard[0] = [
			InlineKeyboardButton(data[0], callback_data="!".join(data))
		]

		text = text.replace("\n\nThe request is booked from @{}".format(callback_query.from_user.username), "")
	elif data[0] == "Not free":
		# Checking if the user that press the button is authorized
		if data[1] != callback_query.from_user.id:
			await callback_query.answer("You aren\'t to use this button", show_alert=True)
			logger.info("I have answered to an Inline button.")
			return

		# Bind the Smuggler's offert
		with connection.cursor() as cursor:
			cursor.execute("UPDATE `Smuggler` SET `free`=%(free)s WHERE `id`=%(id)s;", {
				"id": int(data[1]),
				"free": 0
			})
		connection.commit()

		# Restructuring the InlineKeyboard
		data[0] = "Free"
		keyboard[1] = [
			InlineKeyboardButton(data[0], callback_data="!".join(data))
		]

		text = text.replace("\n\nThe request is Free", "")
	elif data[0] == "Not private":
		# Checking if the user that press the button is authorized
		if data[1] != callback_query.from_user.id:
			await callback_query.answer("You aren\'t to use this button", show_alert=True)
			logger.info("I have answered to an Inline button.")
			return

		# Deprivatize the Smuggler's offert
		with connection.cursor() as cursor:
			cursor.execute("UPDATE `Smuggler` SET `private`=%(private)s WHERE `id`=%(id)s;", {
				"id": int(data[1]),
				"private": 0
			})
		connection.commit()

		# Restructuring the InlineKeyboard
		data[0] = "Private"
		keyboard[2] = [
			InlineKeyboardButton(data[0], callback_data="!".join(data))
		]

		text = text.replace("\n\nThe request is Private", "")
	elif data[0] == "Team":
		# Retrieving the team chats
		with connection.cursor() as cursor:
			cursor.execute("SELECT `id`, `title`, `username`, `invite_link` FROM `Chats` WHERE `type_into_guild`=\'team\';")
			chat = cursor.fetchall().copy()

		chat = sorted(chat, key=lambda n: n["title"])

		# Restructuring the InlineKeyboard
		for i in chat:
			button = await res.chat_button(client, i, connection)

			keyboard.append([
				button
			])
		keyboard.append([
			InlineKeyboardButton(text="", callback_data=""),
			InlineKeyboardButton(text="Next", callback_data="Utility")
		])
	elif data[0] == "Utility":
		# Retrieving the utility chats
		with connection.cursor() as cursor:
			cursor.execute("SELECT `id`, `title`, `username`, `invite_link` FROM `Chats` WHERE `type_into_guild`=\'utility\';")
			chat = cursor.fetchall().copy()

		chat = sorted(chat, key=lambda n: n["title"])

		# Restructuring the InlineKeyboard
		for i in chat:
			button = await res.chat_button(client, i, connection)

			keyboard.append([
				button
			])
		keyboard.append([
			InlineKeyboardButton(text="Previous", callback_data="Team"),
			InlineKeyboardButton(text="Next", callback_data="Games")
		])
	elif data[0] == "Games":
		# Retrieving the games chats
		with connection.cursor() as cursor:
			cursor.execute("SELECT `id`, `title`, `username`, `invite_link` FROM `Chats` WHERE `type_into_guild`=\'games\';")
			chat = cursor.fetchall().copy()

		chat = sorted(chat, key=lambda n: n["title"])

		# Restructuring the InlineKeyboard
		for i in chat:
			button = await res.chat_button(client, i, connection)

			keyboard.append([
				button
			])
		keyboard.append([
			InlineKeyboardButton(text="Previous", callback_data="Utility"),
			InlineKeyboardButton(text="", callback_data="")
		])
	elif data[0] == "Assault":
		# Retrieving the parameters for the craft
		use_craft = True
		items_list = data[1]

		# Checking what kind of craft the players want do
		if data[1] == "All":
			use_craft = False
			items_list = data[2]

		# Retrieving the items list
		items_list = items_list.split(",")

		# Converting the items list in the opportune format
		for i in items_list:
			i = i.split(":")

			i[0] = int(i[0])
			i[2] = int(i[2])

			i = {
				"id": i[0],
				"name": i[1],
				"quantity": i[2]
			}

		craft_list = res.craft_inner(message.from_user.id, items_list, connection, use_craft)
		"""
			craft_list = {
				"commands": [
					"",
					...
				],
				"text": ""
			}
		"""

		await res.split_reply_text(config, message, craft_list.pop("text"), quote=False)

		text = craft_list.pop("commands")
		text = "</code>\n<code>".join(text)
		text = "<code>{}</code>".format(text)

	keyboard = InlineKeyboardMarkup(keyboard)

	output = await callback_query.edit_message_text(text[: config.get("message_max_length")])

	# Checking if the output text can be longest then the maximum length
	if data[0] == "Assault":
		await callback_query.edit_message_reply_markup(None)

		if len(text) >= config.get("message_max_length"):
			for i in range(1, len(text), config.get("message_max_length")):
				try:
					output = await res.split_reply_text(config, message, text[i : i + config.get("message_max_length")], quote=False)
				except FloodWait as e:
					asyncio.sleep(e.x)

		await output.edit_reply_markup(keyboard)
	else:
		await callback_query.edit_message_reply_markup(keyboard)

	logger.info("I have answered to an Inline button.")


@app.on_message(Filters.command("assignments", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def assignments(_, message: Message):
	# /assignments <name>
	global config

	message.command.pop(0)

	assignments_list = [
		{
			"key": "liquido",
			"name": "Il Liquido Blu",
			"answers": [
				1,
				1
			]
		},
		{
			"key": "gabbiano",
			"name": "Il Gabbianodonte",
			"answers": [
				1,
				1,
				1
			]
		},
		{
			"key": "formiche",
			"name": "Formiche di Lootia",
			"answers": [
			]
		},
		{
			"key": "banditi",
			"name": "La Banda dei Banditi",
			"answers": [
				1,
				1,
				3
			]
		},
		{
			"key": "fabbro",
			"name": "L\'Attrezzo di Andre il Fabbro",
			"answers": [
				1,
				3,
				2
			]
		},
		{
			"key": "fame",
			"name": "La Fame dei Boss",
			"answers": [
				2,
				1,
				1,
				3
			]
		},
		{
			"key": "sfinge",
			"name": "La Sfinge di Lootia",
			"answers": [
				1,
				1,
				3,
				1,
				1,
				1,
				2,
				2,
				2,
				1
			]
		},
		{
			"key": "dungeon diurno",
			"name": "Nel Dungeon delle Meraviglie (Diurno)",
			"answers": [
			]
		},
		{
			"key": "dungeon notturno",
			"name": "Nel Dungeon delle Meraviglie (Notturno)",
			"answers": [
			]
		},
		{
			"key": "dungeon finale",
			"name": "Nel Dungeon delle Meraviglie (Finale)",
			"answers": [
			]
		}
	]

	# Checking if the command is correct
	if len(message.command) < 1 or len(message.command) > 2:
		await res.split_reply_text(config, message, "The syntax is: <code>/assignments &lt;name&gt;</code>.\nThe name accepted are:\n\t<code>{}</code>.\n".format("</code>\n\t<code>".join(list(map(lambda n: n["key"].capitalize(), assignments_list)))), quote=False)
		logger.info("{} have sent an incorrect /assignments request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the assignment
	command = " ".join(message.command)
	command = command.lower()
	if command not in list(map(lambda n: n["key"], assignments_list)):
		await res.split_reply_text(config, message, "The syntax is: <code>/assignments &lt;name&gt;</code>.\nThe name accepted are:\n\t<code>{}</code>.\n".format("</code>\n\t<code>".join(list(map(lambda n: n["key"].capitalize(), assignments_list)))), quote=False)
		logger.info("{} have sent an incorrect /assignments request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	assignment = list(filter(lambda n: n["key"] == command, assignments_list))
	assignment = assignment.pop(0)
	text = "The answers to the Assignment <b>{}</b> are{}".format(assignment["name"], ":\n\t{}".format("\n\t".join(assignment["answers"])) if assignment["answers"] is True else " unknown.")

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /assignments because of @{}.".format(message.from_user.username))


@app.on_message(Filters.service & Filters.chat(chats_list))
async def automatic_management_service(_, message: Message):
	global config, connection

	# Checking if the message is a new_chat_members message
	if message.new_chat_members is not None:
		# Retrieving the list of the spammer by Telegram
		to_delete = message.new_chat_members.copy()
		to_delete = list(map(lambda n: n.id, to_delete))

		message.new_chat_members = list(filter(lambda n: n.is_scam is not None and n.is_scam is False, message.new_chat_members))

		for i in message.new_chat_members:
			to_delete.remove(i.id)

		# Retrieving the list of the spammer by Combot Anti Spam
		tmp = message.new_chat_members.copy()

		for i in range(len(tmp)):
			# Downloading the user's informations
			response = requests.get(url="https://api.cas.chat/check?user_id={}".format(tmp[i].id))

			# Retrieving the user's informations
			result = response.json()

			# Checking if it's a spammer
			if result["ok"] is False:
				continue

			to_delete.append(message.new_chat_members.pop(i).id)

		if to_delete is True:
			for i in to_delete:
				await message.chat.kick_member(i.id)

		# Checking if the bot was one of the new users
		if config.get("bot_id") in message.new_chat_members:
			await res.split_reply_text(config, message, "Hi, I\'m @{}\nIf you want, you can set a welcome message for the new users.\nThe rules for the welcome message are:\n\t> Use ${users} where you want the tag for the users\n\t> Use ${title} where you want the title of the group".format(config.get("bot_username")))
			await message.delete(revoke=True)
			return

		# Retrieving the welcome message
		with connection.cursor() as cursor:
			cursor.execute("SELECT `welcome` FROM `Chats` WHERE `id`=%(id)s;", {
				"id": message.chat.id
			})
			welcome = cursor.fetchone()["welcome"]

		# Checking if the welcome message is setted
		if welcome is not None:
			welcome = Template(welcome)

			# Retrieving the new users' list
			users = list(map(lambda n: "@{}".format(n.username), message.new_chat_members))

			# Personalizing the welcome message
			welcome = welcome.safe_substitute({
				"users": ", ".join(users),
				"title": message.chat.title
			})

			await res.split_reply_text(config, message, welcome, quote=False)
			logger.info("I have welcomed some users in the chat {}.".format(message.chat.title))

	await message.delete(revoke=True)


@app.on_message(Filters.text & (Filters.chat(chats_list) | Filters.private))
async def automatic_management_text(client: Client, message: Message):
	global buffers, config, connection, nest_chat

	# Checking if the message have the correct syntax
	if message.forward_from is not None and message.forward_from.id == config.get("loot_bot") and message.text.startswith("Cosa vuoi fare con il tuo drago") is True:
		# Extracting the level of the Dragon
		text = message.text.splitlines()
		text = list(filter(lambda n: n.startswith("Crescita: Livello ") is True, text))
		text = text.pop(0)
		text = text[len("Crescita: Livello ") :]
		text = text.split(" ")
		text[0] = int(text[0])

		# Extracting the missing points to the next level of the Dragon
		if text[1].startswith("(ancora ") is True:
			text[1] = text[1][len("(ancora ") : text.index(" punti pietra)")]
		else:
			text[1] = 0

		user = message.from_user
	elif ((message.forward_from is not None and message.forward_from.id == config.get("loot_plus_bot")) or message.from_user.id == config.get("loot_plus_bot")) and "Proprietario" in message.text:
		text = message.text.splitlines()

		# Extracting the proprietary of the Dragon
		user = list(filter(lambda n: n.startswith("Proprietario: ") is True, text))
		user = user[len("Proprietario: ") :]
		user = user[:user.index(" ")]
		user = await client.get_users(user)

		# Extracting the level of the Dragon
		text = text.pop(0)
		text = text[text.index("(") + len("(L") : text.index(")")]
		text = [int(text), -1]
	else:
		return

	# Checking if the user is an authorized user
	if user.id not in players_allowed_list:
		return

	with connection.cursor() as cursor:
		# Retrieving the user's data
		if cursor.execute("SELECT * FROM `Nest` WHERE `id`=%(id)s;", {
			"id": user.id,
		}) == 0:
			return

		user = cursor.fetchone()

		for i in user.keys():
			user[i] = int(user[i])

		# Updating the database
		user["level"] = text[0]

		# Checking if the Dragon has reached the level he was aiming for
		if user["objective"] == user["level"]:
			user["objective"] = 300

			await client.send_message(user.id, "Your Dragon has reached the level he was aiming for.")

		user["missing_points"] = (user["objective"] - user["level"]) * 70

		if text[1] != -1:
			user["missing_points"] = user["missing_points"] + text[1] - 70

		cursor.execute("UPDATE `Nest` SET `level`=%(level)s, `missing_points`=%(missing_points)s, `objective`=%(objective)s WHERE `id`=%(id)s;", user)
	connection.commit()

	logger.info("I updated the Nest table ({}).".format(user["id"]))


@app.on_message(Filters.command("backpack", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def backpack(client: Client, message: Message):
	# /backpack
	global config, connection

	text = "Your backpack contains:"

	with connection.cursor() as cursor:
		# Retrieving the user's backpack
		if cursor.execute("SELECT * FROM `Backpacks` WHERE `id`=%(id)s;", {
			"id": message.from_user.id,
		}) == 0:
			await res.split_reply_text(config, message, "Your backpack is empty.", quote=False)
			logger.info("I\'ve answered to /backpack because of @{}.".format(message.from_user.username))
			return

		backpack = list(map(lambda n: {
			"id": n["item_id"],
			"quantity": n["quantity"]
		}, cursor.fetchall()))

		for i in backpack:
			for j in i.keys():
				i[j] = int(i[j])

		# Retrieving the items' details
		cursor.executemany("SELECT `name`, `rarity`, `craftable` FROM `Items` WHERE `id`=%(id)s;", list(map(lambda n: {
			"id": n["id"]
		}, backpack)))
		items_list = cursor.fetchall().copy()

		for i in items_list:
			i["craftable"] = bool(i["craftable"])

		for i in range(len(backpack)):
			backpack[i].update(items_list[i])

		# Sorting the backpack by rarity
		backpack = sorted(backpack, key=lambda n: functools.cmp_to_key(res.order_by_rarty))

		# Formatting the backpack
		backpack = list(map(lambda n: {
			"text": "> {} ({})".format("<b>{}</b>".format(n["name"]) if n["craftable"] is False else n["name"], n["quantity"]),
			"rarity": n["rarity"]
		} , backpack))

		rarity = backpack[0]["rarity"]
		text += "<i>{}:</i>\n".format(rarity)

		for i in backpack:
			if rarity != i["rarity"]:
				rarity = i["rarity"]
				text += "\n<i>{}:</i>\n".format(rarity)
			text += "{}\n".format(i["text"])

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /backpack because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command(["ban", "banall", "unban", "kick"], prefixes="/") & Filters.user(admins_list) & Filters.chat(chats_list))
async def ban_hammer(client: Client, message: Message):
	# /ban
	# /banall
	# /unban <username>
	# /kick
	global chats_list, config

	command = message.command.pop(0)

	# Checking if the admin can ban or unban the members of the chat
	with connection.cursor() as cursor:
		if message.from_user is not None and cursor.execute("SELECT NULL FROM `Players` WHERE `id`=%(id)s AND (`domain`=\'creator\' OR `domain`==\'princeps\');", {
			"id": message.from_user.id
		}) == 0:
			await res.split_reply_text(config, message, "You can\'t use this command.", quote=False)
			logger.info("{} have sent an incorrect /{} request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id, command))
			return
	user = await message.chat.get_member(message.from_user.id)
	if user.can_restrict_members is False:
		await message.delete(revoke=True)
		return


	# Checking if the command is correct
	if command == "unban" and message.command is False:
		await res.split_reply_text(config, message, "The syntax is: <code>/unban &lt;username&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /unban request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return
	elif message.reply_to_message is None:
		logger.info("{} have sent an incorrect /{} request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id, command))
		return

	# Executing the command
	if command == "unban":
		user = await client.get_users(message.command.pop(0))

		for i in chats_list:
			await client.unban_chat_member(i, user.id)
	else:
		user = message.reply_to_message.from_user
		limits = 0

		if command == "kick":
			limits = 31

		await message.chat.kick_member(user.id, until_date=limits)

		# Checking if the player must be banned from all chats
		if command == "banall":
			# Removing the data of the player from the database
			with connection.cursor() as cursor:
				cursor.execute("DELETE FROM `Players` WHERE `id`=%(id)s;", {
					"id": user.id
				})
				cursor.execute("DELETE FROM `Statistics` WHERE `id`=%(id)s;", {
					"id": user.id
				})
				cursor.execute("DELETE FROM `Nest_transaction` WHERE `donor_id`=%(id)s OR `receiver_id`=%(id)s;", {
					"id": user.id
				})
				cursor.execute("DELETE FROM `Crafts` WHERE `user_id`=%(user_id)s;", {
					"user_id": user.id
				})
				cursor.execute("DELETE FROM `Backpacks` WHERE `user_id`=%(user_id)s;", {
					"user_id": user.id
				})
				cursor.execute("DELETE FROM `Smuggler` WHERE `id`=%(id)s;", {
					"id": user.id
				})
				cursor.execute("DELETE FROM `Nest` WHERE `id`=%(id)s;", {
					"id": user.id
				})
			connection.commit()

			for i in chats_list:
				if i == message.chat.id:
					continue

				await client.kick_chat_member(i, user.id)

	await res.split_reply_text(config, message, "I have {}ed @{}{}.".format(" {}n".format(command[: command.rindex("n")]) if command != "kick" else command, user.username, "from all chats" if command == "banall" else ""), quote=False)
	logger.info("I\'ve answered to /{} because of @{}.".format(command, message.from_user.username))


@app.on_message(Filters.command("board", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def board(_, message: Message):
	# /board
	global config, connection

	text = res.print_board(connection)

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /board because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("check", prefixes="/") & Filters.user(config.get("creator")))
async def check_database(_, message: Message):
	global admins_list, connection, chats_list

	with connection.cursor() as cursor:
		cursor.execute("SELECT * FROM `Players`;")
		print("{}\n".format(cursor.fetchall()))
	print("{}\n".format(list(map(lambda n: "\t{} - {}\n".format(n, type(n)), admins_list))))

	with connection.cursor() as cursor:
		cursor.execute("SELECT * FROM `Chats`;")
		print("{}\n".format(cursor.fetchall()))
	print("{}\n".format(list(map(lambda n: "\t{} - {}\n".format(n, type(n)), chats_list))))

	with connection.cursor() as cursor:
		cursor.execute("SELECT * FROM `Items`;")
		print("{}\n".format(cursor.fetchall()))

		cursor.execute("SELECT * FROM `Backpacks`;")
		print("{}\n".format(cursor.fetchall()))

		cursor.execute("SELECT * FROM `Smuggler`;")
		print("{}\n".format(cursor.fetchall()))

		cursor.execute("SELECT * FROM `Nest`;")
		print("{}\n".format(cursor.fetchall()))

		cursor.execute("SELECT * FROM `Statistics`;")
		print("{}\n".format(cursor.fetchall()))

		cursor.execute("SELECT * FROM `Nest_transaction`;")
		print("{}\n".format(cursor.fetchall()))

		cursor.execute("SELECT * FROM `Crafts`;")
		print("{}\n".format(cursor.fetchall()))

		cursor.execute("SELECT * FROM `Recipes`;")
		print("{}\n".format(cursor.fetchall()))

	print("\n\n")
	logger.info("I\'ve answered to /check because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command(["craft", "craftb"], prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def craft(_, message: Message):
	# /craft <item>:<quantity>[, <item>:<quantity>[, ...]]
	# /craftb <item>:<quantity>[, <item>:<quantity>[, ...]]
	global config, connection

	command = message.command.pop(0)
	problems = "There are the following problems:"
	use_craft = True

	# Checking if the command is correct
	if message.command is False:
		await res.split_reply_text(config, message, "The syntax is: <code>/{} &lt;item&gt;:&lt;quantity&gt;[, &lt;item&gt;:&lt;quantity&gt;[, ...]]</code>.".format(command), quote=False)
		logger.info("{} have sent an incorrect /{} request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id, command))
		return

	# Checking what kind of craft the players want do
	if command == "craftb":
		use_craft = False

	# Retrieving the craft's list
	request = " ".join(message.command)
	request = request.split(",")

	request = list(map(lambda n: n.strip(), request))

	with connection.cursor() as cursor:
		for i in range(len(request)):
			request[i] = request[i].split(":")

			# Retrieving the item's id and name and checking if it respect the requisites
			if cursor.execute("SELECT `id`, `name` FROM `Items` WHERE `name` COLLATE utf8_general_ci LIKE \'%(name)s\';", {
				"name": request[i][0]
			}) != 1:
				problems += "\n\tThe item <b>{}</b> doesn\'t exists".format(request[i][0])
				continue

			item = cursor.fetchone()
			item["id"] = int(item["id"])

			# Checking if the command is correct
			try:
				item["quantity"] = int(request[i][1])
			except ValueError:
				problems += "\n\tThe quantity of the item <b>{}</b> must be an integer".format(item["name"])
				continue

			# Updating the request
			request[i] = item

	if problems != "There are the following problems:":
		problems += "\nOnly for these item, you must resend the request."

	request = res.craft_inner(message.from_user.id, request, connection, use_craft)
	"""
		request = {
					"commands": [
						"",
						...
					],
					"text": ""
				}
	"""

	problems += "\n\n{}".format(request.pop("text"))

	await res.split_reply_text(config, message, problems, quote=False)
	await res.split_reply_text(config, message, "<code>{}</code>".format("</code>\n<code>".join(request.pop("commands"))), quote=False)
	logger.info("I\'ve answered to /{} because of @{}.".format(message.from_user.username, command))


@app.on_message(Filters.user(players_allowed_list) & Filters.chat(chats_list) & Filters.regex("^(\@exarch)\s+(\S+.*)$", re.IGNORECASE | re.UNICODE | re.MULTILINE))
async def exarch(client: Client, message: Message):
	global config, connection

	# Retrieving the exarches
	with connection.cursor() as cursor:
		cursor.execute("SELECT `id`, `username` FROM `Players` WHERE `domain`!=\'all\';")
		exarches = cursor.fetchall()

		for i in exarches:
			i["id"] = int(i["id"])

	text = "\n@{} needs your help".format(message.from_user.username)

	# Retrieving the eventual message for the exarch
	match = message.matches.pop(0)
	if match.group(2) != "":
		text += " for {}".format(match.group(2))
	text += "."

	# Tagging the exarches
	await res.split_reply_text(config, message.reply_to_message, " ".join(list(map(lambda n: "@{}".format(i["username"]), exarches))), quote=True)
	await message.delete(revoke=True)

	for i in exarches:
		await client.send_message(i["id"], "@{}{}".format(i["username"], text))

	logger.info("I sent @{}\'s request to the competent exarch.".format(message.from_user.username))


@app.on_message(Filters.user(players_allowed_list) & Filters.private & Filters.forwarded & Filters.text)
async def forwarded_messages(_, message: Message):
	global admins_list, backpack_update, config, connection, statistics

	# Checking if the message is forwarded form the correct user
	if message.forward_from.id == config.get("loot_bot"):
		# Checking if the message have the correct syntax
		if message.text.startswith("Puoi migliorare la postazione") is True:
			# Retrieving the items list
			text = message.text.splitlines()
			text = list(filter(lambda n: n.startswith("> ") is True, text))

			text = list(map(lambda n: n[len("> ") :], text))

			for i in text:
				i = i.split(" ")
				i.pop(len(i) - 1)

				# Retrieving the quantity of the item
				quantity = i.pop(len(i) - 1)
				quantity = quantity.split("/")
				quantity = list(map(lambda n: int(n), quantity))

				formalQuantity = quantity[1]
				quantity = quantity[1] - quantity[0]

				if quantity <= 0:
					quantity = formalQuantity

				# Retrieving the item's id
				i.pop(len(i) - 1)
				name = " ".join(i)

				with connection.cursor() as cursor:
					cursor.execute("SELECT `id` FROM `Items` WHERE `name`=%(name)s;", {
						"name": name
					})
					item_id = int(cursor.fetchone()["id"])

				# Adding the item to the request
				i = "{}:{}:{}".format(item_id, name, quantity)

			keyboard = [
				[
					InlineKeyboardButton(text="Craft all", callback_data="Assault!All!{}".format(",".join(text)))
				],
				[
					InlineKeyboardButton(text="Craft only the missing", callback_data="Assault!Missing!{}".format(",".join(text)))
				]
			]
			keyboard = InlineKeyboardMarkup(keyboard)

			await res.split_reply_text(config, message, "How do you want craft the items ?", quote=False, reply_markup=keyboard)
			logger.info("I answer to @{} for an Assault craft request.".format(message.from_user.username))
		else:
			# Retrieving the items list
			text = message.text.splitlines()

			# Checking if the message is a backpack message
			if list(filter(lambda n: n.startswith("> ") is True, text)) is True:
				text = list(filter(lambda n: n.startswith("> ") is True, text))

				# Retrieving the time period from the last update
				period = backpack_update["threshold"] + 1

				if backpack_update["time"] is not None:
					period = backpack_update["time"] - message.date

				period = period.time()
				period = period.second + period.minute * 60 + period.hour * 60 * 60

				for i in text:
					# Retrieving the item's id
					with connection.cursor() as cursor:
						cursor.execute("SELECT `id` FROM `Items` WHERE `name`=%(name)s;", {
							"name": i[len("> ") : i.index("(") - len(" ")]
						})
						item = cursor.fetchone()
					item["id"] = int(item["id"])

					# Retrieving the quantity of the item
					quantity = i[i.index("(") + len("(") : i.index(")")]
					quantity = quantity.replace(".", "")
					quantity = int(quantity)

					item["quantity"] = quantity

					i = item

				# Updating the database
				if period > backpack_update["threshold"]:
					with connection.cursor() as cursor:
						cursor.execute("DELETE FROM `Backpacks` WHERE `user_id`=%(user_id)s;", {
							"user_id": message.from_user.id
						})
					connection.commit()

					await res.split_reply_text(config, message, "Reset backpack.", quote=False)

				# Saving the time of the update
				backpack_update["time"] = message.date

				with connection.cursor() as cursor:
					for i in text:
						item_id = i.pop("id")

						i.update({
							"user_id": message.from_user.id,
							"item_id": item_id
						})

						if cursor.execute("UPDATE FROM `Backpacks` SET `quantity`=%(quantity)s WHERE `user_id`=%(user_id)s AND `item_id`=%(item_id)s;", i) == 0:
							cursor.execute("INSERT INTO `Backpacks` (`user_id`, `item_id`, `quantity`) VALUES (%(user_id)s, %(item_id)s, %(quantity)s);", i)
				connection.commit()

				await res.split_reply_text(config, message, "Backpack saved.", quote=False)

				logger.info("I saved the backpack of @{}.".format(message.from_user.username))
			else:
				# Checking if the message have the correct syntax
				if text[0] != "Membri nel team:" and text[0][0] != Emoji.BUST_IN_SILHOUETTE:
					return

				tmp = {
					"id": 0,
					"experience": 0,
					"rank": 0,
					"craft_points": 0,
					"dragon": 0,
					"ability": 0,
					"weekly_craft_points": 0
				}

				for i in text:
					if i == "":
						with connection.cursor() as cursor:
							# Checking if is the 1st of the month
							if datetime.date.today().day == 1:
								# Removing the inutil informations
								weekly_craft_points = tmp.pop("weekly_craft_points")

								# Retrieving the player's statistics
								if cursor.execute("SELECT `ability`, `craft_points`, `dragon`, `experience`, `rank` FROM `Statistics` WHERE `id`=%(id)s;", {
									"id": tmp["id"]
								}) != 0:
									player = cursor.fetchone()

									for i in player.keys():
										player[i] = int(player[i])

									# Updating the maximum statistics
									if tmp["ability"] - player["ability"] > statistics["ability"]["quantity"]:
										statistics["ability"]["quantity"] = tmp["ability"] - player["ability"]
										statistics["ability"]["id"] = tmp["id"]

									if tmp["craft_points"] - player["craft_points"] > statistics["craft_points"]["quantity"]:
										statistics["craft_points"]["quantity"] = tmp["craft_points"] - player["craft_points"]
										statistics["craft_points"]["id"] = tmp["id"]

									if tmp["dragon"] - player["dragon"] > statistics["dragon"]["quantity"]:
										statistics["dragon"]["quantity"] = tmp["dragon"] - player["dragon"]
										statistics["dragon"]["id"] = tmp["id"]

									if tmp["experience"] - player["experience"] > statistics["experience"]["quantity"]:
										statistics["experience"]["quantity"] = tmp["experience"] - player["experience"]
										statistics["experience"]["id"] = tmp["id"]

									if tmp["rank"] - player["rank"] > statistics["rank"]["quantity"]:
										statistics["rank"]["quantity"] = tmp["rank"] - player["rank"]
										statistics["rank"]["id"] = tmp["id"]

									# Updating the database
									cursor.execute("UPDATE FROM `Statistics` SET  `ability`=%(ability)s, `craft_points`=%(craft_points)s, `dragon`=%(dragon)s, `experience`=%(experience)s, `rank`=%(rank)s WHERE `id`=%(id)s;", tmp)
								else:
									tmp.update({
										"weekly_craft_points": 0
									})

									cursor.execute("INSERT INTO `Statistics` (`id`, `ability`,`craft_points`, `dragon`, `experience`, `rank`, `weekly_craft_points`) VALUES (%(id)s, %(ability)s,%(craft_points)s, %(dragon)s, %(experience)s, %(rank)s, %(weekly_craft_points)s);", tmp)

									tmp.update({
										"weekly_craft_points": weekly_craft_points
									})

							# Checking if is monday
							if datetime.date.weekday() == 0:
								if cursor.execute("SELECT `weekly_craft_points` FROM `Statistics` WHERE `id`=%(id)s;", {
									"id": tmp["id"]
								}) != 0:
									weekly_craft_points = int(cursor.fetchone()["weekly_craft_points"])

									# Updating the maximum statistics
									if tmp["weekly_craft_points"] - weekly_craft_points > statistics["weekly_craft_points"]["quantity"]:
										statistics["weekly_craft_points"]["quantity"] = tmp["weekly_craft_points"] - weekly_craft_points
										statistics["weekly_craft_points"]["id"] = tmp["id"]

									# Updating the database
									cursor.execute("UPDATE FROM `Statistics` SET `weekly_craft_points`=%(weekly_craft_points)s WHERE `id`=%(id)s;", {
										"weekly_craft_points": tmp["weekly_craft_points"],
										"id": tmp["id"]
									})
								else:
									tmp.update({
										"experience": 0,
										"rank": 0,
										"craft_points": 0,
										"dragon": 0,
										"ability": 0
									})
									cursor.execute("INSERT INTO `Statistics` (`id`, `ability`,`craft_points`, `dragon`, `experience`, `rank`, `weekly_craft_points`) VALUES (%(id)s, %(ability)s,%(craft_points)s, %(dragon)s, %(experience)s, %(rank)s, %(weekly_craft_points)s);", tmp)
						connection.commit()

						# Resetting the statistics
						tmp.update({
							"id": 0,
							"experience": 0,
							"rank": 0,
							"craft_points": 0,
							"dragon": 0,
							"ability": 0,
							"weekly_craft_points": 0
						})
					elif i[0] == Emoji.SHIELD:
						# Retrieving the player's rank
						i = i[i.index(",") + len(", ") :]
						i = i[: i.index(" ")]

						# Saving the partial result
						tmp["rank"] = int(i)
					elif i[0] == Emoji.PACKAGE:
						# Retrieving the player's craft points
						i = i.split(",")
						i = list(map(lambda n: n.strip(), i))
						i[0] = i[0][i[0].index(" ") + len(" ") :]
						i[0] = i[0][: i[0].index(" ")]
						i[1] = i[1][: i[1].index(" ")]
						i = list(map(lambda n: res.price_str_to_int(n), i))

						# Saving the partial result
						tmp["craft_points"] = i[0]
						tmp["weekly_craft_points"] = i[1]
					elif i[0] == Emoji.FLASHLIGHT:
						# Retrieving the player's ability
						i = i[i.index(" ") + len(" ") :]
						i = i[: i.index(" ")]

						# Saving the partial result
						tmp["ability"] = int(i)
					elif i[0] == Emoji.DRAGON:
						# Retrieving the player's Dragon's level
						i = i[i.index("(") + len("(Lv ") :]
						i = i[: i.index(")")]

						# Saving the partial result
						tmp["dragon"] = int(i)
					elif i[0] == Emoji.RED_HEART:
						# Retrieving the player's experience
						i = i[i.index("/") + len("/") :]
						i = i[: i.index(" ")]

						# Saving the partial result
						tmp["experience"] = int(i)
					elif i[0] == Emoji.BUST_IN_SILHOUETTE or i[0] == Emoji.CROWN or i[0] == Emoji.JAPANESE_SYMBOL_FOR_BEGINNER:
						# Retrieving the player's username
						i = i[i.index(" ") + len(" ") :]
						i = i[: i.index(" ")]

						# Retrieving the player's data
						i = await client.get_users(i)

						# Saving the partial result
						tmp["id"] = i.id
	elif message.forward_from.id == config.get("loot_plus_bot"):
		# Checking if the message have the correct syntax
		if "Token attuale:" in message.text and message.from_user.id == config.get("creator"):
			# Retrieving the API token
			text = message.text.splitlines()
			text = list(filter(lambda n: n.startswith("Token attuale: ") is True, text))
			text = text.pop(0)
			text = text[len("Token attuale: ") :]

			# Changing the API token
			config.set("loot_bot_API_token", text)

			with connection.cursor() as cursor:
				cursor.execute("UPDATE `info` SET `value`=%(value)s WHERE `key`=%(key)s;", {
					"value": text,
					"key": "loot_bot_API_token"
				})
			connection.commit()

			await res.split_reply_text(config, message, "Token changed.", quote=False)
			logger.info("I have change the Loot Bot API token.")


@app.on_message(Filters.command("globalundertaking", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def global_undertaking(_, message: Message):
	# /globalundertaking
	global config

	# Downloading of the data on the Global Undertaking
	response = requests.get(url="https://fenixweb.net:6600/api/v2/{}/info".format(config.get("loot_api_token")))

	# Checking of the download is done
	response.raise_for_status()

	# Retrieving the  data on the Global Undertaking
	result = result["res"].pop(0)

	# Checking if the Global Undertaking is active
	if result["global_on"] is False:
		text = "The Global Undertaking isn\'t active."
	else:
		text = "<b>Global Undertaking:</b>\n<i>Cap:</i> {}\n<i>Progress:</i> {}{}\n<i>Threshold:</i> {}".format(result["global_cap"] if result["global_cap_hide"] is False else "Unknown", result["global_tot"], " ({:.2%})".format(result["global_tot"] / result["global_cap"]) if result["global_cap_hide"] is False else "", result["global_limit"] if result["global_limit"] is True else "Unknown")

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /globalundertaking because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("groups", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def groups(_, message: Message):
	# /groups
	global config, connection

	# Retrieving the team chats
	with connection.cursor() as cursor:
		cursor.execute("SELECT `id`, `title`, `username`, `invite_link` FROM `Chats` WHERE `type_into_guild`=\'team\';")
		chat = cursor.fetchall().copy()

	chat = sorted(chat, key=lambda n: n["title"])

	# Restructuring the InlineKeyboard
	for i in chat:
		button = await res.chat_button(client, i, connection)

		keyboard.append([
			button
		])

	keyboard.append([
		InlineKeyboardButton(text="", callback_data=""),
		InlineKeyboardButton(text="Next", callback_data="Utility")
	])
	keyboard = InlineKeyboardMarkup(keyboard)

	await res.split_reply_text(config, message, "The groups of the Dragon Guild are:", quote=False, reply_markup=keyboard)
	logger.info("I\'ve answered to /groups because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("help", prefixes="/") & Filters.private)
async def help(_, message: Message):
	# /help
	global admins_list, config

	commands = config.get("commands")

	# Filter the commands list in base at their domain
	if message.from_user.id != config.get("creator"):
		commands = list(filter(lambda n: n["domain"] != "creator", commands))
	if message.from_user.id not in admins_list:
		commands = list(filter(lambda n: n["domain"] != "exarch", commands))

	await res.split_reply_text(config, message, "In this section you will find the list of the command of the bot.\n\t{}".format("\n\t".join(list(map(lambda n: "<code>/{}{}</code> - {}".format(n["name"], " {}".format(n["parameters"]) if n["parameters"] != "" else n["parameters"], n["description"])), commands))), quote=False)

	logger.info("I\'ve answered to /help because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("init", prefixes="/") & Filters.user(admins_list) & Filters.private)
async def initializing(client: Client, _):
	# /init
	global config, connection, nest_chat, nest_pinned_message, players_allowed_list, scheduler, statistics

	players_allowed_list = list()

	# Scheduling the functions
	scheduler.add_job(res.edit_board, IntervalTrigger(hours=1, timezone="Europe/Rome"), kwargs={
		"config": config,
		"nest_pinned_message": nest_pinned_message
	})
	scheduler.add_job(res.post_statistics, CronTrigger(day=1, hour=13, minute=30, timezone="Europe/Rome"), kwargs={
		"client": client,
		"config": config,
		"connection": connection,
		"statistics": statistics
	})
	scheduler.add_job(res.post_statistics, CronTrigger(day_of_week=0, hour=13, minute=30, timezone="Europe/Rome"), kwargs={
		"client": client,
		"config": config,
		"connection": connection,
		"statistics": statistics
	})
	scheduler.add_job(res.remind_statistics, CronTrigger(day=1, hour=13, minute=0, timezone="Europe/Rome"), kwargs={
		"client": client,
		"connection": connection
	})
	scheduler.add_job(res.remind_statistics, CronTrigger(day_of_week=0, hour=13, minute=0, timezone="Europe/Rome"), kwargs={
		"client": client,
		"connection": connection
	})
	scheduler.add_job(res.update_items_queue, IntervalTrigger(weeks=2, timezone="Europe/Rome"), kwargs={
		"config": config,
		"connection": connection
	})
	scheduler.add_job(res.update_players_queue, IntervalTrigger(days=1, timezone="Europe/Rome"), kwargs={
		"config": config,
		"connection": connection,
		"players_allowed_list": players_allowed_list
	})
	scheduler.add_job(res.update_recipes_queue, IntervalTrigger(weeks=2, timezone="Europe/Rome"), kwargs={
		"config": config,
		"connection": connection
	})

	# Pinning the Nest's board
	if nest_pinned_message is None:
		nest_pinned_message = await client.send_message(nest_chat, res.print_board(connection))
		await nest_pinned_message.pin(disable_notification=True)

	# Setting the maximum message length
	max_length = await client.send(functions.help.GetConfig())
	config.set("message_max_length", max_length.message_length_max)

	# Retrieving the bot id
	bot = await client.get_users(config.get("bot_username"))
	config.set("bot_id", bot.id)

	# Downloading, for the first time, the Recipes' data
	await update_recipes_queue()

	logger.info("I\'ve answered to /init because of @{}.".format(message.from_user.username))


@app.on_inline_query(Filters.user(players_allowed_list) & (Filters.chat(chats_list) | Filters.private))
async def inline_mode(_, inline_query: InlineQuery):
	keywords = [
		"Artifacts",
		"Assault",
		"Assignments",
		"Crafting",
		"Dragon",
		"Dungeon",
		"Enchantments",
		"Equipment",
		"Mana",
		"Peaks",
		"Rebirth",
		"Refuge",
		"Soul Points",
		"Talents",
		"Talismans",
		"Vocations"
	]
	query = inline_query.query.lower()
	response = list()

	# Checking if the query is for a guide
	if query in list(map(lambda n: n.lower(), keywords)):
		telegraph = Telegraph()

		# Checking what kind of query is and downloading its Telegra.ph's page
		if "artifacts" in query:
			response.append(telegraph.get_page("Guida-agli-Artefatti-05-06", return_content=True, return_html=True))
		if "assault" in query:
			response.append(telegraph.get_page("Guida-allAssalto-05-06", return_content=True, return_html=True))
		if "assignments" in query:
			response.append(telegraph.get_page("Guida-agli-Incarichi-05-10", return_content=True, return_html=True))
		if "crafting" in query:
			response.append(telegraph.get_page("Guida-al-Crafting-05-11", return_content=True, return_html=True))
		if "dragon" in query:
			response.append(telegraph.get_page("Guida-al-Drago-05-06", return_content=True, return_html=True))
		if "dungeon" in query:
			response.append(telegraph.get_page("Guida-ai-Dungeon-05-06-2", return_content=True, return_html=True))
		if "enchantments" in query:
			response.append(telegraph.get_page("Guida-agli-Incantamenti-05-30", return_content=True, return_html=True))
		if "equipment" in query:
			response.append(telegraph.get_page("Guida-allEquipaggiamento-05-06-2", return_content=True, return_html=True))
		if "mana" in query:
			response.append(telegraph.get_page("Guida-al-Mana-05-06-2", return_content=True, return_html=True))
		if "peaks" in query:
			response.append(telegraph.get_page("Guida-alle-Vette-05-18", return_content=True, return_html=True))
		if "rebirth" in query:
			response.append(telegraph.get_page("Guida-alla-Rinascita-05-06", return_content=True, return_html=True))
		if "refuge" in query:
			response.append(telegraph.get_page("Guida-al-Rifugio-05-11", return_content=True, return_html=True))
		if "soul points" in query:
			response.append(telegraph.get_page("Guida-ai-Punti-Anima-05-11", return_content=True, return_html=True))
		if "talents" in query:
			response.append(telegraph.get_page("Guida-ai-Talenti-05-06", return_content=True, return_html=True))
		if "talismans" in query:
			response.append(telegraph.get_page("Guida-ai-Talismani-05-06", return_content=True, return_html=True))
		if "vocations" in query:
			response.append(telegraph.get_page("Guida-alle-Vocazioni-05-06", return_content=True, return_html=True))

		response = list(map(lambda n: InlineQueryResultArticle(title=n["title"], input_message_content=InputTextMessageContent("This is the guide that you have searched:\n\t<a href=\"{}\">{}</a>\n{}".format(n["url"], n["title"], n["description"]), parse_mode="html", disable_web_page_preview=True), url=n["url"], description=n["description"]), response))
	else:
		response.append(InlineQueryResultArticle(title="Unknown", input_message_content=InputTextMessageContent("List of word to use as keyword in the Inline Mode:\n\t<code>{}</code>".format("</code>\n\t<code>".join(keywords)), parse_mode="html")))

	await inline_query.answer(response, cache_time=1)
	logger.info("I sent the answer to the Inline Query of @{}.".format(inline_query.from_user.username))


@app.on_message(Filters.command("lendnest", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def lend_nest(client: Client, message: Message):
	# /lendnest <points> to <username>
	global config, nest_chat, players_allowed_list

	message.command.pop(0)

	# Checking if the command is correct
	if len(message.command) != 3:
		await res.split_reply_text(config, message, "The syntax is: <code>/lendnest &lt;points&gt; to &lt;username&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /lendnest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	try:
		index = message.command.index("to")
	except ValueError:
		await res.split_reply_text(config, message, "The syntax is: <code>/lendnest &lt;points&gt; to &lt;username&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /lendnest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the points to lends
	try:
		points = int(message.command[index - 1])
	except ValueError:
		await res.split_reply_text(config, message, "The syntax is: <code>/lendnest &lt;points&gt; to &lt;username&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /lendnest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the user's data
	user = await client.get_users(message.command[index + 1])

	# Checking if the user is authorized
	if user.id not in players_allowed_list:
		await res.split_reply_text(config, message, "You can lend Dragon's stones only to teammates.", quote=False)
		logger.info("{} have sent an incorrect /lendnest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Adding the loan to the database
	with connection.cursor() as cursor:
		if cursor.execute("SELECT `quantity` FROM `Nest_transaction` WHERE `donor_id`=%(donor_id)s AND `receiver_id`=%(receiver_id)s;", {
		"donor_id": message.from_user.id,
		"receiver_id": user.id
		}) == 0:
			# Adding to the database
			cursor.execute("INSERT INTO `Nest_transaction` (`donor_id`, `receiver_id`, `quantity`) VALUES (%(donor_id)s, %(receiver_id)s, %(quantity)s);", {
				"quantity": quantity,
				"donor_id": message.from_user.id,
				"receiver_id": user.id
			})
		else:
			quantity = int(cursor.fetchone()["quantity"]) + points

			# Updating the database
			cursor.execute("UPDATE FROM `Nest_transaction` SET `quantity`=%(quantity)s WHERE `donor_id`=%(donor_id)s AND `receiver_id`=%(receiver_id)s;", {
				"quantity": quantity,
				"donor_id": message.from_user.id,
				"receiver_id": user.id
			})
	connection.commit()

	await res.split_reply_text(config, message, "I\'ve registered the lend.", quote=False)
	await client.send_message(nest_chat, "@{} lends {} points to @{}".format(message.from_user.username, points, user.username))
	logger.info("I have answered to /lendnest from @{}.".format(message.from_user.username))


@app.on_message(Filters.command("link", prefixes="/") & Filters.group & Filters.chat(chats_list))
async def link(client: Client, message: Message):
	# /link
	global config

	text = "@{} is the link to this chat.".format(message.chat.username) if message.chat.username is not None else ""

	if message.chat.username is None:
		chat = client.get_chat(message.chat.id)

		text = "This is the <a href=\"{}\">link</a> to this chat.".format(chat.invite_link)

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /link because of @{}.".format(message.from_user.username))


@app.on_message(Filters.user(players_allowed_list) & Filters.chat(makers_chat) & Filters.forwarded)
async def makers(_, message: Message):
	global config, connection

	# Checking if the original user is Loot Bot
	if message.forward_from.id != config.get("loot_bot"):
		return

	# Checking if the message have the correct syntax
	if message.text is None or message.text.startswith("Benvenuto {}!".format(message.from_user.username)) is False:
		return

	# Retrieving the item and the Smuggler's offert
	text = message.text.splitlines()
	text = list(filter(lambda n: "(" in n, text))
	text = text.pop(0)
	item = text[: text.index("(") - len(" ")]
	price = text[text.index(")") + len(" al prezzo di ") : text.index("§") - len(" ")]

	# Retrieving the item's id, name and craft points
	with connection.cursor() as cursor:
		cursor.execute("SELECT `id`, `name`, `craft_pnt` FROM `Items` WHERE `name` COLLATE utf8_general_ci LIKE \'%%(name)s%\';", {
			"name": item
		})
		item = cursor.fetchone()
		item["id"] = int(item["id"])
		item["craft_pnt"] = int(item["craft_pnt"])

	text = "{} @{}\n{} {}\n{} {} PC\n{} {} §".format(Emoji.BUST_IN_SILHOUETTE, message.from_user.username, Emoji.HAMMER_AND_PICK, item["name"], Emoji.PACKAGE, item["craft_pnt"], Emoji.MONEY_BAG, price)

	keyboard = [
		[
			InlineKeyboardButton("Booked", callback_data="Booked!{}".format(message.from_user.id))
		],
		[
			InlineKeyboardButton("Free", callback_data="Free!{}".format(message.from_user.id))
		],
		[
			InlineKeyboardButton("Private", callback_data="Private!{}".format(message.from_user.id))
		],
		[
			InlineKeyboardButton("Close", callback_data="Close!{}".format(message.from_user.id))
		]
	]
	keyboard = InlineKeyboardMarkup(keyboard)

	# Adding the Smuggler's offert at the database
	with connection.cursor() as cursor:
		cursor.execute("INSERT INTO `Smuggler` (`id`, `booked_from`, `free`, `private`) VALUES (%(id)s, %(booked_from)s, %(free)s, %(private)s);", {
			"id": message.from_user.id,
			"booked_from": None,
			"free": 0,
			"private": 0
		})
	connection.commit()

	username = message.from_user.username

	await res.split_reply_text(config, message, text, quote=False, reply_markup=keyboard)
	await message.delete(revoke=True)

	logger.info("I send the craft of the Smuggler of @{}.".format(username))


@app.on_message(Filters.command(["mute", "silence", "unmute", "unsilence"], prefixes="/") & Filters.user(admins_list) & Filters.group & Filters.chat(chats_list))
async def mute_hammer(client: Client, message: Message):
	# /mute [time]
	# /silence
	# /unmute
	# /unsilence
	global admins_list, config, connection

	command = message.command.pop(0)

	# Checking if the command is correct
	if "mute" in command and message.reply_to_message is None:
		logger.info("{} have sent an incorrect /{} request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id, command))
		return

	permission = message.chat.permissions

	# Checking if the command is /mute or /silence
	if "un" not in command:
		permission = ChatPermission(can_send_messages=False, can_send_media_messages=False, can_send_stickers=False, can_send_animations=False, can_send_games=False, can_use_inline_bots=False, can_add_web_page_previews=False, can_send_polls=False, can_change_info=False, can_pin_messages=False)

	# Executing the command
	if "mute" in command:
		user = message.reply_to_message.from_user

		if user.id in admins_list:
			return

		limits = 0

		if command == "mute" and message.command is True:
			limits = message.command.pop(0)

		await message.chat.restrict_member(user.id, permissions, until_date=limits)
	else:
		for i in message.chat.iter_members():
			if i.user.id in admins_list:
				continue

			await message.chat.restrict_member(i.user.id, permission)

	await res.split_reply_text(config, message, "I have {}d {}.".format(command, "@{}".format(user.username) if "mute" in command else "all the users in the chat"), quote=False)
	logger.info("I\'ve answered to /{} because of @{}.".format(command, message.from_user.username))


@app.on_message(Filters.command("remove", prefixes="/") & (Filters.user(admins_list) | Filters.channel))
async def remove_from_the_database(client: Client, message: Message):
	# /remove
	global admins_list, chats_list, config

	# Checking if the message arrive from a channel and, if not, checking if the user that runs the command is allowed
	with connection.cursor() as cursor:
		if message.from_user is not None and cursor.execute("SELECT NULL FROM `Players` WHERE `id`=%(id)s AND (`domain`=\'creator\' OR `domain`==\'princeps\');", {
			"id": message.from_user.id
		}) == 0:
			await res.split_reply_text(config, message, "You can\'t use this command.", quote=False)
			logger.info("{} have sent an incorrect /remove request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
			return

	# Checking if the data are of a chat or of a user
	if message.reply_to_message is not None:
		# Checking if the user is authorized
		if message.reply_to_message.from_user.id not in admins_list:
			await res.split_reply_text(config, message, "You can\'t remove an admin that doesn't exists.", quote=False)
			logger.info("{} have sent an incorrect /remove request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
			return

		# Retrieving the data of the admin
		chat = message.reply_to_message.from_user

		# Removing the admin from the list
		admins_list.remove(chat.id)
	else:
		# Checking if the chat is in the list
		if message.chat.id not in chats_list:
			await res.split_reply_text(config, message, "The chat {} isn\'t present in the list of allowed chat.".format(message.chat.title), quote=False)
			logger.info("{} have sent an incorrect /remove request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
			return

		# Retrieving the data of the chat
		chat = message.chat

		# Deleting the message
		await message.delete(revoke=True)

		# Removing the chat from the list
		chats_list.remove(chat.id)

	# Removing the chat/user from the database
	with connection.cursor() as cursor:
		text = "Chat removed from the database."

		if cursor.execute("DELETE FROM `Chats` WHERE `id`=%(id)s;", {
			"id": chat.id
		}) == 0:
			cursor.execute("UPDATE `Players` SET `domain`=%(domain)s WHERE `id`=%(id)s;", {
				"id": chat.id,
				"domain": "all"
			})

			if cursor.execute("SELECT `id` FROM `Chats` WHERE `type`!=\'bot\' AND `domain`=\'all\' AND `type_into_guild`=\'utility\';") != 0:
				chats = list(map(lambda n: int(n["id"]), cursor.fetchall()))

				for i in chats:
					# Checking if the user is in the chat
					try:
						await client.get_chat_member(i, chat["id"])
					except ChannelInvalid:
						# Downgrading the player's privilege
						await client.promote_chat_member(i, chat["id"], can_change_info=False, can_post_messages=True, can_edit_messages=False, can_delete_messages=False, can_restrict_members=False, can_invite_users=True, can_pin_messages=False, can_promote_members=False)

			text = "Admin removed from the database."
	connection.commit()

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /remove because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("repaynest", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def repay_nest(client: Client, message: Message):
	# /repaynest <points> to <username>
	global config, nest_chat, players_allowed_list

	message.command.pop(0)

	# Checking if the command is correct
	if len(message.command) != 3:
		await res.split_reply_text(config, message, "The syntax is: <code>/repaynest &lt;points&gt; to &lt;username&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /repaynest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	try:
		index = message.command.index("to")
	except ValueError:
		await res.split_reply_text(config, message, "The syntax is: <code>/repaynest &lt;points&gt; to &lt;username&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /repaynest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	try:
		points = int(message.command[index - 1])
	except ValueError:
		await res.split_reply_text(config, message, "The syntax is: <code>/repaynest &lt;points&gt; to &lt;username&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /repaynest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the user's data
	user = await client.get_users(message.command[index + 1])

	# Checking if the user is authorized
	if user.id not in players_allowed_list:
		await res.split_reply_text(config, message, "You can repay stones Dragon's stones only to teammates.", quote=False)
		logger.info("{} have sent an incorrect /repaynest request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Removing the loan from the database
	with connection.cursor() as cursor:
		text = [
			"You doesn't have any debt with @{}.".format(user.username),
			None
		]

		if cursor.execute("SELECT `quantity` FROM `Nest_transaction` WHERE `donor_id`=%(donor_id)s AND `receiver_id`=%(receiver_id)s;", {
			"donor_id": user.id,
			"receiver_id": message.from_user.id
		}) != 0:
			text = [
				"I\'ve registered the repay.",
				"@{} repays {} points to @{}".format(message.from_user.username, points, user.username)
			]

			quantity = int(cursor.fetchone()["quantity"])

			if quantity - points < 0:
				text = [
					"Your debt with @{} is of {}.".format(user.username, points),
					None
				]
			else:
				quantity -= points

			# Updating the database
			if quantity == 0:
				cursor.execute("DELETE FROM `Nest_transaction` WHERE `donor_id`=%(donor_id)s AND `receiver_id`=%(receiver_id)s;", {
					"donor_id": user.id,
					"receiver_id": message.from_user.id
				})
			else:
				cursor.execute("UPDATE FROM `Nest_transaction` SET `quantity`=%(quantity)s WHERE `donor_id`=%(donor_id)s AND `receiver_id`=%(receiver_id)s;", {
					"quantity": quantity,
					"donor_id": user.id,
					"receiver_id": message.from_user.id
				})
	connection.commit()

	await res.split_reply_text(config, message, text[0], quote=False)
	if text[1] is not None:
		await client.send_message(nest_chat, text[1])

	logger.info("I\'ve answered to /repaynest because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("report", prefixes="/") & Filters.user(config.get("creator")) & Filters.private)
async def report(_, message: Message):
	# /report
	global config

	await res.split_reply_text(config, message, "\n".join(list(map(lambda n: "{} - {}".format(n["name"], n["description"]), config.get("commands")))), quote=False)

	logger.info("I\'ve answered to /report because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("rules", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def rules(_, message: Message):
	# /rules
	global config

	telegraph = Telegraph()
	rule = telegraph.get_page("IL-PATTO-DEI-DRAGHI-05-09", return_content=True, return_html=True)

	await res.split_reply_text(config, message, "These are the <a href=\"{}\">rules</a> of the Dragon\'s Guild.".format(rule["url"]), quote=False, disable_web_page_preview=True)
	logger.info("I\'ve answered to /rules because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("rulesnest", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def rules_nest(_, message: Message):
	# /rulesnest
	global config


	text = "This is the formula with you can ask a loans\n\nIf the level of your Dragon is between 10 and 49, you may require 10 levels\nIf the level of your Dragon is between 50 and 99, you may require 20 levels\nIf the level of your Dragon is between 100 and 149, you may require 30 levels\nIf the level of your Dragon is between from 150 and 199, you may require 40 levels\n\nAt these rates, if the applicant has just repaid a loan, he is entitled to a \"loyalty/liability bonus\" of 10 levels, to be added to the levels to which he would be entitled."

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I\'ve answered to /rulesnest because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("sellstones", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def sell_stones(_, message: Message):
	# /sellstones <points> <price_for_point>
	global config, connection

	message.command.pop(0)

	# Checking if the command is correct
	if len(message.command) != 2:
		await res.split_reply_text(config, message, "The syntax is: <code>/sellstones &lt;points&gt; &lt;priceForPoint&gt;</code>.\n<b>N.B.</> You can express the price with the short syntax (1k, etc.).", quote=False)
		logger.info("{} have sent an incorrect /sellstones request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the points to sell
	try:
		message.command[0] = int(message.command[0])
	except ValueError:
		await res.split_reply_text(config, message, "The syntax is: <code>/sellstones &lt;points&gt; &lt;priceForPoint&gt;</code>.\n<b>N.B.</> You can express the price with the short syntax (1k, etc.).", quote=False)
		logger.info("{} have sent an incorrect /sellstones request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the price of the points
	message.command[1] = res.price_str_to_int(message.command[1])
	if message.command[1] == -1:
		await res.split_reply_text(config, message, "The syntax is: <code>/sellstones &lt;points&gt; &lt;priceForPoint&gt;</code>.\n<b>N.B.</> You can express the price with the short syntax (1k, etc.).", quote=False)
		logger.info("{} have sent an incorrect /sellstones request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the list of the Dragon's stones
	with connection.cursor() as cursor:
		cursor.execute("SELECT `Items.id` AS `id`, `name`, `value`, `max_value`, `quantity` FROM `Items`, `Backpacks` WHERE `Items.id`=`Backpacks.item_id` AND `Backpacks.user_id`=%(user_id)s AND `name` COLLATE utf8_general_ci LIKE \'Pietra%\' AND `rarity`=\'D\' ORDER BY `value` DESC;", {
			"user_id": message.from_user.id,
		})
		stones = list(map(lambda n: n.update({
			"points": int(n["value"]) / 1000,
			"quantity_sell": 0
		}), cursor.fetchall()))

		for i in stones:
			i["id"] = int(i["id"])
			i["value"] = int(i["value"])
			i["max_value"] = int(i["max_value"])
			i["quantity"] = int(i["quantity"])

	stones = list(filter(lambda n: n["quantity"] is not None and n["quantity"] != 0, stones))

	# Applying limits at the price of the points
	if message.command[1] < stones[-1]["value"]:
		message.command[1] = stones[-1]["value"]
	elif message.command[1] > stones[-1]["max_value"]:
		message.command[1] = stones[-1]["max_value"]

	# Retrieving the number of points in the backpack
	points = list(map(lambda n: n["quantity"] * n["points"], stones))
	points = functools.reduce(lambda n, m: n + m, points)

	text = "You doesn\'t have enough stones to satisfy your request.\n"

	# Checking if the player have enough stones
	if points > message.command[0]:
		text = ""
		points = message.command[0]

	text += "I created the store with {} points.\n\n<code>".format(points)
	store = "/negozio "

	# Choosing the stones
	for i in stones:
		# Retrieving how many stones the player can sell
		number_stones = points // i["points"]

		if i["quantity"] < number_stones:
			number_stones = i["quantity"]

		# Decreasing the objective
		points -= number_stones * i["points"]

		# Setting the stones as selled
		i["quantity_sell"] = number_stones

		if points == 0:
			break

	stones = list(filter(lambda n: n["quantity_sell"] != 0, stones))

	# Creating the store
	stones = list(map(lambda n: "{}:{}:{}".format(n["name"], message.command[1] * n["points"], n["quantity_sell"]), stones))
	store += ", ".join(stones)

	keyboard = [
		[
			InlineKeyboardButton(text="Create the store", switch_inline_query=store)
		]
	]
	keyboard = InlineKeyboardMarkup(keyboard)

	text += "{}</code>.".format(store)

	await res.split_reply_text(config, message, text, quote=False, reply_markup=keyboard)
	logger.info("I\'ve answered to /sellstones because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("setwelcome", prefixes="/") & Filters.user(admins_list) & Filters.chat(chats_list) & Filters.group)
async def set_welcome(_, message: Message):
	# /setwelcome <text>
	global config, connection

	message.command.pop(0)

	# Checking if the command is correct
	if message.command is False:
		await res.split_reply_text(config, message, "The syntax is: <code>/setwelcome &lt;text&gt;</code>.", quote=False)
		logger.info("{} have sent an incorrect /setwelcome request.".format("@{}".format(message.from_user.username) if message.from_user.username is not None else message.from_user.id))
		return

	# Retrieving the welcome message
	welcome = " ".join(message.command)

	# Updating the welcome message
	with connection.cursor() as cursor:
		cursor.execute("UPDATE `Chats` SET `welcome`=%(welcome)s WHERE `id`=%(id)s;", {
			"welcome": welcome,
			"id": message.chat.id
		})
	connection.commit()

	await res.split_reply_text(config, message, "Welcome message setted.", quote=False)
	logger.info("I\'ve answered to /setwelcome because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("staff", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def staff(_, message: Message):
	# /staff
	global config, connection

	with connection.cursor() as cursor:
		cursor.execute("SELECT `username`, `domain` FROM `Players` WHERE `domain`!=\'all\' ORDER BY `domain` DESC, `username` COLLATE utf8_general_ci;")
		admins = cursor.fetchall().copy()

		admin_type = admins[0]["domain"]
		text = ["<i>{:^}:</i>".format(admin_type.capitalize())]

		for i in admins:
			if i["domain"] != admin_type:
				admin_type = i["domain"]
				text.append("\n<i>{:^}:</i>".format(admin_type.capitalize()))
			text.append("&gt; @{}".format(i["username"]))


	text = "The staff of the Dragon Guild is:\n{}.".format("\n".join(text))

	await res.split_reply_text(config, message, text, quote=False)
	logger.info("I have answered to /staff from @{}.".format(message.from_user.username))


@app.on_message(Filters.command("start", prefixes="/") & Filters.user(players_allowed_list) & Filters.private)
async def start(client: Client, message: Message):
	# /start
	global config

	await res.split_reply_text(config, "Welcome @{}.\nThis bot manage the Dragon\'s Guild.\nEnter in the <a href=\"https://t.me/CHANGELOGDragonEducatorBot\">[CHANGELOG] Educatore dei Draghi</a> to see every update of the bot.".format(message.from_user.username), quote=False)
	logger.info("I\'ve answered to /start because of @{}.".format(message.from_user.username))


@app.on_message(res.unknown_filter(config) & Filters.private)
async def unknown(_, message: Message):
	global config

	await res.split_reply_text(config, message, "This command isn\'t supported.", quote=False)
	logger.info("I managed an unsupported command.")


@app.on_message(Filters.command("update", prefixes="/") & Filters.user(admins_list) & Filters.private)
async def update(_, message: Message):
	# /update
	global config, connection, players_allowed_list

	players_allowed_list = list()
	await res.update_items_queue(config, connection)
	await res.update_players_queue(config, connection, players_allowed_list)
	await res.update_recipes_queue(config, connection)

	await res.split_reply_text(config, message, "Database updated.", quote=False)
	logger.info("I\'ve answered to /update because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("updateitems", prefixes="/") & Filters.user(admins_list) & Filters.private)
async def update_items(_, message: Message):
	# /updateitems
	global config, connection

	await res.update_items_queue(config, connection)

	await res.split_reply_text(config, message, "Items' list updated.", quote=False)
	logger.info("I\'ve answered to /updateitems because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("updateplayers", prefixes="/") & Filters.user(admins_list) & Filters.private)
async def update_players(_, message: Message):
	# /updateplayers
	global config, connection, players_allowed_list

	players_allowed_list = list()
	await res.update_players_queue(config, connection, players_allowed_list)

	await res.split_reply_text(config, message, "Players' list updated.", quote=False)
	logger.info("I\'ve answered to /updateplayers because of @{}.".format(message.from_user.username))


@app.on_message(Filters.command("updaterecipes", prefixes="/") & Filters.user(admins_list) & Filters.private)
async def update_recipes(_, message: Message):
	# /updaterecipes
	global config, connection

	await res.update_recipes_queue(config, connection)

	await res.split_reply_text(config, message, "Recipes' list updated.", quote=False)
	logger.info("I\'ve answered to /updaterecipes because of @{}.".format(message.from_user.username))


logger.info("Client initializated\nSetting the markup syntax ...")
app.set_parse_mode("html")

logger.info("Set the markup syntax\nStarted serving ...")
scheduler.start()
app.run()
connection.close()
