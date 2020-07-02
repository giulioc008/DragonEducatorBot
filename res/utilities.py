import asyncio
import datetime
import logging as logger
from pymysql.connections import Connection
from pyrogram import Client, Filters, InlineKeyboardButton, Message
from pyrogram.errors import FloodWait
import re
import requests
from res.configurations import Configurations


async def chat_button(client: Client, chat: dict, connection: Connection) -> InlineKeyboardButton:
	"""
		A coroutine that creates an InlineKeyboardButton form tha data of a chat
		:param client: The application
		:param chat: The chat's data
		:return: InlineKeyboardButton
	"""
	if chat["username"] is not None:
		invite_link = "https://t.me/{}".format(chat["username"])
	elif chat["invite_link"] is not None:
		invite_link = chat["invite_link"]
	else:
		# Generating the new invite_link
		invite_link = await client.export_chat_invite_link(int(chat["id"]))

		# Saving the new invite_link
		with connection.cursor() as cursor:
			cursor.execute("UPDATE `Chats` SET `invite_link`=%(invite_link)s WHERE `id`=%(id)s;", {
				"id": int(chat["id"]),
				"invite_link": invite_link
			})
		connection.commit()

	return InlineKeyboardButton(text=chat["title"], url=invite_link)


def craft_inner(user_id: int, request: list, connection: Connection, use_craft: bool = False) -> dict:
	"""
		A function that create the craft's data for a player
		:param user_id: The id of the player that start the craft
		:param request: The craft's data
		:param use_craft: The flag that manage the use of the craft into the backpack
		:return: dict

		request = [
					{
						"id": 0,
						"name": "",
						"quantity": 0
					},
						...
				]
	"""
	text = "You want craft these items: <code>"
	output = {
		"craft": list(),
		"base": list()
	}

	for i in request:
		i["id"] = int(i["id"])
		i["quantity"] = int(i["quantity"])

		text +=  "{}:{}, ".format(i["name"], i["quantity"])

		# Creating the items list
		tmp = {
			"craft": [i],
			"needed": list()
		}

		tmp = items_recursive_search(i, tmp)

		"""
			temporary = {
							"craft": [
								{
									"id": 0,
									"name": "",
									"quantity": 0
								},
								...
							],
							"base": [
								{
									"id": 0,
									"name": "",
									"quantity": 0
								},
								...
							]
						}
		"""

		# Saving the partial result
		for i in temporary["base"]:
			if output["base"] is True and i["id"] in list(map(lambda n: n["id"], output["base"])):
				for j in output["base"]:
					if j["id"] == i["id"]:
						j["quantity"] += i["quantity"]
						break
			else:
				output["base"].append(i)

		for i in temporary["craft"]:
			if output["craft"] is True and i["id"] in list(map(lambda n: n["id"], output["craft"])):
				for j in output["craft"]:
					if j["id"] == i["id"]:
						j["quantity"] += i["quantity"]
						break
			else:
				output["craft"].append(i)

	# Retrieving the craft points
	craft_points = 0
	with connection.cursor() as cursor:
		for i in output["craft"]:
			# Retrieving the item's craft_pnt
			cursor.execute("SELECT `craft_pnt` FROM `Items` WHERE `id`=%(id)s;", {
				"id": i["id"]
			})
			craft_points += int(cursor.fetchone()["craft_pnt"])

	# Decreasing the quantity of the crafted items already in the backpack
	if use_craft is True:
		with connection.cursor() as cursor:
			cursor.execute("SELECT `Backpacks.item_id` AS `id`, `Backpacks.quantity` AS `quantity` FROM `Backpacks`, `Items` WHERE `Backpacks.item_id`=`Items.item_id` AND `Items.craftable`=1 AND `Backpacks.user_id`=%(user_id)s;", {
				"user_id": user_id
			})

			for i in cursor.fetchall():
				if int(i["id"]) in list(map(lambda n: n["id"], output["craft"])):
					for j in output["craft"]:
						if j["id"] == int(i["id"]):
							j["quantity"] -= int(i["quantity"])
							break
		output["craft"] = list(filter(lambda n: n["quantity"] > 0, output["craft"]))

	# Retrieving the commands' list
	output["commands"] = list()
	for i in output["craft"]:
		# Checking if the item is already in the list
		if output["commands"] is True and i["id"] in list(map(lambda n: n["id"], output["commands"])):
			for j in output["commands"]:
				if j["id"] == i["id"]:
					# Checking if the quantity of the item in the command is less or equal to 3
					if j["quantity"] < 3:
						i["quantity"] -= 3 - j["quantity"]
						j["quantity"] = 3
					break

			# Checking if the quantity of the item is more then 3
			if i["quantity"] != 0:
				remainder = i["quantity"] % 3
				floored_quotient = i["quantity"] // 3

				i["quantity"] = 3
				for j in range(floored_quotient):
					output["commands"].append(i)

				i["quantity"] = remainder
				output["commands"].append(i)
		else:
			remainder = i["quantity"] % 3
			floored_quotient = i["quantity"] // 3

			i["quantity"] = 3
			for j in range(floored_quotient):
				output["commands"].append(i)

			i["quantity"] = remainder
			output["commands"].append(i)

		del i["name"]

	# Removing eventual empty commands
	output["commands"] = list(filter(lambda n: n["quantity"] != 0, output["commands"]))

	# Formatting the commands list
	output["commands"] = list(map(lambda n: "Crea {}{}".format(n["name"], ", {}".format(n["quantity"]) if n["quantity"] > 1 else ""), output["commands"]))

	text = text[: len(text) - len(", ")]
	text += "</code> obtaining {} craft points.\nYou will consume these items:\n\t{}".format(craft_points, "\n\t".join(list(map(lambda n: "> {} of {}".format(n["quantity"], n["name"]), output["base"]))))

	# Retrieving the missing base items
	with connection.cursor() as cursor:
		cursor.executemany("SELECT `item_id`, `quantity` FROM `Backpacks` WHERE `user_id`=%(user_id)s AND  `user_id`=%(user_id)s;", list(map(lambda n: {
			"user_id": user_id,
			"item_id": n["id"]
		}, output["base"])))
		backpack = cursor.fetchall().copy()

	for i in range(len(output["base"])):
		output["base"][i]["quantity"] -= backpack[i]["quantity"]

	output["base"] = list(filter(lambda n: n["quantity"] > 0, output["base"]))

	if output["base"] is True:
		output["base"] = list(map(lambda n: "> {} of {}".format(n["quantity"], n["name"]), output["base"]))
		text += "\nYou missing these items:\n\t".format("\n\t".join(output.pop("base")))

	output.pop("craft")
	output["text"] = text

	return output


