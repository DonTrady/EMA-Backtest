import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import pickle
import json
import os
import os.path
import re
from web3 import Web3

# Replace with your Dextools API key
api_key = 'ba42eba22b88424f554d326ef324933b'
options = ["25%", "50%", "75%", "100%"]

# DEX Tools API URL
api_url = 'https://api.dextools.io/v1/pair'

# Load data from a JSON file if it exists
data_file_path = 'bot_data.pkl'

# Function to fetch token price from DEX Tools API
def fetch_price(token_address):
    params = {
        'chain': 'ether',
        'address': token_address
    }
    headers = {
        'accept': 'application/json',
        'X-API-Key': api_key
    }

    response = requests.get(api_url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()['data']
        price = data.get('price')
        if price is not None:
            return price
    return None

def save_data_for_user(user_id, user_data):
    data_file_path = f'bot_data_{user_id}.pkl'
    with open(data_file_path, 'wb') as file:
        pickle.dump(user_data, file)

def load_data_for_user(user_id):
    data_file_path = f'bot_data_{user_id}.pkl'
    try:
        with open(data_file_path, 'rb') as file:
            user_data = pickle.load(file)
            return user_data
    except FileNotFoundError:
        return {'purchased_tokens': {}, 'profit_loss_transactions': []}


# Function to handle the /start command and provide usage instructions
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id  # Get the chat ID of the user
    welcome_message = "Welcome to Dons Paper Trading bot!\n\n"
    usage_instructions = "To find the price of a token, use /c followed by the ETH address of the token.\n\n" \
                         "For example: /c 0x58d7e1d45e9ed962d3279b3834dc8f6bb4aa12b3\n\n" \
                         "To buy a token, use /b followed by the ETH address of the token and the amount in USD you want to spend.\n\n" \
                         "For example: /b 0x58d7e1d45e9ed962d3279b3834dc8f6bb4aa12b3 100\n\n" \
                         "To check the tokens you have bought, use /t\n\n" \
                         "To sell a token, use /s followed by the ETH address of the token and the number of tokens you want to sell.\n\n" \
                         "For example: /s 0x58d7e1d45e9ed962d3279b3834dc8f6bb4aa12b3 50\n\n" \
                         "To view daily profit and loss, use /p\n\n" \
                         "To list all transactions, use /l"
    user_data = load_data_for_user(user_id)
    purchased_tokens = user_data['purchased_tokens']

    # Pass the user-specific data when saving data
    user_data['purchased_tokens'] = purchased_tokens
    save_data_for_user(user_id, user_data)

    full_message = welcome_message + usage_instructions

    update.message.reply_text(full_message)

    # Custom menu setup
    custom_menu = [
        [KeyboardButton("/c - Check Price"), KeyboardButton("/b - Buy Token")],
        [KeyboardButton("/t - Check Tokens"), KeyboardButton("/s - Sell Token")],
        [KeyboardButton("/p - Daily P/L"), KeyboardButton("/l - List Transactions")],
        [KeyboardButton("/start")]
    ]

    reply_markup = ReplyKeyboardMarkup(custom_menu, resize_keyboard=True)

    update.message.reply_text(
        "Please choose an option:",
        reply_markup=reply_markup
    )

def handle_token_address(update: Update, context: CallbackContext):
    text = update.message.text  # Extract the text from the message

    # Check if the text is a valid token address
    if is_valid_token_address(text):
        price = fetch_price(text)
        if price:
            update.message.reply_text(f"Current Price for token {text}: {price:.18f} USD")
        else:
            update.message.reply_text(f"Unable to fetch price for token {text}")
            
def is_valid_token_address(address: str) -> bool:
    # This is a placeholder. Modify this based on the actual criteria for valid token addresses.
    return len(address) == 42 and address.startswith("0x")


# Function to handle the /checkprice command (now /c)
def check_price_command(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("Please provide a token address with /c.")
        return

    token_address = context.args[0]
    token_price = fetch_price(token_address)

    if token_price is not None:
        update.message.reply_text(f"The token price for {token_address} is {token_price:.18f} USD.")
    else:
        update.message.reply_text("Sorry, I couldn't fetch the price. Please check the address or try again later.")

# Function to fetch the current price of Ethereum in USD from CoinGecko
def fetch_ethereum_price_usd():
    # Define the URL for fetching ETH price from CoinGecko
    ethereum_price_url = 'https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd'

    try:
        # Send a GET request to the CoinGecko API
        response = requests.get(ethereum_price_url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            data = response.json()
            # Extract the current ETH price in USD
            ethereum_price_usd = data.get('ethereum', {}).get('usd')
            return ethereum_price_usd
        else:
            print("Unable to fetch Ethereum price in USD from CoinGecko.")
            return None
    except Exception as e:
        print(f"Error fetching Ethereum price from CoinGecko: {str(e)}")
        return None

# Function to handle the /buytoken command
def buy_token_command(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        update.message.reply_text("Please provide the token address and the amount in USD with the /buytoken command.")
        return
    
    token_address = context.args[0]
    investment_amount_usd = float(context.args[1])
    user_id = update.effective_user.id
    user_data = load_data_for_user(user_id)
    purchased_tokens = user_data['purchased_tokens']

    token_price_usd = fetch_price(token_address)

    if token_price_usd is not None:
        ethereum_price_usd = fetch_ethereum_price_usd()

        if ethereum_price_usd is not None:
            tokens_bought = investment_amount_usd / token_price_usd
            transaction_timestamp = str(datetime.datetime.now())

            response = requests.get(api_url, params={'chain': 'ether', 'address': token_address},
                                    headers={'accept': 'application/json', 'X-API-Key': api_key})

            if response.status_code == 200:
                data = response.json()['data']
                token_name = data.get('token', {}).get('name', 'Unknown Token')
            else:
                update.message.reply_text('Error: Unable to fetch token data from DEX Tools API')
                return

            purchase_info = {
                'token_address': token_address,
                'token_name': token_name,
                'investment_amount_usd': investment_amount_usd,
                'tokens_bought': tokens_bought,
                'purchase_price_usd': token_price_usd,
                'transaction_timestamp': transaction_timestamp
            }

            purchased_tokens[token_address] = purchase_info
            user_data['profit_loss_transactions'].append(purchase_info)
            save_data_for_user(user_id, user_data)

            update.message.reply_text(f"You have successfully purchased {tokens_bought:.18f} tokens and the data has been saved.")
        else:
            update.message.reply_text("Error: Unable to determine Ethereum price in USD. Please try again later.")
    else:
        update.message.reply_text("Error: Unable to fetch token price or the token price is not available.")
        

# Function to handle the /selltoken command
def sell_token_command(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        update.message.reply_text("Please provide the token address and the number of tokens you want to sell with the /selltoken command.")
        return

    token_address = context.args[0]
    tokens_sold = float(context.args[1])
    user_id = update.effective_user.id
    user_data = load_data_for_user(user_id)
    purchased_tokens = user_data['purchased_tokens']

    if token_address in purchased_tokens:
        token_price_usd = fetch_price(token_address)

        if token_price_usd is not None:
            ethereum_price_usd = fetch_ethereum_price_usd()

            if ethereum_price_usd is not None:
                message = f"Current Ethereum Price (USD): {ethereum_price_usd:.18f} USD\n"
                message += f"The current price of the token is {token_price_usd:.18f} USD.\n"
                message += f"You own {purchased_tokens[token_address]['tokens_bought']:.18f} tokens at address: {token_address}\n"

                if tokens_sold > purchased_tokens[token_address]['tokens_bought']:
                    message += "Error: You cannot sell more tokens than you own."
                else:
                    selling_value_usd = tokens_sold * token_price_usd
                    transaction_timestamp = str(datetime.datetime.now())

                    sell_info = {
                        'token_address': token_address,
                        'token_name': purchased_tokens[token_address]['token_name'],
                        'tokens_sold': tokens_sold,
                        'selling_price_usd': token_price_usd,
                        'transaction_timestamp': transaction_timestamp
                    }

                    purchased_tokens[token_address]['tokens_bought'] -= tokens_sold
                    user_data['profit_loss_transactions'].append(sell_info)
                    save_data_for_user(user_id, user_data)

                    message += f"You have successfully sold {tokens_sold:.18f} tokens for {selling_value_usd:.18f} USD.\n"

                    profit_loss = selling_value_usd - (tokens_sold * purchased_tokens[token_address]['purchase_price_usd'])
                    message += f"Profit/Loss from Sale: {profit_loss:.18f} USD"

                update.message.reply_text(message)
            else:
                update.message.reply_text("Error: Unable to determine Ethereum price in USD. Please try again later.")
        else:
            update.message.reply_text("Error: Unable to fetch token price or the token price is not available.")
    else:
        update.message.reply_text("Error: You do not own tokens at the specified address.")

# Function to check tokens bought
def check_tokens_bought(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_data = load_data_for_user(user_id)
    purchased_tokens = user_data['purchased_tokens']

    if not purchased_tokens:
        update.message.reply_text("You haven't purchased any tokens yet.")
        return

    update.message.reply_text("List of Purchased Tokens:")

    for token_address, purchase_info in purchased_tokens.items():
        # Extracting the necessary details using your old code's approach
        message = f"Token Address: {token_address}\n" \
                  f"Token Name: {purchase_info['token_name']}\n" \
                  f"Investment Amount (USD): {purchase_info['investment_amount_usd']:.18f} USD\n"

        current_price_usd = fetch_price(token_address)
        if current_price_usd is not None:
            message += f"Current Price (USD): {current_price_usd:.18f} USD\n"
            current_value_usd = current_price_usd * purchase_info['tokens_bought']
            message += f"Current Value (USD): {current_value_usd:.18f} USD\n"
        else:
            message += "Error: Unable to fetch current token price.\n"

        message += f"Tokens Bought: {purchase_info['tokens_bought']:.18f} tokens\n" \
                   f"Purchase Price (USD): {purchase_info['purchase_price_usd']:.18f} USD\n" \
                   f"Transaction Timestamp: {purchase_info['transaction_timestamp']}\n"


        # The InlineKeyboardMarkup for selling options and deleting
        keyboard = [
            [
                InlineKeyboardButton("Sell 25%", callback_data=f"{token_address}_25%"),
                InlineKeyboardButton("Sell 50%", callback_data=f"{token_address}_50%"),
                InlineKeyboardButton("Sell 75%", callback_data=f"{token_address}_75%"),
                InlineKeyboardButton("Sell 100%", callback_data=f"{token_address}_100%")
            ],
            [
                InlineKeyboardButton("DELETE", callback_data=f"{token_address}_DELETE")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text(
            text=message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )


# Function to handle button presses for selling
def button_sell(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = load_data_for_user(user_id)
    purchased_tokens = user_data['purchased_tokens']
    # Inside the buy_token_command and sell_token_command functions
    # After modifying user-specific data, update and save it
    user_data['purchased_tokens'] = purchased_tokens
    save_data_for_user(user_id, user_data)
    # Extract data from the callback_data
    _, token_address, percentage = query.data.split("_")
    percentage = float(percentage.strip('%')) / 100  # Convert to a float (e.g., 25% -> 0.25)

    if token_address in purchased_tokens:
        tokens_to_sell = purchased_tokens[token_address]['tokens_bought'] * percentage
        token_price_usd = fetch_price(token_address)

        if token_price_usd is not None:
            selling_value_usd = tokens_to_sell * token_price_usd
            transaction_timestamp = str(datetime.datetime.now())

            sell_info = {
                'token_address': token_address,
                'token_name': purchased_tokens[token_address]['token_name'],
                'tokens_sold': tokens_to_sell,
                'selling_price_usd': token_price_usd,
                'transaction_timestamp': transaction_timestamp
            }

            purchased_tokens[token_address]['tokens_bought'] -= tokens_to_sell
            save_data_for_user(user_id, user_data)

            message = f"You have successfully sold {percentage * 100:.2f}% of your tokens for {selling_value_usd:.18f} USD."
            query.edit_message_text(message)
        else:
            query.edit_message_text("Error: Unable to fetch token price or the token price is not available.")
    else:
        query.edit_message_text("Error: You do not own tokens at the specified address.")


# Function to handle the /delete command
def delete_token_command(update: Update, context: CallbackContext):
    if len(context.args) != 1:
        update.message.reply_text("Please provide the token address to delete with the /delete command.")
        return

    token_address = context.args[0]
    user_id = update.effective_user.id
    user_data = load_data_for_user(user_id)
    purchased_tokens = user_data['purchased_tokens']

    if token_address in purchased_tokens:
        # Remove the token from the purchased_tokens dictionary
        del purchased_tokens[token_address]
        save_data_for_user(user_id, user_data)
        update.message.reply_text(f"The token at address {token_address} has been deleted from your list.")
    else:
        update.message.reply_text("Error: You do not own tokens at the specified address.")


# Function to list all transactions
def list_all_transactions(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_data = load_data_for_user(user_id)
    profit_loss_transactions = user_data.get('profit_loss_transactions', [])  # Get the user's transactions or an empty list if it doesn't exist

    if not profit_loss_transactions:
        update.message.reply_text("No transactions found.")
        return

    update.message.reply_text("List of All Transactions:")
    for i, transaction in enumerate(profit_loss_transactions, start=1):
        message = f"Transaction {i}:\n"
        for key, value in transaction.items():
            message += f"{key}: {value}\n"
        update.message.reply_text(message)

    # Check for open orders (buys without corresponding sells)
    open_buy_orders = {}
    for transaction in profit_loss_transactions:
        token_address = transaction.get('token_address')
        if token_address:
            if 'purchase_price_usd' in transaction:
                open_buy_orders[token_address] = open_buy_orders.get(token_address, 0) + 1
            elif 'selling_price_usd' in transaction:
                open_buy_orders[token_address] = open_buy_orders.get(token_address, 0) - 1

    for token_address, open_orders in open_buy_orders.items():
        if open_orders > 0:
            update.message.reply_text(f"Open buy orders for token address {token_address}: {open_orders} ORDER(S) STILL OPEN")

# Function to calculate daily profit/loss
def view_daily_profit_loss(update: Update, context: CallbackContext):
    print("view_daily_profit_loss function called!")
    user_id = update.effective_user.id
    daily_pnl = calculate_daily_profit_loss(user_id)
    
    message = "Daily Profit and Loss Summary:\n\n"
    if not daily_pnl:
        message += "No data available."
    else:
        for date, pnl_data in daily_pnl.items():
            message += f"{date} - Profit/Loss: {pnl_data['profit_loss']:.2f}, Open Buy Orders: {pnl_data['open_buy_orders']}\n"
    
    try:
        update.message.reply_text(message)
    except Exception as e:
        print(f"Error sending PnL message to user {user_id}: {e}")

# ... [The rest of your functions] ...

def calculate_daily_profit_loss(user_id):
    daily_pnl = {}
    open_buy_orders = 0

    # Load the user's data from the PKL file
    user_data = load_data_for_user(user_id)
    transactions = user_data.get('profit_loss_transactions', [])

    for transaction in transactions:
        print("Processing transaction:", transaction)
        date = transaction['transaction_timestamp'].split()[0]
        if date not in daily_pnl:
            daily_pnl[date] = {'profit_loss': 0.0, 'open_buy_orders': 0}

        if 'purchase_price_usd' in transaction:
            open_buy_orders += 1
        elif 'selling_price_usd' in transaction:
            purchase_transaction = next(
                (t for t in transactions if 'purchase_price_usd' in t and t['token_address'] == transaction['token_address']), None
            )

            if purchase_transaction:
                purchase_price_usd = purchase_transaction['purchase_price_usd']
                profit_loss = (transaction['selling_price_usd'] - purchase_price_usd) * transaction['tokens_sold']
                daily_pnl[date]['profit_loss'] += profit_loss
                open_buy_orders -= 1

        daily_pnl[date]['open_buy_orders'] = max(open_buy_orders, 0)

    return daily_pnl


if __name__ == '__main__':
    updater = Updater(token='6378848790:AAGbbHLapUvCbBX8v9vebjlYfU48raM2xI0', use_context=True)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('c', check_price_command, pass_args=True))
    dispatcher.add_handler(CommandHandler('b', buy_token_command, pass_args=True))
    dispatcher.add_handler(CommandHandler('t', check_tokens_bought))
    dispatcher.add_handler(CommandHandler('s', sell_token_command, pass_args=True))
    dispatcher.add_handler(CommandHandler('p', view_daily_profit_loss))
    dispatcher.add_handler(CommandHandler('l', list_all_transactions))
    dispatcher.add_handler(CommandHandler('d', delete_token_command, pass_args=True))
for option in options:
    dispatcher.add_handler(CallbackQueryHandler(button_sell, pattern=f"sell_.*_{option}"))

    updater.start_polling()
    updater.idle()



#   6378848790:AAGbbHLapUvCbBX8v9vebjlYfU48raM2xI0
#   ba42eba22b88424f554d326ef324933b
#   0x58d7e1d45e9ed962d3279b3834dc8f6bb4aa12b3
