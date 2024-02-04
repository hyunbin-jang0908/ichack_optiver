import logging
import time
from typing import List
from optibook import common_types as t
from optibook import ORDER_TYPE_IOC, ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
import json

logging.getLogger('client').setLevel('ERROR')
logger = logging.getLogger(__name__)

INSTRUMENT_ID = 'SMALL_CHIPS'
INSTRUMENT_IDS = ['SMALL_CHIPS', 'TECH_INC', 'SMALL_CHIPS_NEW_COUNTRY', 'TECH_INC_NEW_COUNTRY']


class OrderStatusEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, t.OrderStatus):
            return str(obj)
        return super().default(obj)

def print_report(e: Exchange):
    pnl = e.get_pnl()
    positions = e.get_positions()
    my_trades = e.poll_new_trades(INSTRUMENT_ID)
    all_market_trades = e.poll_new_trade_ticks(INSTRUMENT_ID)
    logger.info(f'I have done {len(my_trades)} trade(s) in {INSTRUMENT_ID} since the last report. There have been {len(all_market_trades)} market trade(s) in total in {INSTRUMENT_ID} since the last report.')
    logger.info(f'My PNL is: {pnl:.2f}')
    logger.info(f'My current positions are: {json.dumps(positions, indent=3)}')
    logger.info("orders: " + json.dumps(e.get_outstanding_orders(INSTRUMENT_ID), cls=OrderStatusEncoder))

def print_order_response(order_response: InsertOrderResponse):
    if order_response.success:
        logger.info(f"Inserted order successfully, order_id='{order_response.order_id}'")
    else:
        logger.info(f"Unable to insert order with reason: '{order_response.success}'")


def trade_cycle(e: Exchange):
    # this is the main bot logic which gets called every 5 seconds
    # fetch the current order book

    for instrument_id in INSTRUMENT_IDS:
        tradable_instruments = e.get_instruments()

        # first we verify that the instrument we wish to trade actually exists
        if instrument_id not in tradable_instruments:
            logger.info(f"Unable to trade because instrument '{instrument_id}' does not exist")
            return

        # then we make sure that the instrument is not currently paused
        if tradable_instruments[instrument_id].paused:
            logger.info(f"Skipping cycle because instrument '{instrument_id}' is paused, will try again in the next cycle.")
            return

        # Get the latest order book
        book = e.get_last_price_book(instrument_id)
        position = e.get_positions()[instrument_id]

        # verify that the book exists and that it has at least one bid and ask
        if book and book.bids and book.asks:
            # Calculate the spread and mid price
            spread = book.asks[0].price - book.bids[0].price
            mid_price = (book.asks[0].price + book.bids[0].price) / 2

            # If the spread is wide enough, place orders to try and capture the spread
            if spread > 0.2:
                # Place a bid order slightly above the best bid price
                bid_price = book.bids[0].price - 0.1
                # Place an ask order slightly below the best ask price
                ask_price = book.asks[0].price + 0.1

                # Get the historical trade ticks
                trade_ticks = e.get_trade_tick_history(instrument_id)

                # Calculate the trend based on the last 5 trade ticks
                if len(trade_ticks) >= 7:
                    last_prices = [tick.price for tick in trade_ticks[-7:]]
                    trend = last_prices[-1] - last_prices[0]

                    # Adjust the trading volume based on the trend
                    if trend > 0:
                        saleVolume = 35  # Increase volume if trend is up
                    else:
                        volume = 15  # Decrease volume if trend is down

                    # Ensure the bid price is less than the ask price
                    if bid_price < ask_price:
                        response: InsertOrderResponse = e.insert_order(instrument_id, price=bid_price, volume=volume, side=SIDE_BID, order_type=ORDER_TYPE_IOC)
                        print_order_response(response)

                        response: InsertOrderResponse = e.insert_order(instrument_id, price=ask_price, volume=volume, side=SIDE_ASK, order_type=ORDER_TYPE_IOC)
                        print_order_response(response)

            # now look at whether you successfully inserted an order or not.
            # note: If you send invalid information, such as in instrument which does not exist, you will be disconnected
            
        else:
            logger.info(f"No top bid/ask or no book at all for the instrument '{instrument_id}'")

        print_report(e)


def main():
    exchange = Exchange()
    exchange.connect()

    # you can also define host/user/pass yourself
    # when not defined, it is taken from ~/.optibook file if it exists
    # if that file does not exists, an error is thrown
    #exchange = Exchange(host='host-to-connect-to', info_port=7001, exec_port=8001, username='your-username', password='your-password')
    #exchange.connect()

    sleep_duration_sec = 5
    while True:
        trade_cycle(exchange)
        logger.info(f'Iteration complete. Sleeping for {sleep_duration_sec} seconds')
        time.sleep(sleep_duration_sec)


if __name__ == '__main__':
    main()