async def edit_board(config: Configurations, nest_pinned_message: Message):
	"""
		A coroutine that edits the board
		:return: None
	"""
	if nest_pinned_message is None:
		return

	text = print_board()
	if len(text) >= config.get("message_max_length"):
		# Generating the new pinned message
		nest_pinned_message = await nest_pinned_message.reply_text(text[: config.get("message_max_length")], quote=False)
		tmp = nest_pinned_message

		for i in range(1, len(text), config.get("message_max_length")):
			try:
				tmp = await tmp.reply_text(text[i : i + config.get("message_max_length")], quote=True)
			except FloodWait as e:
				asyncio.sleep(e.x)

		await nest_pinned_message.pin(disable_notification=True)
	else:
		await split_edit_text(nest_pinned_message, print_board())

	logger.info("I updated the board.")


def items_recursive_search(item: dict, request: dict, config: Configurations) -> dict:
	"""
		A function that searches recursively the items needed for a craft
		:param item: The item to search
		:param request: The craft's data
		:return: dict

		item = {
					"id": 0,
					"name": "",
					"quantity": 0
				}

		request = {
					"craft": [
						{
							"id": 0,
							"name": "",
							"quantity": 0
						},
						...
					],
					"base": [
						{
							"id": 0,
							"name": "",
							"quantity": 0
						},
						...
					]
				}
	"""
	# Downloading the item's informations
	response = requests.get(url="https://fenixweb.net:6600/api/v2/{}/crafts/{}/needed".format(config.get("loot_api_token"), item["id"]))

 	# Checking of the download is done
	response.raise_for_status()

	# Retrieving the item's informations
	result = response.json()
	result = result["res"]

	for i in result:
		flag = bool(i.pop("craftable"))
		item_type = "base"

		# Removing the inutil informations
		i.pop("rarity")

		# Checking if the item is craftable
		if flag is True:
			item_type = "craft"

		i["id"] = int(i["id"])
		i["quantity"] = 1

		# Adding the item to the opportune items list
		if request["{}".format(item_type)] is True and i["id"] in list(map(lambda n: n["id"], request["{}".format(item_type)])):
			for j in request["{}".format(item_type)]:
				if j["id"] == i["id"]:
					j["quantity"] += i["quantity"]
					break
		else:
			request["{}".format(item_type)].append(i)

		# Checking if the item is craftable and, in case, recurring
		if flag is True:
			request = items_recursive_search(i, request)

	return request


