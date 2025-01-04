import time
from binance.client import Client
from binance.enums import *
from config import API_KEY, API_SECRET  # Import API keys from config.py

# Initialize Binance client
client = Client(api_key=API_KEY, api_secret=API_SECRET, testnet=True)

def Pric_Precision(price, symbol):
    """
    Adjusts price to the nearest tick size for the symbol.
    """
    tick_size = [float(x['filters'][0]['tickSize']) for x in client.futures_exchange_info()['symbols'] if x['symbol'] == symbol][0]
    return round(round(float(price) / tick_size) * tick_size, len(str(tick_size).split('.')[-1]))

def QUN_Precision(quantity, symbol):
    """
    Adjusts quantity to the required precision for the symbol.
    """
    precision = [x['quantityPrecision'] for x in client.futures_exchange_info()['symbols'] if x['symbol'] == symbol][0]
    return round(float(quantity), precision)

def place_limit_order(symbol, side, price, quantity):
    """
    Places a limit order on Binance.

    :param symbol: Trading pair (e.g., BTCUSDT)
    :param side: BUY or SELL
    :param price: Limit price
    :param quantity: Order quantity
    """
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=FUTURE_ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            price=price,
            quantity=quantity
        )
        print(f"Limit order placed: {order}")
        return order
    except Exception as e:
        print(f"Error placing limit order: {e}")
        raise RuntimeError("Failed to place limit order")

def cancel_open_orders(symbol):
    """
    Cancels all open orders for a given symbol.

    :param symbol: Trading pair (e.g., BTCUSDT)
    """
    try:
        open_orders = client.futures_get_open_orders(symbol=symbol)
        for order in open_orders:
            client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
            print(f"Canceled order: {order['orderId']}")
    except Exception as e:
        print(f"Error canceling orders: {e}")
        raise RuntimeError("Failed to cancel open orders")

def check_order_execution(order_id, symbol):
    """
    Checks if an order has been executed.

    :param order_id: The ID of the order to check
    :param symbol: Trading pair (e.g., BTCUSDT)
    :return: True if the order is filled, False otherwise
    """
    try:
        while True:
            order_status = client.futures_get_order(symbol=symbol, orderId=order_id)
            if order_status['status'] == 'FILLED':
                print(f"Order {order_id} filled.")
                return True
            time.sleep(2)  # Wait before checking again
    except Exception as e:
        print(f"Error checking order status: {e}")
        raise RuntimeError("Failed to check order execution")

def place_stop_loss(symbol, side, stop_price, quantity):
    """
    Places a stop-loss order on Binance.

    :param symbol: Trading pair (e.g., BTCUSDT)
    :param side: BUY or SELL
    :param stop_price: Stop loss price
    :param quantity: Order quantity
    """
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=FUTURE_ORDER_TYPE_STOP_MARKET,
            stopPrice=stop_price,
            quantity=quantity
        )
        print(f"Stop-loss order placed: {order}")
        return order
    except Exception as e:
        print(f"Error placing stop-loss order: {e}")
        raise RuntimeError("Failed to place stop-loss order")

