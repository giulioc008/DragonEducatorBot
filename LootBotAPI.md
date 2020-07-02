# Guide to LootBot API

			Oggetti:
https://fenixweb.net:6600/api/v2/{TOKEN}/items  
https://fenixweb.net:6600/api/v2/{TOKEN}/items/(itemID)  
https://fenixweb.net:6600/api/v2/{TOKEN}/items/(itemName)  
https://fenixweb.net:6600/api/v2/{TOKEN}/items/(rarity)

			Creazioni:
https://fenixweb.net:6600/api/v2/{TOKEN}/crafts/(itemID)/needed  
https://fenixweb.net:6600/api/v2/{TOKEN}/crafts/(itemID)/used  
https://fenixweb.net:6600/api/v2/{TOKEN}/crafts/id

			Cronologie:
https://fenixweb.net:6600/api/v2/{TOKEN}/history/market?limit=(quantity)&offset=(distacco)&from=(username)&to=(username)&fromItem=(item)&toItem=(item)&both=(username)&fromPrice=(price)&toPrice=(price)&orderBy=(asc|desc)  
https://fenixweb.net:6600/api/v2/{TOKEN}/history/market_direct?limit=(quantity)&offset=(distacco)&from=(username)&to=(username)&fromItem=(item)&toItem=(item)&both=(username)&fromPrice=(price)&toPrice=(price)&orderBy=(asc|desc)  
https://fenixweb.net:6600/api/v2/{TOKEN}/history/lotteries?limit=(quantity)&offset=(distacco)&from=(username)&to=(username)&fromItem=(item)&toItem=(item)&both=(username)&fromPrice=(price)&toPrice=(price)&orderBy=(asc|desc)  
https://fenixweb.net:6600/api/v2/{TOKEN}/history/auctions?limit=(quantity)&offset=(distacco)&from=(username)&to=(username)&fromItem=(item)&toItem=(item)&both=(username)&fromPrice=(price)&toPrice=(price)&orderBy=(asc|desc)  
https://fenixweb.net:6600/api/v2/{TOKEN}/history/payments?limit=(quantity)&offset=(distacco)&from=(username)&to=(username)&fromItem=(item)&toItem=(item)&both=(username)&fromPrice=(price)&toPrice=(price)&orderBy=(asc|desc)  
https://fenixweb.net:6600/api/v2/{TOKEN}/history/heists?limit=(quantity)&offset=(distacco)&from=(username)&to=(username)&fromItem=(item)&toItem=(item)&both=(username)&fromPrice=(price)&toPrice=(price)&orderBy=(asc|desc)  
	limit: int = 100		quantità di risultati  
	offset: int = None		distacco dal limit  
	from: str = None		username che ha iniziato la transazione  
	to: str = None			username destinatario per la transazione  
	fromItem: str = None	oggetto del mittente  
	toItem: str = None		oggetto del destinatario  
	both: str = None		username di mittente e destinatario insieme  
	fromPrice: int = None	prezzo minimo compreso  
	toPrice: int = None		prezzo massimo compreso  
	orderBy: str = None		ordinamento dei risultati

			Giocatori:
https://fenixweb.net:6600/api/v2/{TOKEN}/players  
https://fenixweb.net:6600/api/v2/{TOKEN}/players/(name)

			Negozi:
https://fenixweb.net:6600/api/v2/{TOKEN}/shop/(code)

			Team:
https://fenixweb.net:6600/api/v2/{TOKEN}/team/(name)

			Ricerche:
https://fenixweb.net:6600/api/v2/{TOKEN}/search/(quantity)

			Altre info:
https://fenixweb.net:6600/api/v2/{TOKEN}/info  
https://fenixweb.net:6600/api/v2/{TOKEN}/global