def order_by_rarty(rarity_x: str, rarity_y: str) -> int:
	"""
		A function that order two items by theirs rarity
		:param rarity_x: The rarity of the first item
		:param rarity_y: The rarity of the second item
		:return: int
	"""
	if rarity_x == rarity_y:
		return 0
	elif rarity_x == "D":
		return 1
	elif rarity_y == "D":
		return -1
	elif rarity_x == "A":
		return 1
	elif rarity_y == "A":
		return -1
	elif rarity_x == "X":
		return 1
	elif rarity_y == "X":
		return -1
	elif rarity_x == "U":
		return 1
	elif rarity_y == "U":
		return -1
	elif rarity_x == "S":
		return 1
	elif rarity_y == "S":
		return -1
	elif rarity_x == "UE":
		return 1
	elif rarity_y == "UE":
		return -1
	elif rarity_x == "E":
		return 1
	elif rarity_y == "E":
		return -1
	elif rarity_x == "L":
		return 1
	elif rarity_y == "L":
		return -1
	elif rarity_x == "UR":
		return 1
	elif rarity_y == "UR":
		return -1
	elif rarity_x == "R":
		return 1
	elif rarity_y == "R":
		return -1
	elif rarity_x == "NC":
		return 1
	elif rarity_y == "NC":
		return -1
	elif rarity_x == "C":
		return 1
	else:
		return -1