def trading_strategy(symbol, position_type, entry_price, entry_volume, take_profit_price, dip_buy_1_limit, dip_buy_1_volume, dip_buy_1_target, dip_buy_2_limit, dip_buy_2_volume, dip_buy_2_target, stop_loss_price):
    """
    Executes the trading strategy based on user inputs.
    """
    side_entry = SIDE_BUY if position_type == "long" else SIDE_SELL
    side_exit = SIDE_SELL if position_type == "long" else SIDE_BUY

    # Place the initial entry order
    entry_order = place_limit_order(symbol, side_entry, entry_price, entry_volume)
    if not check_order_execution(entry_order['orderId'], symbol):
        raise RuntimeError("Initial entry order not executed. Exiting strategy.")

    # Place initial take-profit order
    tp_order = place_limit_order(symbol, side_exit, take_profit_price, entry_volume)

    # Place first dip buy order
    dip_buy_1_order = place_limit_order(symbol, side_entry, dip_buy_1_limit, dip_buy_1_volume)
    dip_buy_2_order = None  # To be placed after dip buy 1
    sl_order = None  # To be placed after dip buy 2

    # Monitoring loop
    while True:
        open_orders = client.futures_get_open_orders(symbol=symbol)
        open_order_ids = [order['orderId'] for order in open_orders]

        # Check if take-profit order is executed
        if tp_order['orderId'] not in open_order_ids:
            print("Take profit executed. Cancelling all other open orders and exiting.")
            cancel_open_orders(symbol)
            break

        # Check if stop-loss order is executed
        if sl_order and sl_order['orderId'] not in open_order_ids:
            print("Stop-loss executed. Cancelling all other open orders and exiting.")
            cancel_open_orders(symbol)
            break

        # Check if dip buy 1 is executed
        if dip_buy_1_order and dip_buy_1_order['orderId'] not in open_order_ids:
            print("Dip buy 1 executed. Adjusting take profit and placing dip buy 2.")
            cancel_open_orders(symbol)
            total_volume = QUN_Precision(entry_volume + dip_buy_1_volume, symbol)
            tp_order = place_limit_order(symbol, side_exit, dip_buy_1_target, total_volume)
            dip_buy_2_order = place_limit_order(symbol, side_entry, dip_buy_2_limit, dip_buy_2_volume)
            dip_buy_1_order = None  # Remove reference to dip buy 1

        # Check if dip buy 2 is executed
        if dip_buy_2_order and dip_buy_2_order['orderId'] not in open_order_ids:
            print("Dip buy 2 executed. Adjusting take profit and placing stop-loss.")
            cancel_open_orders(symbol)
            total_volume = QUN_Precision(entry_volume + dip_buy_1_volume + dip_buy_2_volume, symbol)
            tp_order = place_limit_order(symbol, side_exit, dip_buy_2_target, total_volume)
            sl_order = place_stop_loss(symbol, side_exit, stop_loss_price, total_volume)
            dip_buy_2_order = None  # Remove reference to dip buy 2

        time.sleep(2)

def main():
    """
    Main function to execute the trading bot. Collects user inputs and initiates the trading strategy.
    """
    print("Welcome to the Binance Trading Bot!")

    # Collect user inputs
    symbol = input("Enter the trading pair (e.g., BTCUSDT): ").strip().upper()

    # Long or Short position
    position_type = input("Enter the position type (long/short): ").strip().lower()
    if position_type not in ["long", "short"]:
        print("Invalid position type! Please enter 'long' or 'short'.")
        return

    entry_price = Pric_Precision(float(input("Enter the entry price: ")), symbol)
    entry_volume = QUN_Precision(float(input("Enter the entry volume: ")), symbol)
    take_profit_price = Pric_Precision(float(input("Enter the take profit price: ")), symbol)
    stop_loss_price = Pric_Precision(float(input("Enter the stop-loss price: ")), symbol)

    dip_buy_1_limit = Pric_Precision(float(input("Enter the first dip buy limit price: ")), symbol)
    dip_buy_1_volume = QUN_Precision(float(input("Enter the first dip buy volume: ")), symbol)
    dip_buy_1_target = Pric_Precision(float(input("Enter the first dip take profit price: ")), symbol)

    dip_buy_2_limit = Pric_Precision(float(input("Enter the second dip buy limit price: ")), symbol)
    dip_buy_2_volume = QUN_Precision(float(input("Enter the second dip buy volume: ")), symbol)
    dip_buy_2_target = Pric_Precision(float(input("Enter the second dip take profit price: ")), symbol)

    # Confirm inputs with user
    print("\nTrading Parameters:")
    print(f"Symbol: {symbol}")
    print(f"Position Type: {position_type.capitalize()}")
    print(f"Entry Price: {entry_price}")
    print(f"Entry Volume: {entry_volume}")
    print(f"Take Profit: {take_profit_price}")
    print(f"Stop Loss Price: {stop_loss_price}")
    print(f"Dip Buy 1: Limit {dip_buy_1_limit}, Volume {dip_buy_1_volume}, Target {dip_buy_1_target}")
    print(f"Dip Buy 2: Limit {dip_buy_2_limit}, Volume {dip_buy_2_volume}, Target {dip_buy_2_target}")

    confirm = input("Do you want to proceed with these parameters? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Exiting the bot. No trades were placed.")
        return

    # Execute the trading strategy
    try:
        trading_strategy(
            symbol=symbol,
            position_type=position_type,
            entry_price=entry_price,
            entry_volume=entry_volume,
            take_profit_price=take_profit_price,
            dip_buy_1_limit=dip_buy_1_limit,
            dip_buy_1_volume=dip_buy_1_volume,
            dip_buy_1_target=dip_buy_1_target,
            dip_buy_2_limit=dip_buy_2_limit,
            dip_buy_2_volume=dip_buy_2_volume,
            dip_buy_2_target=dip_buy_2_target,
            stop_loss_price=stop_loss_price
        )
        print("Trading strategy executed successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