async def post_statistics(client: Client, config: Configurations, connection: Connection, statistics: dict):
	"""
		A coroutine that posts the statistics of the Guild
		:param client: The application
		:return: None
	"""
	# Checking if it's the correct moment to post the statistics
	if datetime.date.today().day != 1 and datetime.date.weekday() != 0:
		return

	text = ""

	# Retrieving the id of the "La Tana dei Draghi" chat
	with connection.cursor() as cursor:
		cursor.execute("SELECT `id` FROM `Chats` WHERE `title` COLLATE utf8_general_ci LIKE \'%Tana%\';")
		chat_id = int(cursor.fetchone()["id"])

	# Checking if is the 1st of the month
	if datetime.date.today().day == 1:
		# Retrieving the user's data
		user = await client.get_users(statistics["ability"].pop("id"))
		statistics["ability"]["username"] = user.username

		user = await client.get_users(statistics["craft_points"].pop("id"))
		statistics["craft_points"]["username"] = user.username

		user = await client.get_users(statistics["dragon"].pop("id"))
		statistics["dragon"]["username"] = user.username

		user = await client.get_users(statistics["experience"].pop("id"))
		statistics["experience"]["username"] = user.username

		user = await client.get_users(statistics["rank"].pop("id"))
		statistics["rank"]["username"] = user.username

		text = "Monthly statistics:\n\tRank: @{} with +{} points\n\tDragon: @{} with +{} levels\n\tAbility: @{} with +{} points\n\tLevel: @{} with +{} exp\n\tCraft Points: @{} with +{} PC".format(statistics["ability"]["username"], statistics["ability"]["quantity"], statistics["craft_points"]["username"], statistics["craft_points"]["quantity"], statistics["dragon"]["username"], statistics["dragon"]["quantity"], statistics["experience"]["username"], statistics["experience"]["quantity"], statistics["rank"]["username"], statistics["rank"]["quantity"])

		# Resetting the statistics
		statistics.update({
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
			}
		})

	# Checking if is monday
	if datetime.date.weekday() == 0:
		# Retrieving the user's data
		user = await client.get_users(statistics["weekly_craft_points"].pop("id"))
		statistics["weekly_craft_points"]["username"] = user.username

		# Checking if is, also, 1st of the month
		if text != "":
			text += "\n\n"

		text += "Weekly statistics:\n\tCraft Points: @{} with +{} PC".format(statistics["weekly_craft_points"]["username"], statistics["weekly_craft_points"]["quantity"])

		# Resetting the statistics
		statistics.update({
			"weekly_craft_points": {
				"id": 0,
				"quantity": 0
			}
		})

	# Post the statistics
	await client.send_message(chat_id, text[: config.get("message_max_length")])
	if len(text) >= config.get("message_max_length"):
		for i in range(1, len(text), config.get("message_max_length")):
			try:
				await client.send_message(chat_id, text[i : i + config.get("message_max_length")])
			except FloodWait as e:
				asyncio.sleep(e.x)

	# Remind the statistics
	await remind_statistics(client)

	logger.info("I posted the statistics in the Den.")


def price_int_to_str(price: int) -> str:
	"""
		A function that converts a price in its string form.
		:param price: The price to convert
		:return: str
	"""
	groupsLength = 3
	price = str(price)
	start = len(price) % 3

	# Retrieving the first group
	convertedPrice = price[: start]

	# Retrieving the others groups
	for i in range(start, len(price), groupsLength):
		convertedPrice += "{}{}".format("." if convertedPrice != "" else "", price[i : i + groupsLength])

	return convertedPrice


def price_str_to_int(price: str) -> int:
	"""
		A function that converts a price in its integer form.
		:param price: The price to convert
		:return: int
	"""
	match = re.findall("^((\d+)\.?(\d+)?\.?(\d+)?\.?(\d+)?)(k*)$", price, re.MULTILINE | re.IGNORECASE | re.UNICODE)

	# Checking if the string have the correct syntax
	if match is False:
		return -1

	# Retrieving the match
	match = match.pop(0)
	match = list(match)

	# Determine the price
	price = int(match[0].replace(".", "")) * math.pow(10, len(match[-1]) * 3)
	price = int(price)

	return price


def print_board(connection: Connection) -> str:
	"""
		A function that prints the board.
		:return: str
	"""
	text = list()

	with connection.cursor() as cursor:
		# Retrieving the admins' ids
		cursor.execute("SELECT `Players.username` AS `username`, `Nest.missing_points` AS `missing_points` FROM `Nest`, `Players` WHERE `Nest.id`=`Players.id`;")

		for i in cursor.fetchall():
			text.append("<b>Player:</b> @{}\n\t<i>Points from the objective:</i> {}".format(i["username"], price_str_to_int(i["missing_points"])))

	text = "\n".join(text)

	if text == "":
		text = "The board is empty."

	return text


async def remind_statistics(client: Client, connection: Connection):
	"""
		A coroutine that reminds, at the admins, to update the statistics of the Guild
		:param client: The application
		:return: None
	"""
	# Checking if it's the correct moment to remind the statistics
	if datetime.date.today().day != 1 and datetime.date.weekday() != 0:
		return

	with connection.cursor() as cursor:
		# Retrieving the admins' ids
		cursor.execute("SELECT `id`, `username` FROM `Players` WHERE `domain`=\'admin\';")

		# Remind the statistics
		for i in cursor.fetchall():
			await client.send_message(int(i["id"]), "Hi @{},\nI want remind you to forward me the members detail of your team, this are necessary for monitor the statistics of the growth of the Guild.".format(i["username"]))

	logger.info("I reminded the statistics to the admins.")


async def split_edit_text(config: Configurations, message: Message, text: str, **options):
	"""
		A coroutine that edits the text of a message; if text is too long sends more messages.
		:param message: Message to edit
		:param text: Text to insert
		:return: None
	"""
	await message.edit_text(text[: config.get("message_max_length")], options)
	if len(text) >= config.get("message_max_length"):
		for i in range(1, len(text), config.get("message_max_length")):
			try:
				await message.reply_text(text[i : i + config.get("message_max_length")], options, quote=True)
			except FloodWait as e:
				await asyncio.sleep(e.x)


async def split_reply_text(config: Configurations, message: Message, text: str, **options):
	"""
		A coroutine that reply to a message; if text is too long sends more messages.
		:param message: Message to reply
		:param text: Text to insert
		:return: None
	"""
	await message.reply_text(text[: config.get("message_max_length")], options)
	if len(text) >= config.get("message_max_length"):
		for i in range(1, len(text), config.get("message_max_length")):
			try:
				await message.reply_text(text[i : i + config.get("message_max_length")], options)
			except FloodWait as e:
				await asyncio.sleep(e.x)


def unknown_filter(config: Configurations):
	def func(flt, message: Message):
		text = message.text
		if text:
			message.matches = list(flt.p.finditer(text)) or None
			if message.matches is False and text.startswith("/") is True and len(text) > 1:
				return True
		return False

	commands = list(map(lambda n: n["name"], config.get("commands")))

	return Filters.create(func, "UnknownFilter", p=re.compile("/{}".format("|/".join(commands)), 0))


async def update_items_queue(config: Configurations, connection: Connection):
	"""
		A coroutine that updates the database (only Items table)
		:return: None
	"""
	# Downloading the items' informations
	response = requests.get(url="https://fenixweb.net:6600/api/v2/{}/items".format(config.get("loot_api_token")))

	# Checking of the download is done
	response.raise_for_status()

	# Retrieving the items' informations
	result = response.json()
	result = result["res"]

	# Updating the database
	with connection.cursor() as cursor:
		for i in result:
			if cursor.execute("UPDATE `Items` SET `name`=%(name)s, `rarity`=%(rarity)s, `description`=%(description)s, `value`=%(value)s, `max_value`=%(max_value)s, `estimate`=%(estimate)s, `spread`=%(spread)s, `spread_tot`=%(spread_tot)s, `craftable`=%(craftable)s, `reborn`=%(reborn)s, `power`=%(power)s, `power_armor`=%(power_armor)s, `power_shield`=%(power_shield)s, `dragon_power`=%(dragon_power)s, `critical`=%(critical)s, `category`=%(category)s, `cons`=%(cons)s, `allow_sell`=%(allow_sell)s, `rarity_name`=%(rarity_name)s, `craft_pnt`=%(craft_pnt)s, `cons_val`=%(cons_val)s WHERE `id`=%(id)s;", i) == 0:
				cursor.execute("INSERT INTO `Items` (`id`, `name`, `rarity`, `description`, `value`, `max_value`, `estimate`, `spread`, `spread_tot`, `craftable`, `reborn`, `power`, `power_armor`, `power_shield`, `dragon_power`, `critical`, `category`, `cons`, `allow_sell`, `rarity_name`, `craft_pnt`, `cons_val`) VALUES (%(id)s, %(name)s, %(rarity)s, %(description)s, %(value)s, %(max_value)s, %(estimate)s, %(spread)s, %(spread_tot)s, %(craftable)s, %(reborn)s, %(power)s, %(power_armor)s, %(power_shield)s, %(dragon_power)s, %(critical)s, %(category)s, %(cons)s, %(allow_sell)s, %(rarity_name)s, %(craft_pnt)s, %(cons_val)s);", i)
	connection.commit()

	logger.info("I updated the item list.")


async def update_players_queue(config: Configurations, connection: Connection, players_allowed_list: list):
	"""
		A coroutine that updates the database (only Players table)
		:return: None
	"""
	# Downloading the informations of the players that are part of the teams
	response = requests.get(url="https://fenixweb.net:6600/api/v2/{}/team/TEAM_NAME_1".format(config.get("loot_api_token")))

	# Checking of the download is done
	response.raise_for_status()

	# Reading of the players
	result = response.json()
	players_allowed_list.extend(list(map(lambda n: n["username"], result["res"])))

	# Downloading the informations of the players that are part of the teams
	response = requests.get(url="https://fenixweb.net:6600/api/v2/{}/team/TEAM_NAME_2".format(config.get("loot_api_token")))

	# Checking of the download is done
	response.raise_for_status()

	# Reading of the players
	result = response.json()
	players_allowed_list.extend(list(map(lambda n: n["username"], result["res"])))

	# Retrieving the players informations
	players_allowed_list = await client.get_users(players_allowed_list)

	users = list(map(lambda n: n.__dict__, players_allowed_list))

	# Updating the player database
	players_allowed_list = list(map(lambda n: n.id, players_allowed_list))

	with connection.cursor() as cursor:
		for i in users:
			i.pop("_client", None)
			i.pop("_", None)
			i.pop("photo", None)
			i.pop("restrictions", None)
			i.pop("status", None)
			i.pop("last_online_date", None)
			i.pop("next_offline_date", None)
			i.pop("dc_id", None)
			i.pop("is_self", None)
			i.pop("is_contact", None)
			i.pop("is_mutual_contact", None)
			i.pop("is_deleted", None)
			i.pop("is_bot", None)
			i.pop("is_verified", None)
			i.pop("is_restricted", None)
			i.pop("is_scam", None)
			i.pop("is_support", None)
			i.pop("language_code", None)
			if cursor.execute("UPDATE `Players` SET `first_name`=%(first_name)s, `last_name`=%(last_name)s, `username`=%(username)s, `phone_number`=%(phone_number)s WHERE `id`=%(id)s;", i) == 0:
				cursor.execute("INSERT INTO `Players` (`id`, `first_name`, `last_name`, `username`, `phone_number`) VALUES (%(id)s, %(first_name)s, %(last_name)s, %(username)s, %(phone_number)s);", i)
	connection.commit()

	logger.info("I updated the player list.")


async def update_recipes_queue(config: Configurations, connection: Connection):
	"""
		A coroutine that updates the database (only Recipes table)
		:return: None
	"""
	# Downloading the informations of the recipes
	response = requests.get(url="https://fenixweb.net:6600/api/v2/{}/crafts/id".format(config.get("loot_api_token")))

	# Checking of the download is done
	response.raise_for_status()

	# Retrieving the recipes' informations
	result = response.json()
	result = result["res"]

	# Updating the database
	with connection.cursor() as cursor:
		for i in result:
			cursor.execute("SELECT `name` FROM `Items` WHERE `id`=%(id)s;", {
				"id": i["material_result"]
			})
			i["command"] = "Crea {}".format(cursor.fetchone()["name"])

			if cursor.execute("UPDATE `Recipes` SET `material_1`=%(material_1)s, `material_2`=%(material_2)s, `material_3`=%(material_3)s, `material_result`=%(material_result)s, `command`=%(command)s WHERE `id`=%(id)s;", i) == 0:
				cursor.execute("INSERT INTO `Recipes` (`id`, `material_1`, `material_2`, `material_3`, `material_result`, `command`) VALUES (%(id)s, %(material_1)s, %(material_2)s, %(material_3)s, %(material_result)s, %(command)s);", i)
	connection.commit()

	logger.info("I updated the recipe list.")



